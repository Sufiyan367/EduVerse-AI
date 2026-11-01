from pathlib import Path

frontend_dir = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/frontend/src/routes")

for fname in ["AdaptiveRevision.tsx", "ExamSimulator.tsx", "PaperAnalytics.tsx", "SyllabusMap.tsx"]:
    p = frontend_dir / fname
    text = p.read_text(encoding="utf-8")
    text = text.replace("import { useRouterState } from '@tanstack/react-router'\n", "")
    text = text.replace("import { useRouterState, Link } from '@tanstack/react-router'\n", "")
    text = text.replace("import { useRouterState } from '@tanstack/react-router'", "")
    p.write_text(text, encoding="utf-8")

papers_path = frontend_dir / "PaperAnalytics.tsx"
p_text = papers_path.read_text(encoding="utf-8")
p_text = p_text.replace(", AlertCircle, ArrowUpRight", "")
papers_path.write_text(p_text, encoding="utf-8")

print("Cleaned remaining unused imports!")
