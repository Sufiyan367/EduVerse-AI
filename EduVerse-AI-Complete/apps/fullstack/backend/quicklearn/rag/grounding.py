"""Quote normalization and evidence grounding engine for EduVerse AI.

Provides resilient citation and quote verification adapted from HKUDS/DeepTutor,
handling real-world document artifacts (line-break hyphens, margin numbers, ligatures,
Unicode quirks, collapsed whitespace) while preserving exact original text provenance,
page numbers, bounding boxes, and segment IDs.

Key invariant:
Normalized text is used ONLY for candidate matching. The original extracted text
and coordinate bounding boxes are never mutated or discarded.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Sequence

# Margin numbers regex:
# Matches isolated lines consisting strictly of 1 to 4 digits with optional surrounding whitespace.
# Crucially, this does NOT match:
# - Numbered lists (e.g. "1. Introduction", "2) Methods")
# - Equations (e.g. "x = 2 * y + 3")
# - Section / clause references (e.g. "Section 4.1", "Article 12")
# - Footnote lines with content (e.g. "1 See Smith et al., 2020")
_MARGIN_NUMBER_RE = re.compile(r"(?:\A|\n)[ \t]*\d{1,4}[ \t]*(?=\n|\Z)")

# Line-break hyphenation:
# Matches a word interrupted by a hyphen, soft hyphen (\u00ad), or Unicode hyphen (\u2010, \u2011)
# immediately followed by a newline and optional whitespace, followed by word characters.
# E.g. "concur-\nrency" -> "concurrency", "trans-\n action" -> "transaction"
_LINE_BREAK_HYPHEN_RE = re.compile(r"(\w+)[\-\u00ad\u2010\u2011]\s*\n\s*(\w+)")

# Whitespace normalization
_SPACING_RE = re.compile(r"\s+")


# Spacing & dash/quote canonical translation table
_PUNCT_TRANS = str.maketrans({
    "“": '"',
    "”": '"',
    "„": '"',
    "«": '"',
    "»": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "—": "-",
    "–": "-",
    "−": "-",
})


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    """The result of verifying an evidence quote against document segments."""

    matched: bool
    source_id: int | None = None
    page_no: int | None = None
    segment_id: int | None = None
    original_quote: str = ""
    matched_span: tuple[int, int] | None = None  # (start_idx, end_idx) in the original segment text
    confidence: float = 0.0
    matched_segment_text: str = ""
    notes: str = ""


def normalize_for_matching(text: str) -> str:
    """Produce a canonical string for fuzzy evidence matching.

    Performs:
    1. Unicode NFKC normalization (canonical decomposition + compatibility composition),
       which resolves ligatures (fi -> f i, fl -> f l) and smart quotes/dashes.
    2. Strips standalone margin line numbers that appear on lines by themselves.
    3. Rejoins words broken across line wraps by hyphens.
    4. Collapses multi-line and multi-space whitespace into single spaces.
    5. Case-folds for case-insensitive matching.
    """
    if not text:
        return ""

    # Step 1: Unicode NFKC normalization and quote/dash translation
    nfkc = unicodedata.normalize("NFKC", text).translate(_PUNCT_TRANS)

    # Step 2: Strip isolated margin line numbers (only digit-only lines)
    without_margin_numbers = _MARGIN_NUMBER_RE.sub("\n", nfkc)

    # Step 3: De-hyphenate wrapped words across line breaks
    dehyphenated = _LINE_BREAK_HYPHEN_RE.sub(r"\1\2", without_margin_numbers)

    # Step 4: Collapse whitespace into single spaces
    collapsed = _SPACING_RE.sub(" ", dehyphenated).strip()

    # Step 5: Case fold
    return collapsed.casefold()


def normalized_with_map(value: str) -> tuple[str, list[int]]:
    """Produce normalized matching text while retaining the original character offset for every char.

    Returns:
        (normalized_str, position_map)
        where position_map[i] is the index of normalized_str[i] in the original `value`.
    """
    if not value:
        return "", []

    # First perform Unicode NFKC character by character / token
    # To maintain reliable indices, we track positions through transformation
    normalized_chars: list[str] = []
    source_positions: list[int] = []

    # Apply NFKC decomposition/composition mapping
    # We step through characters, normalizing whitespace and soft hyphens
    i = 0
    n = len(value)
    
    # Check for margin numbers or soft hyphens as we go
    while i < n:
        char = value[i]

        # Check for soft hyphen or break hyphen at newline: word-\nword
        if char in "-\u00ad\u2010\u2011" and i + 1 < n:
            # Look ahead for newline and following word
            rest = value[i + 1:]
            nl_match = re.match(r"^\s*\n\s*(\w)", rest)
            if nl_match and normalized_chars and normalized_chars[-1].isalnum():
                # Skip the hyphen and the newline whitespace to rejoin the word
                skip_len = len(rest) - len(rest.lstrip())
                # Advance i past the hyphen and whitespace up to the next word char
                # Find index of the next word char
                next_char_offset = 1 + nl_match.start(1)
                i += next_char_offset
                continue

        # Handle whitespace collapsing
        if char.isspace():
            if normalized_chars and normalized_chars[-1] != " ":
                normalized_chars.append(" ")
                source_positions.append(i)
            i += 1
            continue

        # Handle ligatures / NFKC and smart quote / dash translation on individual char
        norm_char = unicodedata.normalize("NFKC", char).translate(_PUNCT_TRANS).casefold()
        for nc in norm_char:
            normalized_chars.append(nc)
            source_positions.append(i)
        i += 1

    # Strip trailing space
    if normalized_chars and normalized_chars[-1] == " ":
        normalized_chars.pop()
        source_positions.pop()

    return "".join(normalized_chars), source_positions


def find_evidence_span(original_text: str, quote: str) -> tuple[int, int] | None:
    """Find the exact start and end character indices of `quote` in `original_text`.

    Returns (start, end) tuple referencing character offsets in `original_text`, or None.
    """
    if not original_text or not quote:
        return None

    # Fast path: exact substring match
    exact = original_text.find(quote)
    if exact >= 0:
        return exact, exact + len(quote)

    # Fast path 2: case-insensitive exact substring match
    exact_lower = original_text.lower().find(quote.lower())
    if exact_lower >= 0:
        return exact_lower, exact_lower + len(quote)

    # Robust path: normalized matching with character map
    norm_text, positions = normalized_with_map(original_text)
    norm_quote = normalize_for_matching(quote)

    if not norm_quote or not norm_text:
        return None

    found = norm_text.find(norm_quote)
    if found >= 0 and (found + len(norm_quote) <= len(positions)):
        start = positions[found]
        end = positions[found + len(norm_quote) - 1] + 1
        return start, end

    # Fallback: check if the first 80% or key words of the quote match
    # (handles slight punctuation differences at quote boundaries)
    clean_quote = norm_quote.strip(" \t\n\r\"'.,;:!?()[]{}")
    if len(clean_quote) >= 12:
        found_clean = norm_text.find(clean_quote)
        if found_clean >= 0 and (found_clean + len(clean_quote) <= len(positions)):
            start = positions[found_clean]
            end = positions[found_clean + len(clean_quote) - 1] + 1
            return start, end

    return None


def verify_evidence_in_segments(
    quote: str,
    segments: Sequence[Any],
) -> EvidenceMatch:
    """Verify an evidence quote against a sequence of candidate Segments.

    Args:
        quote: The evidence phrase or sentence generated by the LLM.
        segments: Iterable of Segment ORM objects or dictionaries with 'text', 'id',
                  'source_id', 'page_no'.

    Returns:
        EvidenceMatch with verification status and preserved provenance.
    """
    clean_quote = quote.strip().strip("\"'“”")
    if not clean_quote or len(clean_quote) < 4:
        return EvidenceMatch(
            matched=False,
            original_quote=quote,
            notes="Quote is empty or shorter than 4 characters.",
        )

    # Step 1: Scan individual segments
    for seg in segments:
        text = getattr(seg, "text", None)
        if text is None and isinstance(seg, dict):
            text = seg.get("text", "")
        if not text:
            continue

        span = find_evidence_span(text, clean_quote)
        if span is not None:
            seg_id = getattr(seg, "id", None) or (seg.get("id") if isinstance(seg, dict) else None)
            source_id = getattr(seg, "source_id", None) or (
                seg.get("source_id") if isinstance(seg, dict) else None
            )
            page_no = getattr(seg, "page_no", None) or (
                seg.get("page_no") if isinstance(seg, dict) else None
            )

            return EvidenceMatch(
                matched=True,
                source_id=source_id,
                page_no=page_no,
                segment_id=seg_id,
                original_quote=clean_quote,
                matched_span=span,
                confidence=1.0,
                matched_segment_text=text,
                notes="Matched within single segment.",
            )

    # Step 2: Cross-segment boundary search (in case quote crosses consecutive segments)
    sorted_segments = list(segments)
    for i in range(len(sorted_segments) - 1):
        s1 = sorted_segments[i]
        s2 = sorted_segments[i + 1]

        # Only join segments from the same source
        src1 = getattr(s1, "source_id", None) or (s1.get("source_id") if isinstance(s1, dict) else None)
        src2 = getattr(s2, "source_id", None) or (s2.get("source_id") if isinstance(s2, dict) else None)
        if src1 != src2:
            continue

        text1 = getattr(s1, "text", "") or (s1.get("text", "") if isinstance(s1, dict) else "")
        text2 = getattr(s2, "text", "") or (s2.get("text", "") if isinstance(s2, dict) else "")
        joined_text = f"{text1}\n{text2}"

        span = find_evidence_span(joined_text, clean_quote)
        if span is not None:
            seg_id = getattr(s1, "id", None) or (s1.get("id") if isinstance(s1, dict) else None)
            page_no = getattr(s1, "page_no", None) or (
                s1.get("page_no") if isinstance(s1, dict) else None
            )
            return EvidenceMatch(
                matched=True,
                source_id=src1,
                page_no=page_no,
                segment_id=seg_id,
                original_quote=clean_quote,
                matched_span=span,
                confidence=0.95,
                matched_segment_text=joined_text,
                notes="Matched across segment boundary.",
            )

    return EvidenceMatch(
        matched=False,
        original_quote=clean_quote,
        notes="Quote not found in verified document segments.",
    )
