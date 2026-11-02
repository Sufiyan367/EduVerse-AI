"""Comprehensive automated verification of the PDF intelligence pipeline across 10 PDF types.

Tests:
1. Normal selectable text PDF
2. Long multi-page textbook PDF (10+ pages)
3. Multi-column academic paper (2-column layout with headers/footers)
4. PDF with structured tables (table preservation via find_tables)
5. PDF with code and equations
6. Scanned image-only PDF (0 text characters)
7. Mixed digital and scanned pages (preserves readable text)
8. Blank-page PDF
9. Corrupt PDF
10. Password-protected PDF
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
import fitz
from PIL import Image, ImageDraw

from quicklearn.errors import PipelineError
from quicklearn.pipeline.extract.document import extract_pdf, _extract_pdf_sync
from quicklearn.pipeline.segment import build_segments
from quicklearn.db.search import escape_query


@pytest.fixture
def pdf_fixtures_dir(tmp_path: Path) -> Path:
    out = tmp_path / "pdf_fixtures"
    out.mkdir(parents=True, exist_ok=True)
    return out


def create_scanned_page_image(text: str = "Scanned Lecture Note") -> bytes:
    img = Image.new("RGB", (600, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 100), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Normal selectable text
# ---------------------------------------------------------------------------
def test_pdf_01_normal_selectable_text(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "01_normal_text.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Chapter 1: Distributed Systems Overview", fontsize=16)
    page.insert_text(
        (72, 120),
        "A distributed system is a collection of autonomous computing entities that communicate "
        "over a network to achieve a common goal. Each node runs independent processes.",
        fontsize=11,
    )
    doc.save(str(path))
    doc.close()

    units, page_count, scanned = _extract_pdf_sync(path)
    assert page_count == 1
    assert scanned == []
    assert len(units) >= 2
    full_text = " ".join(u.text for u in units)
    assert "Distributed Systems Overview" in full_text
    assert "autonomous computing entities" in full_text


# ---------------------------------------------------------------------------
# 2. Long multi-page text
# ---------------------------------------------------------------------------
def test_pdf_02_long_textbook(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "02_long_textbook.pdf"
    doc = fitz.open()
    for i in range(1, 13):
        page = doc.new_page(width=612, height=792)
        # Add running header and footer to test noise filtering
        page.insert_text((72, 25), "Database Systems Internals — Draft", fontsize=8)
        page.insert_text((280, 770), f"Page {i} of 12", fontsize=8)
        page.insert_text((72, 100), f"Section {i}: Transaction Management Topic {i}", fontsize=14)
        page.insert_text(
            (72, 140),
            f"The write-ahead logging (WAL) protocol dictates that log records must reach stable storage "
            f"before the corresponding data page is flushed to disk. Detailed in phase {i}.",
            fontsize=11,
        )
    doc.save(str(path))
    doc.close()

    units, page_count, scanned = _extract_pdf_sync(path)
    assert page_count == 12
    assert scanned == []
    # Verify standalone page numbers were stripped from units
    for u in units:
        assert not u.text.strip().lower().startswith("page ")
    # Verify content across pages is captured
    all_pages = {u.page_no for u in units}
    assert len(all_pages) == 12


# ---------------------------------------------------------------------------
# 3. Multi-column academic paper
# ---------------------------------------------------------------------------
def test_pdf_03_multicolumn_academic(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "03_multicolumn.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Full width title at top
    page.insert_text((72, 72), "Scalable Consensus in Asynchronous Networks", fontsize=16)
    # Left column text (x: 72 to 270)
    page.insert_text((72, 150), "Left column paragraph 1: Introduction to leader election.", fontsize=10)
    page.insert_text((72, 250), "Left column paragraph 2: Safety guarantees under partitions.", fontsize=10)
    # Right column text (x: 340 to 540)
    page.insert_text((340, 150), "Right column paragraph 1: Evaluation methodology and cluster setup.", fontsize=10)
    page.insert_text((340, 250), "Right column paragraph 2: Throughput results show linear scaling.", fontsize=10)
    # Full width footer/conclusion at bottom
    page.insert_text((72, 700), "Conclusion: The protocol achieves consensus in optimal round trips.", fontsize=11)
    doc.save(str(path))
    doc.close()

    units, page_count, scanned = _extract_pdf_sync(path)
    texts = [u.text for u in units]
    # Verify reading order: Title -> Left Column 1 -> Left Column 2 -> Right Column 1 -> Right Column 2 -> Conclusion
    title_idx = next(i for i, t in enumerate(texts) if "Scalable Consensus" in t)
    left1_idx = next(i for i, t in enumerate(texts) if "Left column paragraph 1" in t)
    left2_idx = next(i for i, t in enumerate(texts) if "Left column paragraph 2" in t)
    right1_idx = next(i for i, t in enumerate(texts) if "Right column paragraph 1" in t)
    right2_idx = next(i for i, t in enumerate(texts) if "Right column paragraph 2" in t)
    concl_idx = next(i for i, t in enumerate(texts) if "Conclusion" in t)

    assert title_idx < left1_idx < left2_idx < right1_idx < right2_idx < concl_idx


# ---------------------------------------------------------------------------
# 4. Tables preservation
# ---------------------------------------------------------------------------
def test_pdf_04_tables_preservation(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "04_tables.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "System Performance Metrics", fontsize=14)

    # Draw a table with lines so PyMuPDF find_tables() recognizes it
    rect = fitz.Rect(72, 150, 540, 270)
    # Outer box
    page.draw_rect(rect)
    # Horizontal grid lines
    page.draw_line(fitz.Point(72, 180), fitz.Point(540, 180))
    page.draw_line(fitz.Point(72, 210), fitz.Point(540, 210))
    page.draw_line(fitz.Point(72, 240), fitz.Point(540, 240))
    # Vertical grid lines
    page.draw_line(fitz.Point(220, 150), fitz.Point(220, 270))
    page.draw_line(fitz.Point(380, 150), fitz.Point(380, 270))

    # Cell texts
    page.insert_text((80, 170), "Service Component", fontsize=9)
    page.insert_text((230, 170), "P99 Latency (ms)", fontsize=9)
    page.insert_text((390, 170), "Throughput (req/s)", fontsize=9)

    page.insert_text((80, 200), "Auth Gateway", fontsize=9)
    page.insert_text((230, 200), "12.4", fontsize=9)
    page.insert_text((390, 200), "45000", fontsize=9)

    page.insert_text((80, 230), "RAG Search", fontsize=9)
    page.insert_text((230, 230), "85.2", fontsize=9)
    page.insert_text((390, 230), "3200", fontsize=9)

    page.insert_text((80, 260), "Vector Index", fontsize=9)
    page.insert_text((230, 260), "4.8", fontsize=9)
    page.insert_text((390, 260), "92000", fontsize=9)

    doc.save(str(path))
    doc.close()

    units, page_count, scanned = _extract_pdf_sync(path)
    combined = "\n".join(u.text for u in units)
    # Check that table was parsed as markdown table with pipe characters
    assert "|" in combined
    assert "Auth Gateway" in combined
    assert "P99 Latency" in combined


# ---------------------------------------------------------------------------
# 5. Code and equations
# ---------------------------------------------------------------------------
def test_pdf_05_code_and_equations(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "05_code_equations.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Algorithm Specification: Raft RPC Handling", fontsize=14)
    code_text = (
        "def append_entries(term, leader_id, prev_log_index, prev_log_term, entries):\n"
        "    if term < current_term:\n"
        "        return False\n"
        "    if log[prev_log_index].term != prev_log_term:\n"
        "        return False\n"
        "    return True"
    )
    page.insert_text((72, 120), code_text, fontname="courier", fontsize=10)
    page.insert_text((72, 260), "Mathematical Loss Formula: L(theta) = 1/N * sum((y_i - y_hat)^2)", fontsize=11)
    doc.save(str(path))
    doc.close()

    units, page_count, scanned = _extract_pdf_sync(path)
    text = " ".join(u.text for u in units)
    assert "append_entries" in text
    assert "prev_log_term" in text
    assert "Loss Formula" in text


# ---------------------------------------------------------------------------
# 6. Scanned image-only
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pdf_06_scanned_image_only(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "06_scanned.pdf"
    doc = fitz.open()
    img_bytes = create_scanned_page_image("Photocopied Notes on Calculus")
    for _ in range(2):
        page = doc.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=img_bytes)
    doc.save(str(path))
    doc.close()

    # Raw sync extraction detects scanned pages
    units, page_count, scanned = _extract_pdf_sync(path)
    assert page_count == 2
    assert scanned == [1, 2]
    assert len(units) == 0

    # Async extract_pdf raises clear PipelineError when vision model is not configured
    with pytest.raises(PipelineError) as exc_info:
        await extract_pdf(path)
    assert "Scanned pages" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7. Mixed digital and scanned pages
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pdf_07_mixed_digital_and_scanned(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "07_mixed.pdf"
    doc = fitz.open()

    # Page 1: Digital text
    p1 = doc.new_page(width=612, height=792)
    p1.insert_textbox(
        fitz.Rect(72, 100, 540, 300),
        "Page 1: Digital lecture summary with clear searchable typography. "
        "This section introduces the foundational concepts of distributed transaction isolation levels and concurrency control.",
        fontsize=12,
    )

    # Page 2: Scanned image
    p2 = doc.new_page(width=612, height=792)
    img_bytes = create_scanned_page_image("Page 2 Diagram Scan")
    p2.insert_image(p2.rect, stream=img_bytes)

    # Page 3: Digital text
    p3 = doc.new_page(width=612, height=792)
    p3.insert_textbox(
        fitz.Rect(72, 100, 540, 300),
        "Page 3: Digital conclusion and references cited in Section 4. "
        "In summary, optimistic concurrency control minimizes lock contention in low-conflict distributed environments.",
        fontsize=12,
    )

    doc.save(str(path))
    doc.close()

    # extract_pdf preserves readable pages (Page 1 and Page 3) without failing the whole file
    res = await extract_pdf(path)
    assert res.page_count == 3
    assert res.raw.get("scanned_pages") == [2]
    assert res.raw.get("unreadable_pages") == [2]
    # Verify units from digital pages are preserved
    preserved_pages = {u.page_no for u in res.units}
    assert 1 in preserved_pages
    assert 3 in preserved_pages
    assert any("Page 1: Digital" in u.text for u in res.units)
    assert any("Page 3: Digital" in u.text for u in res.units)


# ---------------------------------------------------------------------------
# 8. Blank-page PDF
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pdf_08_blank_pages(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "08_blank.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()

    units, page_count, scanned = _extract_pdf_sync(path)
    assert page_count == 3
    # Truly blank pages (0 chars, 0 images) must not be flagged as scanned
    assert scanned == []
    assert len(units) == 0

    with pytest.raises(PipelineError) as exc_info:
        await extract_pdf(path)
    assert "No readable text found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 9. Corrupt PDF
# ---------------------------------------------------------------------------
def test_pdf_09_corrupt_pdf(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "09_corrupt.pdf"
    path.write_bytes(b"%PDF-1.4\n%broken junk data\x00\xfftruncated without xref")

    with pytest.raises(PipelineError) as exc_info:
        _extract_pdf_sync(path)
    assert "corrupt or cannot be opened" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 10. Password-protected PDF
# ---------------------------------------------------------------------------
def test_pdf_10_password_protected_pdf(pdf_fixtures_dir: Path):
    path = pdf_fixtures_dir / "10_encrypted.pdf"
    doc = fitz.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text((72, 72), "Classified exam questions.")
    doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret123")
    doc.close()

    with pytest.raises(PipelineError) as exc_info:
        _extract_pdf_sync(path)
    assert "password-protected" in str(exc_info.value)


# ---------------------------------------------------------------------------
# FTS5 search query escaping verification
# ---------------------------------------------------------------------------
def test_fts5_query_escaping_and_stopword_handling():
    # Natural language question
    q1 = "What is the lock acquisition timeout?"
    fts_match = escape_query(q1)
    # Stopwords ('what', 'is', 'the') removed, key terms joined with OR
    assert '"lock"' in fts_match
    assert '"acquisition"' in fts_match
    assert '"timeout"' in fts_match or '"timeout"*' in fts_match
    assert " OR " in fts_match
    assert '"what"' not in fts_match.lower()
    assert '"is"' not in fts_match.lower()
