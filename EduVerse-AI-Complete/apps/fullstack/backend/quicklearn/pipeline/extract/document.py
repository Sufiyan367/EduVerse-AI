"""Document extraction: PDF, DOCX, PPTX, plain text.

PDF uses PyMuPDF for the text layer — fast, and crucially no ML dependency, which is what keeps
the base image near 1.5 GB (PRD §6.3). When the text layer is too sparse to be real the page is
a scan, and we rasterise and hand it to a vision model instead of returning a blank note.

DOCX and PPTX preserve heading hierarchy and slide boundaries respectively, because those are
the structural cues the outline pass uses to find section breaks.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from pathlib import Path
from typing import Any, Sequence

from ...errors import PipelineError
from ...providers.base import ImagePart, Message
from .base import ExtractResult, RawUnit

log = logging.getLogger(__name__)

#: Below this many characters per page, assume the text layer is decorative and the real
#: content is an image. Chosen to sit well under a sparse slide but above a page number alone.
SCAN_THRESHOLD_CHARS = 120
#: Rasterisation scale for the OCR fallback. 2x gives ~150 DPI, enough for a vision model
#: without producing images too large to send.
RASTER_SCALE = 2.0
MAX_OCR_PAGES = 40


def _box_overlaps(b1: Sequence[float], b2: Sequence[float], threshold: float = 0.4) -> bool:
    """Check if block b1 significantly overlaps b2 (e.g. text inside table)."""
    x_left = max(b1[0], b2[0])
    y_top = max(b1[1], b2[1])
    x_right = min(b1[2], b2[2])
    y_bottom = min(b1[3], b2[3])
    if x_right <= x_left or y_bottom <= y_top:
        return False
    intersection = (x_right - x_left) * (y_bottom - y_top)
    b1_area = (b1[2] - b1[0]) * (b1[3] - b1[1])
    return (b1_area > 0) and ((intersection / b1_area) >= threshold)


def _is_noise_header_footer(text: str, bbox: Sequence[float], page_height: float) -> bool:
    """Detect running headers/footers and isolated page numbers."""
    # Only evaluate blocks in extreme margin zones (< 38pt from top or bottom)
    in_top_margin = bbox[3] <= 38.0
    in_bottom_margin = bbox[1] >= (page_height - 38.0)
    if not (in_top_margin or in_bottom_margin):
        return False

    cleaned = text.strip()
    # Check page number patterns: "1", "Page 1 of 10", "- 1 -", "p. 4"
    if re.match(r"^(page\s+)?\d+(\s+(of|/)\s+\d+)?$", cleaned, re.IGNORECASE):
        return True
    if re.match(r"^[-–—]\s*\d+\s*[-–—]$", cleaned):
        return True
    if cleaned.isdigit():
        return True
    return False


def _sort_page_blocks(blocks: list[Any], page_width: float) -> list[Any]:
    """Sort blocks preserving reading order in both single-column and multi-column pages."""
    text_blocks = [b for b in blocks if len(b) > 4 and str(b[4]).strip()]
    if len(text_blocks) <= 1:
        return text_blocks

    midpoint = page_width / 2.0
    left_blocks = []
    right_blocks = []
    full_blocks = []

    for b in text_blocks:
        x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        block_width = x1 - x0
        is_full = block_width > (page_width * 0.50)
        if is_full:
            full_blocks.append(b)
        elif x1 <= (midpoint + 0.1 * page_width):
            left_blocks.append(b)
        elif x0 >= (midpoint - 0.1 * page_width):
            right_blocks.append(b)
        else:
            center_x = (x0 + x1) / 2.0
            if center_x < midpoint:
                left_blocks.append(b)
            else:
                right_blocks.append(b)

    is_two_column = len(left_blocks) >= 2 and len(right_blocks) >= 2
    if not is_two_column:
        return sorted(text_blocks, key=lambda b: (round(float(b[1]), 1), round(float(b[0]), 1)))

    min_col_y = min([float(b[1]) for b in left_blocks + right_blocks])
    max_col_y = max([float(b[3]) for b in left_blocks + right_blocks])

    top_full = [b for b in full_blocks if float(b[3]) <= min_col_y]
    bottom_full = [b for b in full_blocks if float(b[1]) >= max_col_y]
    mid_full = [b for b in full_blocks if b not in top_full and b not in bottom_full]

    sorted_top = sorted(top_full, key=lambda b: float(b[1]))
    sorted_left = sorted(left_blocks, key=lambda b: float(b[1]))
    sorted_right = sorted(right_blocks, key=lambda b: float(b[1]))
    sorted_mid = sorted(mid_full, key=lambda b: float(b[1]))
    sorted_bottom = sorted(bottom_full, key=lambda b: float(b[1]))

    return sorted_top + sorted_left + sorted_right + sorted_mid + sorted_bottom


def _extract_pdf_sync(path: Path) -> tuple[list[RawUnit], int, list[int]]:
    """Text layer per page. Returns units, page count, and pages that look scanned."""
    import fitz

    units: list[RawUnit] = []
    scanned: list[int] = []

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise PipelineError(f"'{path.name}' is corrupt or cannot be opened as a valid PDF.") from exc

    with doc:
        if doc.is_encrypted or doc.needs_pass:
            raise PipelineError(f"'{path.name}' is password-protected and cannot be read without a password.")

        page_count = doc.page_count
        if page_count == 0:
            raise PipelineError(f"'{path.name}' contains no readable pages.")

        for page_index in range(page_count):
            page = doc.load_page(page_index)
            page_no = page_index + 1
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)

            # 1. Detect and extract structured tables
            table_bboxes: list[list[float]] = []
            table_units: list[RawUnit] = []
            try:
                table_finder = page.find_tables()
                if table_finder and table_finder.tables:
                    for tab in table_finder.tables:
                        md = tab.to_markdown()
                        if md and md.strip():
                            tbbox = [float(tab.bbox[0]), float(tab.bbox[1]), float(tab.bbox[2]), float(tab.bbox[3])]
                            table_bboxes.append(tbbox)
                            table_units.append(RawUnit(text=md.strip(), page_no=page_no, bbox=tbbox))
            except Exception as exc:
                log.debug("find_tables on page %d: %s", page_no, exc)

            # 2. Extract and filter text blocks
            blocks = page.get_text("blocks")
            sorted_blocks = _sort_page_blocks(blocks, page_width)
            page_chars = 0
            page_text_units: list[RawUnit] = []

            for block in sorted_blocks:
                text = str(block[4]).strip() if len(block) > 4 else ""
                if not text:
                    continue
                bbox = [float(block[0]), float(block[1]), float(block[2]), float(block[3])]

                # Filter running header/footer noise (e.g. standalone page numbers)
                if _is_noise_header_footer(text, bbox, page_height):
                    continue

                # Skip raw text blocks that overlap extracted tables to prevent duplicate jumbled tables
                if any(_box_overlaps(bbox, tbbox) for tbbox in table_bboxes):
                    continue

                # Merge broken hyphenated words across line wraps
                text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
                page_chars += len(text)
                page_text_units.append(
                    RawUnit(
                        text=text,
                        page_no=page_no,
                        bbox=bbox,
                    )
                )

            # Insert table units into page units while preserving multi-column block reading order
            if not table_units:
                combined_page_units = page_text_units
            else:
                combined_page_units = list(page_text_units)
                for tab in table_units:
                    tab_y = tab.bbox[1] if tab.bbox else 0.0
                    insert_idx = len(combined_page_units)
                    for i, u in enumerate(combined_page_units):
                        if u.bbox and u.bbox[1] > tab_y:
                            insert_idx = i
                            break
                    combined_page_units.insert(insert_idx, tab)
            units.extend(combined_page_units)

            # 3. Distinguish truly blank pages (0 chars, 0 images, 0 drawings) from sparse/scanned pages
            if page_chars < SCAN_THRESHOLD_CHARS and not table_units:
                num_images = len(page.get_images())
                num_drawings = len(page.get_drawings())
                if page_chars == 0 and num_images == 0 and num_drawings == 0:
                    log.debug("Page %d of '%s' is an empty/blank page", page_no, path.name)
                else:
                    scanned.append(page_no)

    return units, page_count, scanned


def _rasterise_pages_sync(path: Path, pages: list[int]) -> list[tuple[int, bytes]]:
    import fitz

    images: list[tuple[int, bytes]] = []
    with fitz.open(str(path)) as doc:
        for page_no in pages:
            page = doc.load_page(page_no - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(RASTER_SCALE, RASTER_SCALE))
            images.append((page_no, pixmap.tobytes("png")))
    return images


async def extract_pdf(
    path: Path, *, source_id: int | None = None, job_id: int | None = None
) -> ExtractResult:
    units, page_count, scanned = await asyncio.to_thread(_extract_pdf_sync, path)
    unreadable_pages: list[int] = []

    # Identify sparse/image-based pages individually and OCR eligible pages even in mixed PDFs
    if scanned:
        log.info(
            "%s identified %d sparse/scanned page(s) out of %d: %s",
            path.name,
            len(scanned),
            page_count,
            scanned,
        )
        eligible_pages = scanned[:MAX_OCR_PAGES]
        ocr_units = await _ocr_pages(path, eligible_pages, source_id, job_id)
        if ocr_units:
            ocred_pages = {u.page_no for u in ocr_units if u.page_no is not None}
            # Keep selectable text from text-bearing pages, replace sparse pages with OCR output
            units = [u for u in units if u.page_no not in ocred_pages] + ocr_units
            units.sort(key=lambda u: u.page_no or 0)
            unreadable_pages = [p for p in scanned if p not in ocred_pages]
        else:
            unreadable_pages = list(scanned)

    if unreadable_pages:
        log.warning(
            "Document '%s' contains %d page(s) that could not be OCR-processed: %s",
            path.name,
            len(unreadable_pages),
            unreadable_pages,
        )

    if not units:
        raise PipelineError(
            f"No readable text found in '{path.name}'. Scanned pages ({unreadable_pages}) require "
            "a configured vision-capable model (Google Gemini, OpenAI, or Anthropic) in Settings → Model routing."
        )

    return ExtractResult(
        units=units,
        page_count=page_count,
        provider="pymupdf",
        raw={"scanned_pages": scanned, "unreadable_pages": unreadable_pages},
    )


async def _ocr_pages(
    path: Path, pages: list[int], source_id: int | None, job_id: int | None
) -> list[RawUnit]:
    """Rasterise and transcribe pages with a vision model."""
    from ... import prompts
    from ...providers import gateway, registry

    try:
        resolved = registry.get_llm("standard")
    except Exception as exc:
        log.warning("no LLM configured for the scanned-PDF fallback: %s", exc)
        return []

    if resolved.provider_name == "mock" or not resolved.provider.supports_vision:
        log.warning(
            "model %s (%s) cannot perform vision OCR; scanned pages %s require a real vision model",
            resolved.model,
            resolved.provider_name,
            pages,
        )
        return []

    images = await asyncio.to_thread(_rasterise_pages_sync, path, pages)
    instruction = prompts.render("image_describe", hint=f"Page from {path.name}")
    semaphore = asyncio.Semaphore(2)

    async def run(page_no: int, data: bytes) -> RawUnit | None:
        image_part: ImagePart = {
            "type": "image",
            "media_type": "image/png",
            "data": base64.b64encode(data).decode(),
        }
        message: Message = {
            "role": "user",
            "content": [{"type": "text", "text": instruction}, image_part],
        }
        async with semaphore:
            try:
                text = await gateway.complete_text(
                    "ocr_page", [message], source_id=source_id, job_id=job_id, max_tokens=2048
                )
            except Exception as exc:  # a failed page should not fail the whole document
                log.warning("OCR failed on page %d: %s", page_no, exc)
                return None
        return RawUnit(text=text.strip(), page_no=page_no) if text.strip() else None

    # Process scanned pages in batches of 4 to manage memory and API quotas
    results = []
    batch_size = 4
    for i in range(0, len(images), batch_size):
        batch = images[i : i + batch_size]
        batch_results = await asyncio.gather(*(run(p, d) for p, d in batch))
        results.extend(batch_results)
    return [unit for unit in results if unit is not None]


def _extract_docx_sync(path: Path) -> list[RawUnit]:
    from docx import Document

    document = Document(str(path))
    units: list[RawUnit] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name or "").lower() if paragraph.style else ""
        # Markdown-mark headings so the outline pass can see the author's own structure
        # instead of having to infer it from prose.
        if style.startswith("heading"):
            level = "".join(c for c in style if c.isdigit()) or "1"
            text = f"{'#' * min(6, int(level))} {text}"
        units.append(RawUnit(text=text))

    for table in document.tables:
        rows = [
            " | ".join(cell.text.strip() for cell in row.cells)
            for row in table.rows
            if any(cell.text.strip() for cell in row.cells)
        ]
        if rows:
            units.append(RawUnit(text="\n".join(rows)))
    return units


async def extract_docx(path: Path) -> ExtractResult:
    units = await asyncio.to_thread(_extract_docx_sync, path)
    if not units:
        raise PipelineError(f"'{path.name}' contains no readable text.")
    return ExtractResult(units=units, provider="python-docx")


def _extract_pptx_sync(path: Path) -> tuple[list[RawUnit], int]:
    from pptx import Presentation

    presentation = Presentation(str(path))
    units: list[RawUnit] = []
    slide_count = 0

    for index, slide in enumerate(presentation.slides, start=1):
        slide_count = index
        pieces: list[str] = []
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            text = shape.text_frame.text.strip()
            if text:
                pieces.append(text)

        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()

        if not pieces and not notes:
            continue

        body = "\n".join(pieces)
        if notes:
            # Speaker notes usually carry the actual explanation, so they are content, not
            # metadata — but they are labelled so the model knows they were not on screen.
            body = f"{body}\n\n[Speaker notes] {notes}".strip()

        # page_no carries the slide number, which is what document anchoring displays.
        units.append(RawUnit(text=f"## Slide {index}\n{body}", page_no=index))

    return units, slide_count


async def extract_pptx(path: Path) -> ExtractResult:
    units, slides = await asyncio.to_thread(_extract_pptx_sync, path)
    if not units:
        raise PipelineError(f"'{path.name}' contains no readable text.")
    return ExtractResult(units=units, page_count=slides, provider="python-pptx")


def extract_text(content: str) -> ExtractResult:
    """Pasted or plain-text input — no decoding needed, split on blank lines."""
    blocks = [block.strip() for block in content.split("\n\n")]
    units = [RawUnit(text=block) for block in blocks if block]
    if not units and content.strip():
        units = [RawUnit(text=content.strip())]
    return ExtractResult(units=units, provider="text")
