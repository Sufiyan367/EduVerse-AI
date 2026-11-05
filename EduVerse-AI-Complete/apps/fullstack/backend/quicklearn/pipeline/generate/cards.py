"""Flashcard generation from concepts (PRD §7.3)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import delete, select

from ... import prompts
from ...db.enums import CardState, CardType
from ...db.models import Card, Concept, Source
from ...db.search import upsert_many
from ...db.session import raw_sqlite, session_scope
from ...db.types import utcnow
from ...providers import gateway
from ...providers.base import text_message
from ...settings import get_settings
from ..schemas import CardList

log = logging.getLogger(__name__)

CONCEPTS_PER_CALL = 12


def _safe_card_type(val: Any) -> CardType:
    if not val:
        return CardType.BASIC
    v = str(val).lower()
    if "cloze" in v:
        return CardType.CLOZE
    if "reverse" in v:
        return CardType.REVERSE
    return CardType.BASIC


async def generate_cards(
    source_id: int,
    *,
    max_cards: int | None = None,
    job_id: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[int]:
    """Generate cards for every concept on a source. Returns the new card ids."""
    settings = get_settings()
    cap = max_cards or settings.get_int("generation.max_cards_per_source", 50)

    with session_scope() as session:
        source = session.get(Source, source_id)
        title = source.title if source else ""
        concepts = list(
            session.execute(
                select(Concept)
                .where(Concept.source_id == source_id)
                .order_by(Concept.importance.desc(), Concept.id)
            ).scalars()
        )
        concept_data = [
            {
                "id": c.id,
                "name": c.name,
                "definition": c.definition,
                "importance": c.importance,
                "segment_ids": c.segment_ids,
            }
            for c in concepts
        ]

    collected: list[tuple[CardType, str, str, int | None, list[int]]] = []

    if concept_data:
        valid_concept_ids = {c["id"] for c in concept_data}
        per_concept = 2 if len(concept_data) * 2 <= cap else 1
        batches = [
            concept_data[i : i + CONCEPTS_PER_CALL]
            for i in range(0, len(concept_data), CONCEPTS_PER_CALL)
        ]
        for index, batch in enumerate(batches):
            try:
                prompt = prompts.render("cards", title=title, concepts=batch, max_per_concept=per_concept)
                result = await gateway.complete_structured(
                    "flashcards",
                    [text_message("user", prompt)],
                    CardList,
                    task_class="standard",
                    temperature=0.3,
                    source_id=source_id,
                    job_id=job_id,
                )
                by_id = {c["id"]: c for c in batch}
                for card in result.cards:
                    front, back = card.front.strip(), card.back.strip()
                    if not front or not back:
                        continue
                    concept_id = card.concept_id if card.concept_id in valid_concept_ids else None
                    if concept_id is None and len(batch) == 1:
                        concept_id = batch[0]["id"]
                    segment_ids = card.segment_ids or (
                        list(by_id.get(concept_id, {}).get("segment_ids", [])) if concept_id else []
                    )
                    collected.append((_safe_card_type(card.type), front, back, concept_id, segment_ids))
            except Exception as exc:
                log.warning("Concept flashcard batch %d failed: %s", index, exc)

            if on_progress:
                on_progress(index + 1, len(batches))

    # Fallback to segment-based flashcard synthesis if concepts were missing or yielded no cards
    if not collected:
        log.info("Generating flashcards directly from source segments for source %s", source_id)
        from ...db.models import Segment
        with session_scope() as session:
            segments = list(
                session.execute(
                    select(Segment)
                    .where(Segment.source_id == source_id)
                    .order_by(Segment.index)
                ).scalars()
            )

        if segments:
            # 1. Attempt LLM generation from combined segment sample
            sample_text = "\n\n".join([f"Passage {s.index + 1} (Page {s.page_no or 1}):\n{s.text[:500]}" for s in segments[:15]])
            llm_success = False
            try:
                prompt = (
                    f"Generate up to {min(cap, 15)} high-yield study flashcards based on this academic document: '{title}'.\n"
                    "For each card provide:\n"
                    "- type: 'concept' or 'definition'\n"
                    "- front: A specific, clear active-recall question or key concept\n"
                    "- back: An accurate, concise explanation or definition\n\n"
                    f"Document Excerpts:\n{sample_text[:3500]}"
                )
                result = await gateway.complete_structured(
                    "flashcards",
                    [text_message("user", prompt)],
                    CardList,
                    task_class="standard",
                    temperature=0.3,
                    source_id=source_id,
                    job_id=job_id,
                )
                for card in result.cards:
                    front, back = card.front.strip(), card.back.strip()
                    if front and back:
                        collected.append((_safe_card_type(card.type), front, back, None, [s.id for s in segments[:3]]))
                if collected:
                    llm_success = True
            except Exception as exc:
                log.debug("Segment-level LLM card generation failed, using deterministic extractor: %s", exc)

            # 2. Deterministic high-precision extraction fallback (works 100% offline)
            if not llm_success:
                import re
                seen_fronts = set()
                for seg in segments:
                    lines = [l.strip() for l in seg.text.split("\n") if l.strip()]
                    current_heading = None
                    for line in lines:
                        if line.startswith("#"):
                            heading_clean = re.sub(r"^#+\s*", "", line).strip()
                            if len(heading_clean) > 5 and heading_clean not in seen_fronts:
                                current_heading = heading_clean

                        # Check for Oral / Exam Questions: "Q: ... Ans: ..."
                        if re.match(r"^(?:Q\d*|Question)\s*[:\.]\s*(.+)", line, re.IGNORECASE):
                            q_text = re.sub(r"^(?:Q\d*|Question)\s*[:\.]\s*", "", line, flags=re.IGNORECASE).strip()
                            if len(q_text) > 8 and q_text not in seen_fronts:
                                seen_fronts.add(q_text)
                                collected.append((CardType.BASIC, q_text, seg.text[:300].strip(), None, [seg.id]))

                        # Check for definitions "Ans: ..."
                        elif line.startswith("Ans ->") or line.startswith("Ans:"):
                            ans_text = re.sub(r"^Ans\s*(?:->|:)\s*", "", line).strip()
                            if current_heading and len(ans_text) > 15:
                                card_front = f"In {current_heading}: What is the key principle or definition?"
                                if card_front not in seen_fronts:
                                    seen_fronts.add(card_front)
                                    collected.append((CardType.BASIC, card_front, ans_text, None, [seg.id]))

                        # Check for key term definitions "Term: Definition"
                        m_def = re.match(r"^([A-Z][A-Za-z0-9\s\-_/]{2,35})\s*:\s*(.{20,250})$", line)
                        if m_def:
                            term, defn = m_def.group(1).strip(), m_def.group(2).strip()
                            if not term.lower().startswith(("course", "manual", "date", "roll", "page", "note")):
                                card_front = f"Define: {term}"
                                if card_front not in seen_fronts:
                                    seen_fronts.add(card_front)
                                    collected.append((CardType.BASIC, card_front, defn, None, [seg.id]))

                    # If segment has a prominent practical / chapter heading, turn into a core card
                    if current_heading and current_heading not in seen_fronts and len(collected) < cap:
                        seen_fronts.add(current_heading)
                        front = f"What is the objective and overview of {current_heading}?"
                        descriptive = [l for l in lines if not l.startswith("#") and not l.startswith("```") and len(l) > 20]
                        back = " ".join(descriptive[:2]) if descriptive else seg.text[:200]
                        if len(back) > 15:
                            collected.append((CardType.BASIC, front, back.strip(), None, [seg.id]))

                    if len(collected) >= cap:
                        break

    if len(collected) > cap:
        log.info("trimming %d generated cards to the cap of %d", len(collected), cap)
        collected = collected[:cap]

    if not collected:
        return []

    now = utcnow()
    with session_scope() as session:
        session.execute(delete(Card).where(Card.source_id == source_id))
        session.flush()
        rows = [
            Card(
                source_id=source_id,
                concept_id=concept_id,
                type=card_type,
                front=front,
                back=back,
                segment_ids=segment_ids,
                # A new card is due immediately; FSRS takes over from the first review.
                due=now,
                state=CardState.NEW,
                step=0,
            )
            for card_type, front, back, concept_id, segment_ids in collected
        ]
        session.add_all(rows)
        session.flush()
        ids = [row.id for row in rows]

    with raw_sqlite() as conn:
        conn.execute("DELETE FROM search_docs WHERE kind = 'card' AND source_id = ?", (source_id,))
        upsert_many(
            conn,
            "card",
            [
                (card_id, front, back, source_id)
                for card_id, (_, front, back, _, _) in zip(ids, collected, strict=True)
            ],
        )

    log.info("generated %d cards for source %s", len(ids), source_id)
    return ids
