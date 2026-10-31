# EduVerse AI — RAG Engineering & Architectural Stabilization Report

**Project:** EduVerse AI (B.Tech AI & Data Science Mini-Project)  
**Branch:** `feature/eduverse-48h-rebuild`  
**Canonical Path:** `EduVerse-AI-Complete/apps/fullstack`  
**Lead Engineer:** Senior AI/ML & Full-Stack Systems Engineer  
**Date:** October 31, 2026 / November 1, 2026  

---

## 1. Executive Summary

This engineering report documents the comprehensive audit, structural repair, and architectural stabilization of the Retrieval-Augmented Generation (RAG) pipeline in EduVerse AI. Prior to this intervention, the document-grounded question-answering workflow suffered from systemic vector store misinitialization, reading-order corruption in multi-column PDFs, cross-page chunk boundary blending, unconstrained reranker scoring, anaphoric follow-up retrieval failure, cross-tenant retrieval leakage, and unverified citation hallucinations.

All seven root causes have been systematically repaired, tested with automated regression suites, verified with a 15-category synthetic academic benchmark, and integrated into the canonical fullstack application without compromising existing user authentication, database models, or UI workflows.

---

## 2. Root Cause Analysis of Prior Failures

### 2.1 Vector Store Engine Misinitialization (`sqlite-vec`)
- **Fault Mechanism:** `quicklearn.rag.index.get_index()` executed `vec_available()` before any connection to the SQLAlchemy engine had been initiated. Because `sqlite_vec.load()` was attached to SQLAlchemy's engine `connect` event, `vec_available()` evaluated against an uninitialized state, returned `False`, and permanently defaulted to an ephemeral, in-memory `NumpyIndex` that wiped embeddings on restart.
- **Impact:** Vector retrieval returned 0 hits or stale vectors, forcing the pipeline into pure BM25 or empty contexts.
- **Resolution:** Modified `get_index()` to explicitly probe the database engine (`with get_engine().connect(): pass`) before inspecting `vec_available()`, ensuring `sqlite-vec` loads reliably into SQLite virtual tables (`segment_vectors`).

### 2.2 Multi-Column Academic PDF Reading-Order Corruption
- **Fault Mechanism:** Standard PyMuPDF block extraction returned layout blocks in raw vertical coordinate order (`y0, x0`), interleaving adjacent columns in academic two-column papers. A sentence starting in column 1 was interrupted mid-thought by column 2.
- **Impact:** Semantic vectors and keyword search received garbled fragments, breaking retrieval accuracy for academic papers.
- **Resolution:** Implemented `_sort_page_blocks(blocks, page_width)` in `backend/quicklearn/pipeline/extract/document.py`. It calculates column partitions (left: $x_1 \le 0.48 \times W$, right: $x_0 \ge 0.52 \times W$, header/footer spans: $W_{span} \ge 0.70 \times W$) and assembles text in true semantic reading order: Full-width Headers $\rightarrow$ Left Column (top-to-bottom) $\rightarrow$ Right Column (top-to-bottom) $\rightarrow$ Full-width Footers.

### 2.3 Individual Sparse & Scanned Page Dropping
- **Fault Mechanism:** The extractor required $\ge 50\%$ of all pages in a document to be scanned before triggering OCR or vision transcription. In a 20-page lecture slide deck with 3 image/diagram pages, those 3 pages yielded empty text and were silently ignored.
- **Impact:** Students asking questions about diagrams, architecture charts, or handwritten formulas on specific slides received "I could not find anything in your notes."
- **Resolution:** Page-level scanned detection: individual pages with $< 100$ characters are tracked in `scanned_pages` and batched (up to 4 pages per batch) to the vision provider. Unreadable pages are explicitly tracked in `ExtractResult.raw["unreadable_pages"]`.

### 2.4 Cross-Page Chunk Blending and Citations
- **Fault Mechanism:** The text segmenter merged tokens across page boundaries to fill segment character limits (`merge_document`).
- **Impact:** Citations pointed to arbitrary page numbers where the chunk started, even if the quoted fact was physically on the next page.
- **Resolution:** Rewrote `merge_document` with strict page-boundary guards: chunks never cross `page_no` boundaries, table rows are kept intact, and new chunks start cleanly on Markdown headings. A rolling overlap unit (~150-300 characters) is retained exclusively on the *same* page.

### 2.5 Reranker Relevance Threshold & False Contexts
- **Fault Mechanism:** The reranker sorted fused BM25/vector hits and blindly returned the top $K$ excerpts even when the highest score was near zero ($< 0.05$).
- **Impact:** Irrelevant passages were provided to the LLM as confident context, encouraging hallucinated answers on completely unrelated or ungrounded queries.
- **Resolution:** Applied a strict 0.15 threshold filter in `backend/quicklearn/rag/retrieve.py`. If all retrieved candidates score $\le 0.15$, the reranker returns `[]`, enabling honest model abstention ("The provided course materials do not cover this topic.").

### 2.6 Follow-up Question Anaphora (Loss of Topic)
- **Fault Mechanism:** Follow-up questions like "What are its two phases?" or "Explain the second one" were passed verbatim to vector retrieval. Because the query contained only pronouns and lacked the subject noun from the prior turn, vector search matched arbitrary passages.
- **Impact:** Follow-up conversations disintegrated immediately after the first turn.
- **Resolution:** Added `_contextualize_query()` in `backend/quicklearn/api/chat.py`. It inspects conversational history and, when anaphoric pronouns or elliptical queries are detected, uses the fast LLM tier (or deterministic fallback) to rewrite the retrieval query into a standalone semantic search query before invoking RAG.

### 2.7 Cross-Tenant Retrieval Security Leakage
- **Fault Mechanism:** `retrieve()` in `retrieve.py` lacked user authentication filtering. When `scope_type="global"`, `_scope_source_ids` returned all sources in the database, allowing Student A to retrieve and view private notes and study materials uploaded by Student B.
- **Impact:** Multi-tenant privacy violation.
- **Resolution:** Enforced `user_id` filtering in `_scope_source_ids` and `_load_excerpts`. Authenticated users can only retrieve from sources they own (`user_id == user.id`) or public unowned demo materials (`user_id IS NULL`). Cross-user requests resolve to a `[-1]` sentinel matching zero segments.

---

## 3. End-to-End RAG Architecture

```
                                      [ Uploaded Document (PDF, MD, Audio) ]
                                                        │
                                                        ▼
                                       [ Document Extraction Engine ]
                             ┌──────────────────────────┴──────────────────────────┐
                             │ Multi-Column Geometry Sorter (_sort_page_blocks)    │
                             │ Individual Sparse Page Detection (scanned_pages)    │
                             └──────────────────────────┬──────────────────────────┘
                                                        │
                                                        ▼
                                       [ Boundary-Aware Chunking ]
                             ┌──────────────────────────┴──────────────────────────┐
                             │ Strict Page-Boundary Guards (never cross page_no)   │
                             │ Heading & Table Preservation + Same-Page Overlap    │
                             └──────────────────────────┬──────────────────────────┘
                                                        │
                                           ┌────────────┴────────────┐
                                           ▼                         ▼
                                 [ Dense Vector Index ]    [ Sparse BM25 / FTS ]
                                 (sqlite-vec / 384-dim)    (SQLite Full-Text Search)
                                           │                         │
                                           └────────────┬────────────┘
                                                        │
[ Student Query + History ] ──► [ Query Contextualizer ] │
                                         │              │
                                         ▼              ▼
                                [ Hybrid Retrieval & RRF Fusion ]
                                (Reciprocal Rank Fusion k=60)
                                         │
                                         ▼
                             [ Cross-Encoder / Relevance Reranker ]
                             (Relevance Threshold > 0.15 Guard)
                                         │
                                         ├─── Below 0.15 ──► [ Empty Context (Honest Abstention) ]
                                         │
                                         ▼ Above 0.15
                                 [ Verified Prompt Assembly ]
                             ┌───────────────────┴───────────────────┐
                             │ Excerpts: [ID, Source, Page, Text]    │
                             │ Scope Isolation (Multi-tenant check)  │
                             └───────────────────┬───────────────────┘
                                                 │
                                                 ▼
                                        [ LLM Generation ]
                                 (Google Gemini / Local / Fallback)
                                                 │
                                                 ▼
                                     [ Citation Grounding Guard ]
                             ┌───────────────────┴───────────────────┐
                             │ 1. Validate [ID] against retrieved IDs│
                             │ 2. Strip hallucinated citation markers│
                             │ 3. Fail closed on ungrounded claims   │
                             │ 4. Multi-paragraph citation check     │
                             │ 5. Compute Evidence Support Status    │
                             │    (strong / partial / insufficient)  │
                             └───────────────────┬───────────────────┘
                                                 │
                                                 ▼
                                  [ Streamed / Verified Response ]
                                  (Clickable Citation Previews & Excerpts)
```

---

## 4. Key Files Modified and Technical Changes

| File | Primary Changes |
| :--- | :--- |
| `backend/quicklearn/rag/index.py` | Probes engine connection in `get_index()` so `sqlite-vec` loads reliably into SQLite virtual tables before fallback check. |
| `backend/quicklearn/pipeline/extract/document.py` | Implemented `_sort_page_blocks` for two-column academic reading order; individual scanned page OCR batching; tracks `unreadable_pages`. |
| `backend/quicklearn/pipeline/segment.py` | Page-boundary chunking in `merge_document`; preserves table rows and headings; enforces same-page trailing overlap. |
| `backend/quicklearn/rag/retrieve.py` | Enforces `user_id` multi-tenant isolation in `_scope_source_ids` and `_load_excerpts`; adds strict 0.15 reranker threshold; adds diagnostic logging. |
| `backend/quicklearn/api/chat.py` | Implemented `_contextualize_query`; added `assess_evidence_support`; wired `user: User \| None = Depends(get_optional_user)` to all chat routes; enforced chat ownership. |
| `backend/quicklearn/providers/llm/google.py` | Added Google Gemini model fallbacks (`gemini-3.8-flash`, `gemini-2.5-flash`); structured output & vision support. |
| `backend/quicklearn/providers/pricing.py` | Added pricing entries for `gemini-3.8-flash` and `gemini-2.5-flash`. |
| `backend/quicklearn/providers/llm/mock.py` | Added cited excerpt grounding and explicit `is_mock=True` flag for transparent offline development. |
| `tests/test_rag_pipeline_repair.py` | Automated 9-test evaluation suite covering all 15 question categories, multi-column sorting, user isolation, and citation validation. |

---

## 5. Security & Multi-Tenant Data Isolation

1. **Document Scope Isolation:** `_scope_source_ids(scope_type, scope_id, user_id)` verifies that the requested `source_id` or `folder_id` belongs to the requesting user (`Source.user_id == user_id`). If an ID belongs to another user, it returns `[-1]`, preventing data leakage.
2. **Global Retrieval Containment:** When `scope_type="global"` is queried, only the student's own sources are queried. Other students' study materials are mathematically excluded from the search space.
3. **Citation Enumeration Defense:** The `/chat/citations?ids=...` endpoint joins `Source` and filters by `user_id`, preventing unauthorized students from enumerating and reading segments belonging to another user.
4. **Fail-Closed Ungrounded Claim Defense:** Answers that state factual claims without citing retrieved excerpts fail closed with a clear disclaimer: *"I could not verify this claim in the provided course materials. The retrieved passages do not contain evidence supporting this statement."*

---

## 6. Known Limitations and Future Work

- **Handwritten Equations in Scanned Images:** Highly non-standard handwritten math formulas in low-resolution scans require multimodal vision LLM transcription; pure rule-based OCR yields partial LaTeX.
- **Complex Multi-Page Spanning Tables:** Tables spanning across page 1 and page 2 are divided at the page boundary. Future work could introduce Markdown table continuation stitchers.
- **Dynamic Cross-Encoder GPU Inference:** In local offline mode without GPU, reranking utilizes lexical score fusion and title matching. High-concurrency production deployments can enable dedicated cross-encoder servers.
