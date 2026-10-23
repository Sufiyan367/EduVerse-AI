# EduVerse AI — Undergraduate Engineering Project Report

**Project Title:** EduVerse AI – An Animated Virtual Tutor for Personalized Learning  
**Department:** Artificial Intelligence & Data Science  
**Institution:** Indira College of Engineering and Management (ICEM), Parandwadi, Pune  
**Affiliation:** Autonomous Institute Affiliated to Savitribai Phule Pune University (SPPU)  
**Academic Year:** 2026–2027  
**Submission Requirement:** Mini Project Report / Review-2 Documentation (Strictly 25 Pages)  

---

## Project Team & Mentorship

- **Aryan Shinde** (Roll No: AI-01)
- **Huzaifa Sheikh** (Roll No: AI-02)
- **Sufiyan Surve** (Roll No: AI-03)
- **Project Guide / Mentor:** Prof. Monika Patil, Assistant Professor, Department of AI & DS, ICEM Pune

---

## Directory Structure

```text
EduVerse_AI_Project_Report/
│
├── EduVerse_AI_Project_Report.tex    # Master LaTeX document (25 pages)
├── EduVerse_AI_Project_Report.pdf    # Compiled PDF report (Exactly 25 pages)
├── README.md                         # Detailed documentation and compilation guide
│
├── images/                           # High-resolution vector and raster assets
│   ├── college_banner.png            # Official ICEM / SPPU autonomous institutional banner
│   ├── college_logo.png              # Indira circular emblem
│   ├── hero_visual.jpg               # 3D student + AI tutor educational concept illustration
│   ├── avatar_assistant.jpg          # 3D virtual tutor character model visual
│   ├── system_architecture.png       # End-to-end multi-tier system architecture diagram
│   └── prototype_ui.png              # Functional Review-2 prototype interface mockup
│
└── preview/                          # Rendered high-dpi page previews
    ├── page_1.png                    # Cover page
    ├── page_2.png                    # Certificate of Approval & Candidate Declaration
    ├── page_5.png                    # Table of Contents
    ├── page_7.png                    # Problem Statement & Educational Bottleneck
    ├── page_12.png                   # System Architecture & Tier Decomposition
    ├── page_15.png                   # Prototype Workspace UI Demonstration
    ├── page_19.png                   # Virtual Tutor & Avatar Interaction
    ├── page_21.png                   # Review-2 Prototype Deliverables & Status Matrix
    └── page_25.png                   # Technical Specifications, REST Endpoints & JSON Schema
```

---

## Complete 25-Page Document Mapping

Each chapter and preliminary matter is strictly formatted to occupy exactly one page without accidental underflow or multi-page overflow:

| Page | Title / Section | Key Technical Content |
|:---:|:---|:---|
| **1** | **Cover Page** | Official ICEM SPPU Autonomous Banner, Project Title, Team Members, Mentor, AY 2026–2027 |
| **2** | **Certificate / Declaration** | Bonafide project certificate, signature lines for Guide, HOD, Principal, and Candidate Declaration |
| **3** | **Acknowledgement** | Academic acknowledgements to Guide, Department, Management, and peer reviewers |
| **4** | **Abstract** | Concise summary of problem, PyMuPDF extraction, LLM grounding, quiz engine, and prototype status |
| **5** | **Table of Contents** | Formal structured listing of preliminary matters and Chapters 1 to 20 |
| **6** | **1. Introduction** | Background, cognitive fatigue in passive reading, need for interactive tutors, and report structure |
| **7** | **2. Problem Statement & Motivation** | Information fragmentation, absence of contextual doubt resolution, bottleneck model, and NLP motivation |
| **8** | **3. Aim, Objectives and Scope** | Core project aim, 6 functional engineering objectives, in-scope capabilities, and project boundaries |
| **9** | **4. Existing System vs. Proposed Solution** | Analysis of PDF readers vs generic chatbots vs EduVerse AI, feature matrix, closed-loop workflow |
| **10** | **5. Requirements Analysis** | Functional Requirements (FR-01 to FR-07), Non-Functional Requirements (NFR-01 to NFR-03), HW/SW specs |
| **11** | **6. Technology Stack Specification** | React.js frontend, Python FastAPI backend, PyMuPDF engine, LLM API tier, SQLite/PostgreSQL, WebGL |
| **12** | **7. System Architecture & Pipeline Design** | High-level architectural model, system diagram, and 5-tier decomposition with data flow rules |
| **13** | **8. Module Decomposition and Design** | Ingestion module, context grounding engine, quiz generator, avatar coordinator, and analytics |
| **14** | **9. Detailed End-to-End System Workflow** | 6-stage sequential lifecycle from upload to text parsing, grounding, Q&A, quiz, and evaluation |
| **15** | **10. Frontend Architecture & User Interface** | 3-column UI design principles, annotated prototype workspace diagram, and UI component breakdown |
| **16** | **11. Document Processing & Text Extraction** | PDF geometric stream challenge, PyMuPDF C++ engine integration, Python extraction routine, limitations |
| **17** | **12. Contextual Q&A and Explanation Engine** | Prompt engineering for zero hallucination, strict context boundaries, analogy decomposition strategy |
| **18** | **13. Automated Quiz Generation & Evaluation** | Active recall pedagogy, MCQ JSON prompt formulation, distractor plausibility, and scoring engine |
| **19** | **14. Virtual Tutor and Avatar Interaction** | Social presence in EdTech, 3D character design, visual state cues, WebGL / Three.js pathway |
| **20** | **15. Testing, Verification & Test Cases** | Verification strategy, 5 formal test case specifications (TC-01 to TC-05), and pass criteria |
| **21** | **16. Prototype Results and Discussion** | Review-2 prototype deliverables, feature implementation status matrix, and architectural discussion |
| **22** | **17. Applications, Advantages & Limitations** | Engineering self-study, exam revision, lab manual tutor, core advantages, and technical constraints |
| **23** | **18. Phased Roadmap and Future Scope** | 4-phase development trajectory (Review-2 Prototype $\to$ Core Implementation $\to$ Avatars $\to$ Evaluation) |
| **24** | **19. Conclusion and References** | Project summary, educational significance, and formal bibliographic citations (Vaswani, Lewis, etc.) |
| **25** | **20. Appendix: Technical Specifications & Schemas** | RESTful API endpoint table (`/api/documents/upload`, etc.), JSON schema contract, metadata |

---

## How to Compile the Report

### Method 1: Using the Bundled Tectonic Compiler (Recommended)

The workspace includes the modern self-contained TeX compiler **Tectonic** at `s:\SY\SEM 3\MP\bin\tectonic.exe`. Tectonic automatically manages all CTAN package downloads and generates the final PDF in a single step without needing multi-pass scripts.

Run the following command from PowerShell:

```powershell
& "s:\SY\SEM 3\MP\bin\tectonic.exe" "s:\SY\SEM 3\MP\EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.tex"
```

The output file `EduVerse_AI_Project_Report.pdf` will be created or updated directly in `EduVerse_AI_Project_Report/`.

### Method 2: Using TeX Live or MiKTeX (Standard LaTeX Distribution)

If you have a standard TeX distribution installed on your system (`pdflatex` or `xelatex`):

```bash
cd EduVerse_AI_Project_Report
pdflatex EduVerse_AI_Project_Report.tex
pdflatex EduVerse_AI_Project_Report.tex
```
*(Running twice is recommended to ensure all page references and hyperref bookmarks resolve properly).*

---

## Verifying the Exact 25-Page Count

You can programmatically verify that the compiled PDF report is **strictly 25 pages** using the included Python verification snippet:

```powershell
python -c "import fitz; doc = fitz.open(r's:\SY\SEM 3\MP\EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.pdf'); print(f'Total Pages: {len(doc)} (Target: 25)')"
```

Expected output:
```text
Total Pages: 25 (Target: 25)
```
