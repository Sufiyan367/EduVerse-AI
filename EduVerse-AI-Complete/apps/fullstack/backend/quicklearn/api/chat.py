"""Chat with cited answers over the user's own material (PRD §7.5)."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from .. import prompts
from ..auth import User, get_optional_user
from ..db.enums import ChatScope, MessageRole
from ..db.models import Chat, Message, Segment, Source
from ..db.session import session_scope
from ..errors import NotFoundError, QuicklearnError
from ..pipeline.schemas import FollowupQuestions
from ..providers import gateway
from ..providers.base import Message as ProviderMessage
from ..providers.base import text_message
from ..rag import retrieve as rag
from ..rag.manifest import get_user_source_manifest, render_manifest_note
from .common import chat_dict, message_dict, run_db, segment_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

CITATION_RE = re.compile(r"\[(\d+)\]")
#: Phrases that count as the model admitting it has nothing. Checked when retrieval was empty.
DISCLAIMER_MARKERS = (
    "don't cover",
    "do not cover",
    "not covered",
    "no information",
    "nothing in your",
    "couldn't find",
    "could not find",
    "isn't in your",
    "is not in your",
    "not found in",
    "don't contain",
    "do not contain",
    "no relevant",
    "not mentioned",
    "unable to find",
)
NO_CONTEXT_FALLBACK = (
    "I couldn't find anything in your notes that answers this. Try rephrasing, widening the "
    "scope to your whole library, or adding the source material first."
)

FOLLOWUP_PRONOUNS = {
    "it", "its", "they", "them", "their", "theirs", "this", "that", "these", "those",
    "the former", "the latter", "the first", "the second", "the third", "above", "mentioned",
    "previous", "explain further", "elaborate", "tell me more", "what about", "why", "how so"
}


class CreateChatRequest(BaseModel):
    scope_type: Literal["source", "folder", "global", "course", "topic"] = "global"
    scope_id: int | None = None
    title: str = ""


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


@router.post("")
def create_chat(
    payload: CreateChatRequest, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    if user is None:
        from ..errors import ForbiddenError
        raise ForbiddenError("Authentication required to create a chat.")
    with session_scope() as session:
        chat = Chat(
            user_id=user.id,
            scope_type=ChatScope(payload.scope_type),
            scope_id=payload.scope_id,
            title=payload.title.strip() or "New chat",
        )
        session.add(chat)
        session.flush()
        return chat_dict(chat)


@router.get("")
def list_chats(
    limit: int = 50, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    if user is None:
        return {"chats": []}
    with session_scope() as session:
        stmt = select(Chat).order_by(Chat.created_at.desc())
        if user.id == 1:
            stmt = stmt.where(or_(Chat.user_id == user.id, Chat.user_id.is_(None)))
        else:
            stmt = stmt.where(Chat.user_id == user.id)
        rows = list(session.execute(stmt.limit(limit)).scalars())
        counts = dict(
            session.execute(
                select(Message.chat_id, func.count(Message.id)).group_by(Message.chat_id)
            ).all()
        )
        return {
            "chats": [chat_dict(chat, message_count=int(counts.get(chat.id, 0))) for chat in rows]
        }


@router.get("/{chat_id}/messages")
def get_messages(
    chat_id: int, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    with session_scope() as session:
        chat = session.get(Chat, chat_id)
        if chat is None:
            raise NotFoundError(f"Chat {chat_id} not found.")
        if chat.user_id is not None:
            if user is None or chat.user_id != user.id:
                raise NotFoundError(f"Chat {chat_id} not found.")
        else:
            if user is None or user.id != 1:
                raise NotFoundError(f"Chat {chat_id} not found.")
        rows = list(
            session.execute(
                select(Message).where(Message.chat_id == chat_id).order_by(Message.id)
            ).scalars()
        )
        return {"chat": chat_dict(chat), "messages": [message_dict(m) for m in rows]}


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    with session_scope() as session:
        chat = session.get(Chat, chat_id)
        if chat is None:
            raise NotFoundError(f"Chat {chat_id} not found.")
        if chat.user_id is not None:
            if user is None or chat.user_id != user.id:
                raise NotFoundError(f"Chat {chat_id} not found.")
        else:
            if user is None or user.id != 1:
                raise NotFoundError(f"Chat {chat_id} not found.")
        session.delete(chat)
    return {"deleted": True}


@router.get("/citations")
def resolve_citations(
    ids: str, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    """Resolve citation markers to segments, for click-through from an answer."""
    try:
        wanted = [int(part) for part in ids.split(",") if part.strip()]
    except ValueError as exc:
        raise NotFoundError("Invalid citation ids.") from exc

    with session_scope() as session:
        stmt = (
            select(Segment)
            .join(Source, Source.id == Segment.source_id)
            .where(Segment.id.in_(wanted))
        )
        if user is not None:
            stmt = stmt.where(or_(Source.user_id == user.id, Source.user_id.is_(None)))
        rows = list(session.execute(stmt).scalars())
    return {"segments": [segment_dict(segment) for segment in rows]}


# --------------------------------------------------------------------------- answering


def _load_chat(
    chat_id: int, user_id: int | None = None
) -> tuple[str, int | None, list[ProviderMessage], int | None]:
    """Chat scope plus recent turns, for conversational context."""
    with session_scope() as session:
        chat = session.get(Chat, chat_id)
        if chat is None:
            raise NotFoundError(f"Chat {chat_id} not found.")
        if user_id is not None and chat.user_id is not None and chat.user_id != user_id:
            raise NotFoundError(f"Chat {chat_id} not found.")
        history = list(
            session.execute(
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.id.desc())
                .limit(8)
            ).scalars()
        )
        turns: list[ProviderMessage] = [
            text_message("assistant" if m.role is MessageRole.ASSISTANT else "user", m.content)
            for m in reversed(history)
        ]
        return str(chat.scope_type), chat.scope_id, turns, chat.user_id


def _store(
    chat_id: int, role: MessageRole, content: str, citations: list[int], followups: list[str]
) -> dict[str, Any]:
    with session_scope() as session:
        message = Message(
            chat_id=chat_id,
            role=role,
            content=content,
            citations=citations,
            followups=followups,
        )
        session.add(message)
        session.flush()
        chat = session.get(Chat, chat_id)
        # Name the chat after its first question, so the sidebar is scannable.
        if chat is not None and chat.title == "New chat" and role is MessageRole.USER:
            chat.title = content.strip()[:80]
        return message_dict(message)


def validate_answer(answer: str, excerpts: list[rag.Excerpt]) -> tuple[str, list[int]]:
    """Enforce the citation contract from PRD §7.5 and rigorous evidence grounding.

    Rules enforced:
    1. Empty retrieval -> explicit fallback disclaimer.
    2. Honest model abstention -> accept abstention without forcing citations.
    3. Ungrounded claims (no valid citations) -> fail closed with verified abstention.
    4. Hallucinated citation markers -> strip invalid citations with note.
    5. Multi-paragraph grounding -> a single citation does NOT validate unrelated claims.
    """
    valid_ids = {excerpt.id for excerpt in excerpts}

    cited = {int(match) for match in CITATION_RE.findall(answer)}
    valid_cited = cited & valid_ids
    hallucinated = cited - valid_ids

    # 1. Honest model abstention:
    lower_ans = answer.lower()
    has_disclaimer = any(marker in lower_ans for marker in DISCLAIMER_MARKERS)
    if has_disclaimer and not valid_cited:
        return answer, []

    if not excerpts:
        return NO_CONTEXT_FALLBACK, []

    # 2. Fail closed on unsupported assertions:
    if not valid_cited:
        log.warning(
            "model made claims without valid citations (cited=%s, valid_set=%s); rejecting unsupported answer",
            cited,
            valid_ids,
        )
        return (
            "I could not verify this claim in the provided course materials. "
            "The retrieved passages do not contain evidence supporting this statement.",
            [],
        )

    # 3. Clean up hallucinated citation markers
    has_hallucinated = bool(hallucinated)
    if has_hallucinated:
        log.info("dropping %d citation marker(s) not in retrieved set: %s", len(hallucinated), hallucinated)
        answer = CITATION_RE.sub(
            lambda m: "" if int(m.group(1)) in hallucinated else m.group(0), answer
        ).strip()

    # 4. Multi-paragraph validation:
    # A single valid citation must not be treated as proof that every unrelated claim is supported.
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
    uncited_substantive_paras = 0
    for p in paragraphs:
        p_cited = {int(m) for m in CITATION_RE.findall(p)} & valid_ids
        p_has_disclaimer = any(m in p.lower() for m in DISCLAIMER_MARKERS)
        if len(p) > 60 and not p_cited and not p_has_disclaimer and not p.startswith("#") and not p.startswith("*"):
            uncited_substantive_paras += 1

    notes: list[str] = []
    if has_hallucinated:
        notes.append("Some referenced citation markers were not found in the verified course material.")
    if uncited_substantive_paras > 0 and len(paragraphs) > 1:
        notes.append("Portions of this answer lack direct citation markers in the retrieved passages.")

    if notes:
        answer = answer + "\n\n*(Note: " + " ".join(notes) + ")*"

    return answer, sorted(valid_cited)


def assess_evidence_support(
    answer: str,
    citations: list[int],
    excerpts: list[rag.Excerpt],
) -> Literal["strong", "partial", "insufficient"]:
    """Assess evidence support status for the generated response."""
    if not citations or not excerpts:
        return "insufficient"

    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
    valid_ids = {e.id for e in excerpts}
    uncited = 0
    for p in paragraphs:
        p_cited = {int(m) for m in CITATION_RE.findall(p)} & valid_ids
        p_has_disclaimer = any(m in p.lower() for m in DISCLAIMER_MARKERS)
        if len(p) > 60 and not p_cited and not p_has_disclaimer and not p.startswith("#") and not p.startswith("*"):
            uncited += 1

    if len(citations) >= 2 and uncited == 0:
        return "strong"
    return "partial"


def _msg_role(m: Any) -> str:
    return m.get("role", "") if isinstance(m, dict) else str(getattr(m, "role", ""))


def _msg_content(m: Any) -> str:
    c = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
    if isinstance(c, list):
        return " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    return str(c or "")


async def _contextualize_query(question: str, history: list[ProviderMessage]) -> str:
    """Rewrite follow-up questions containing anaphora or elliptical references into standalone queries."""
    if not history:
        return question

    q_lower = question.lower().strip()
    words = set(re.findall(r"\b\w+\b", q_lower))
    is_followup = bool(words & FOLLOWUP_PRONOUNS) or len(words) <= 5 or q_lower.startswith(("why?", "how?", "what about", "elaborate"))

    if not is_followup:
        return question

    # Extract the last 2-3 turns for context
    recent_turns = [f"{_msg_role(m)}: {_msg_content(m)}" for m in history[-4:]]
    history_str = "\n".join(recent_turns)

    prompt = (
        "Given the following conversation history and a follow-up question, rewrite the follow-up question "
        "into a standalone search query that preserves the specific topic and entities being discussed. "
        "Output ONLY the standalone query with no explanation or punctuation around it.\n\n"
        f"Conversation History:\n{history_str}\n\n"
        f"Follow-up question: {question}\n\n"
        "Standalone query:"
    )

    try:
        rewritten = await gateway.complete_text(
            "contextualize query",
            [text_message("user", prompt)],
            task_class="fast",
            temperature=0.0,
            max_tokens=60,
        )
        cleaned = rewritten.strip().strip('"').strip("'")
        if cleaned and len(cleaned) > 3:
            log.info("Contextualized query from '%s' to '%s'", question, cleaned)
            return cleaned
    except Exception as exc:
        log.debug("Query contextualization LLM call skipped/failed: %s", exc)

    # Fallback heuristic: find the latest user message topic
    for m in reversed(history):
        if _msg_role(m) == "user" and _msg_content(m).strip():
            fallback_query = f"{_msg_content(m).strip()[:60]} {question}"
            log.info("Heuristic contextualized query fallback: '%s'", fallback_query)
            return fallback_query

    return question


async def _followups(query: str, answer: str) -> list[str]:
    try:
        result = await gateway.complete_structured(
            "chat followups",
            [
                text_message(
                    "user", prompts.render("chat_followups", query=query, answer=answer, count=3)
                )
            ],
            FollowupQuestions,
            task_class="fast",
            temperature=0.6,
            max_tokens=400,
        )
        return [q.strip() for q in result.questions if q.strip()][:3]
    except Exception as exc:
        log.debug("follow-up generation failed: %s", exc)
        return []


async def _build_prompt(
    chat_id: int, question: str, user_id: int | None = None
) -> tuple[list[ProviderMessage], list[rag.Excerpt], str]:
    scope_type, scope_id, history, chat_user_id = await run_db(_load_chat, chat_id, user_id)
    effective_user_id = user_id if user_id is not None else chat_user_id

    # Contextualize follow-up question for retrieval
    retrieval_query = await _contextualize_query(question, history)

    excerpts = await rag.retrieve(
        retrieval_query,
        scope_type=scope_type,
        scope_id=scope_id,
        user_id=effective_user_id,
    )

    # If scoped search yields 0 excerpts (e.g. asking about SQL in DS Lab practicals),
    # gracefully fall back to searching the student's wider global library so they get answered!
    if not excerpts and scope_type != "global":
        wider = await rag.retrieve(
            retrieval_query,
            scope_type="global",
            scope_id=None,
            user_id=effective_user_id,
        )
        if wider:
            log.info("Scoped search yielded 0 results; found %d in wider library", len(wider))
            excerpts = wider

    # Compute deterministic user source inventory manifest
    manifest_scope_type = scope_type.value if hasattr(scope_type, "value") else str(scope_type)
    manifest = await run_db(get_user_source_manifest, effective_user_id, manifest_scope_type, scope_id)
    manifest_note = render_manifest_note(manifest)

    system = prompts.render(
        "chat_system",
        excerpts=[
            {
                "id": excerpt.id,
                "text": excerpt.text,
                "source_title": excerpt.source_title,
                "timestamp": excerpt.timestamp,
            }
            for excerpt in excerpts
        ],
        scope_description=rag.scope_description(scope_type, scope_id),
        manifest_note=manifest_note,
    )
    messages: list[ProviderMessage] = [text_message("system", system)]
    messages.extend(history)
    messages.append(text_message("user", question))
    return messages, excerpts, retrieval_query


@router.post("/{chat_id}/message")
async def send_message(
    chat_id: int, payload: SendMessageRequest, user: User | None = Depends(get_optional_user)
) -> dict[str, Any]:
    """Non-streaming answer. The WebSocket route is preferred, this is the fallback."""
    question = payload.content.strip()
    user_id = user.id if user else None
    await run_db(_store, chat_id, MessageRole.USER, question, [], [])

    messages, excerpts, retrieval_query = await _build_prompt(chat_id, question, user_id=user_id)
    raw = await gateway.complete_text("chat", messages, temperature=0.3, max_tokens=2000)
    answer, citations = validate_answer(raw, excerpts)
    evidence_support = assess_evidence_support(answer, citations, excerpts)
    followups = await _followups(question, answer) if excerpts else []

    stored = await run_db(_store, chat_id, MessageRole.ASSISTANT, answer, citations, followups)
    stored["excerpts"] = [excerpt.to_dict() for excerpt in excerpts]
    stored["evidence_support"] = evidence_support
    stored["retrieval_query"] = retrieval_query
    try:
        resolved = gateway.registry.get_llm("standard")
        stored["provider"] = resolved.provider_name
        stored["model"] = resolved.model
        stored["is_mock"] = (resolved.provider_name == "mock")
    except Exception:
        stored["is_mock"] = False
    return stored


@router.websocket("/ws/{chat_id}")
async def chat_socket(websocket: WebSocket, chat_id: int) -> None:
    """Streaming chat with query contextualization and evidence grounding."""
    subprotocol = next((p for p in websocket.scope.get("subprotocols", []) if p.startswith("bearer.")), None)
    await websocket.accept(subprotocol=subprotocol)

    # Resolve optional user identity from query param or auth header
    user = None
    token = websocket.query_params.get("token")
    if not token and "authorization" in websocket.headers:
        auth_h = websocket.headers.get("authorization", "")
        if auth_h.startswith("Bearer "):
            token = auth_h[7:].strip()
    if token:
        try:
            user = get_optional_user(token)
        except Exception:
            user = None

    user_id = user.id if user else None

    try:
        while True:
            payload = await websocket.receive_json()
            question = str(payload.get("content") or "").strip()
            if not question:
                await websocket.send_json({"type": "error", "message": "Empty message."})
                continue

            try:
                await run_db(_store, chat_id, MessageRole.USER, question, [], [])
                messages, excerpts, retrieval_query = await _build_prompt(chat_id, question, user_id=user_id)

                await websocket.send_json(
                    {
                        "type": "excerpts",
                        "excerpts": [excerpt.to_dict() for excerpt in excerpts],
                        "retrieval_query": retrieval_query,
                    }
                )

                collected: list[str] = []
                client_disconnected = False
                try:
                    async for delta in gateway.stream_text(
                        "chat", messages, temperature=0.3, max_tokens=2000
                    ):
                        collected.append(delta)
                        if not client_disconnected:
                            try:
                                await websocket.send_json({"type": "token", "text": delta})
                            except Exception:
                                client_disconnected = True
                except Exception as stream_err:
                    log.warning("Stream loop error: %s", stream_err)

                raw_output = "".join(collected).strip()
                if not raw_output:
                    try:
                        raw_output = await gateway.complete_text("chat", messages, temperature=0.3, max_tokens=2000)
                    except Exception as comp_err:
                        raw_output = NO_CONTEXT_FALLBACK

                answer, citations = validate_answer(raw_output, excerpts)
                evidence_support = assess_evidence_support(answer, citations, excerpts)
                followups = await _followups(question, answer) if excerpts else []
                stored = await run_db(
                    _store, chat_id, MessageRole.ASSISTANT, answer, citations, followups
                )
                is_mock_provider = False
                provider_name = ""
                model_name = ""
                try:
                    resolved = gateway.registry.get_llm("standard")
                    provider_name = resolved.provider_name
                    model_name = resolved.model
                    is_mock_provider = (resolved.provider_name == "mock")
                except Exception:
                    pass

                if not client_disconnected:
                    try:
                        await websocket.send_json(
                            {
                                "type": "done",
                                "message": stored,
                                "citations": citations,
                                "evidence_support": evidence_support,
                                "followups": followups,
                                "corrected": answer != raw_output,
                                "provider": provider_name,
                                "model": model_name,
                                "is_mock": is_mock_provider,
                            }
                        )
                    except Exception:
                        pass
            except QuicklearnError as exc:
                await websocket.send_json({"type": "error", "message": exc.message})
            except Exception as exc:
                log.exception("chat stream failed: %s", exc)
                await websocket.send_json(
                    {"type": "error", "message": "An error occurred while generating the response. Please try again."}
                )
    except WebSocketDisconnect:
        return
    except Exception:  # pragma: no cover - transport-level failure
        log.debug("chat socket closed unexpectedly", exc_info=True)
