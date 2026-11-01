# Third-Party Notices and Acknowledgements

EduVerse AI incorporates and adapts technical patterns, algorithms, and reference implementations from open-source projects under permissible licenses. This document records upstream origins, commit SHAs, copyright notices, and licensing terms in accordance with open-source compliance requirements.

---

## 1. Cinnamon Kotaemon

- **Upstream Repository:** [https://github.com/Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon)
- **License:** Apache License, Version 2.0
- **Copyright:** Copyright (c) 2024 Cinnamon AI
- **Verified Commit SHA:** `9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9`
- **Verification Date:** November 1, 2026

### Adapted & Ported Components:
EduVerse AI does not import the entire Kotaemon repository (which introduces heavy dependencies such as Gradio, TheFlow, and ChromaDB conflicting with EduVerse's lightweight React + SQLite architecture). Instead, the following specialized algorithms and technical patterns were adapted into EduVerse:

1. **Document-Aware PDF Layout & Reading Order (`libs/kotaemon/kotaemon/loaders/utils/box.py` & `pdf_ocr.py`):**
   - Spatial bounding-box coordinate classification and reading-order reconstruction for multi-column academic documents.
   - Adapted in: `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/pipeline/extract/document.py` (`_sort_page_blocks`).

2. **Table Markdown Conversion (`libs/kotaemon/kotaemon/loaders/utils/table.py`):**
   - Table cell boundary detection, column conflict checking, and markdown table synthesis (`make_markdown_table`, `format_cell`).
   - Adapted in: `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/pipeline/extract/document.py` and `segment.py`.

3. **Page Thumbnail Previews for Citations (`libs/kotaemon/kotaemon/loaders/pdf_loader.py`):**
   - On-demand base64 page thumbnail generation (`get_page_thumbnails`) for interactive citation hover and click-through preview.
   - Adapted in: `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/api/sources.py`.

4. **Inline Citation QA & Evidence Linking (`libs/kotaemon/kotaemon/indices/qa/citation_qa_inline.py`):**
   - Inline citation extraction regex, bracketed marker formatting, and interactive HTML citation link synthesis.
   - Adapted in: `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/api/chat.py` (`validate_answer`, `assess_evidence_support`).

5. **Context Relevance Warning Threshold (`libs/ktem/ktem/reasoning/simple.py`):**
   - Reranker relevance threshold guard (`CONTEXT_RELEVANT_WARNING_SCORE = 0.15`) preventing weakly related passages from being presented as confident context.
   - Adapted in: `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/rag/retrieve.py` (`rerank`).

6. **Conversational Query Contextualization (`libs/ktem/ktem/reasoning/simple.py` & `decompose_question.py`):**
   - Conversational query rewriting for anaphoric follow-up questions before hitting retrieval indices.
   - Adapted in: `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn/api/chat.py` (`_contextualize_query`).

---

### Apache License 2.0 Text:

```text
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.
      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.
      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.
      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity.
      ...
   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:
      (a) You must give any other recipients of the Work or Derivative
          Works a copy of this License; and
      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and
      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work.
```

---

## 2. Other Open-Source Dependencies

- **FastAPI:** MIT License, Copyright (c) 2018 Sebastián Ramírez
- **PyMuPDF (`fitz`):** AGPL-3.0 / Commercial, Copyright (c) 2024 Artifex Software, Inc.
- **FastEmbed:** Apache-2.0, Copyright (c) 2023 Qdrant
- **sqlite-vec:** MIT License / Apache-2.0, Copyright (c) 2024 Alex Garcia
- **React & Vite:** MIT License, Copyright (c) Meta Platforms, Inc. and Vite contributors
- **Tailwind CSS:** MIT License, Copyright (c) Tailwind Labs, Inc.
