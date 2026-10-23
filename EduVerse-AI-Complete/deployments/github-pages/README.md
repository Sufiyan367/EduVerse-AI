# EduVerse AI — GitHub Pages Static Showcase Deployment

This directory contains the production-ready static assets deployed to **GitHub Pages** (`https://sufiyan367.github.io/EduVerse-AI/`).

## Architectural Scope & Capabilities

GitHub Pages provides static content delivery without a backend server process. As an honest and transparent educational interface, this deployment is configured with a **Static Preview Mode**:

| Feature / Module | Status on GitHub Pages | Behavior & Scope |
| :--- | :---: | :--- |
| **Interactive Knowledge Constellation** | **Full Support** | Dynamic SVG node graph and accessible list view for curriculum concepts with interactive topic inspection. |
| **Curriculum Syllabus Viewer** | **Full Support** | Bounded syllabus anchor preview for engineering course notes (Unit IV: Supervised Learning). |
| **Assessment Question Explorer** | **Full Support** | Browse curriculum-grounded multiple-choice questions, view verified answer keys, and read concept explanations. |
| **Mobile Navigation & Astra Design** | **Full Support** | Responsive 3-column workstation layout with dark mode tokens, typography, and tabbed panels. |
| **Custom PDF Upload & PyMuPDF Parsing** | **Requires Local Backend** | Server-side file parsing requires the Python FastAPI runtime. |
| **Live AI Tutor Inference (Gemini/Ollama)** | **Requires Local Backend** | LLM API credentials and token streaming run exclusively server-side. |
| **Multi-User SQLite & Vector Memory** | **Requires Local Backend** | User accounts, `sqlite-vec` embeddings, and attempt history are persisted in local SQLite databases. |

## Deployment Workflow

Static deployment is automated via the GitHub Actions workflow [`.github/workflows/deploy-pages.yml`](../../.github/workflows/deploy-pages.yml).

### Manual Enablement Steps in GitHub:
1. Navigate to repository **Settings** &rarr; **Pages**.
2. Under **Build and deployment** &rarr; **Source**, select **GitHub Actions**.
3. Push to `main` or trigger the workflow manually under the **Actions** tab.
