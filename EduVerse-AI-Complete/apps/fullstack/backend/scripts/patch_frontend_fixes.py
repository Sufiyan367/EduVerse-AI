from pathlib import Path

frontend_dir = Path("EduVerse-AI-repo/EduVerse-AI-Complete/apps/fullstack/frontend/src")

# 1. Update components/ui/index.tsx
ui_index = frontend_dir / "components" / "ui" / "index.tsx"
ui_content = ui_index.read_text(encoding="utf-8")
if "export function Modal" not in ui_content:
    modal_code = """
export function Modal({
  open,
  onClose,
  title,
  children,
  className,
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className={className}>
        {title && <DialogTitle className="mb-3">{title}</DialogTitle>}
        {children}
      </DialogContent>
    </Dialog>
  )
}
"""
    ui_content += modal_code
    ui_index.write_text(ui_content, encoding="utf-8")
    print("Added Modal to components/ui/index.tsx")

# 2. Update components/layout/AppShell.tsx
appshell_path = frontend_dir / "components" / "layout" / "AppShell.tsx"
appshell_content = appshell_path.read_text(encoding="utf-8")
appshell_content = appshell_content.replace("Mic, MessageSquare, Headphones,", "MessageSquare,")
appshell_content = appshell_content.replace("ListChecks, AlertTriangle, CalendarCheck,", "ListChecks, CalendarCheck,")
appshell_path.write_text(appshell_content, encoding="utf-8")
print("Cleaned unused imports in AppShell.tsx")

# 3. Update Courses.tsx
courses_path = frontend_dir / "routes" / "Courses.tsx"
courses_content = courses_path.read_text(encoding="utf-8")
courses_content = courses_content.replace(", Calendar", "")
courses_content = courses_content.replace('variant="outline"', 'variant="secondary"')
courses_content = courses_content.replace('<Badge variant="secondary"', '<Badge tone="accent"')
courses_path.write_text(courses_content, encoding="utf-8")
print("Patched Courses.tsx")

# 4. Update SyllabusMap.tsx
syllabus_path = frontend_dir / "routes" / "SyllabusMap.tsx"
syllabus_content = syllabus_path.read_text(encoding="utf-8")
syllabus_content = syllabus_content.replace("BookOpen, Trash2, CheckCircle2, AlertCircle", "Trash2")
syllabus_content = syllabus_content.replace(", Badge", "")
syllabus_content = syllabus_content.replace('variant="outline"', 'variant="secondary"')
syllabus_content = syllabus_content.replace("() => api.sources(),", "() => api.listSources().then(r => r.sources),")
syllabus_content = syllabus_content.replace(
    "  const searchParams = useRouterState({\n    select: (s) => (s.location.search as any) || {},\n  })",
    "  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams()"
)
syllabus_content = syllabus_content.replace(
    "if (searchParams.courseId) return Number(searchParams.courseId)",
    "const cid = urlParams.get('courseId'); if (cid) return Number(cid)"
)
syllabus_path.write_text(syllabus_content, encoding="utf-8")
print("Patched SyllabusMap.tsx")

# 5. Update PaperAnalytics.tsx
papers_path = frontend_dir / "routes" / "PaperAnalytics.tsx"
papers_content = papers_path.read_text(encoding="utf-8")
papers_content = papers_content.replace(", Badge", "")
papers_content = papers_content.replace('variant="outline"', 'variant="secondary"')
papers_content = papers_content.replace("() => api.sources(),", "() => api.listSources().then(r => r.sources),")
papers_content = papers_content.replace(
    "  const searchParams = useRouterState({\n    select: (s) => (s.location.search as any) || {},\n  })",
    "  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams()"
)
papers_content = papers_content.replace(
    "if (searchParams.courseId) return Number(searchParams.courseId)",
    "const cid = urlParams.get('courseId'); if (cid) return Number(cid)"
)
papers_path.write_text(papers_content, encoding="utf-8")
print("Patched PaperAnalytics.tsx")

# 6. Update ExamSimulator.tsx
simulator_path = frontend_dir / "routes" / "ExamSimulator.tsx"
sim_content = simulator_path.read_text(encoding="utf-8")
sim_content = sim_content.replace("Clock, CheckCircle2, AlertCircle, Sparkles, Send, RotateCcw,", "Sparkles, Send,")
sim_content = sim_content.replace("const { data: sessionData, isLoading: sessionLoading }", "const { data: sessionData }")
sim_content = sim_content.replace('variant="outline"', 'variant="secondary"')
sim_content = sim_content.replace("<Badge variant={isGraded ? 'default' : 'secondary'}", "<Badge tone={isGraded ? 'success' : 'neutral'}")
sim_content = sim_content.replace(
    "  const searchParams = useRouterState({\n    select: (s) => (s.location.search as any) || {},\n  })",
    "  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams()"
)
sim_content = sim_content.replace(
    "if (searchParams.courseId) return Number(searchParams.courseId)",
    "const cid = urlParams.get('courseId'); if (cid) return Number(cid)"
)
simulator_path.write_text(sim_content, encoding="utf-8")
print("Patched ExamSimulator.tsx")

# 7. Update AdaptiveRevision.tsx
adaptive_path = frontend_dir / "routes" / "AdaptiveRevision.tsx"
adapt_content = adaptive_path.read_text(encoding="utf-8")
adapt_content = adapt_content.replace(", Link", "")
adapt_content = adapt_content.replace("AlertTriangle, CheckCircle, Clock, Sparkles, Brain, ListChecks, BookOpen", "CheckCircle, Clock, Sparkles, Brain, ListChecks")
adapt_content = adapt_content.replace("Input, Modal, Badge", "")
adapt_content = adapt_content.replace("const { data: planData, isLoading: planLoading }", "const { data: planData }")
adapt_content = adapt_content.replace('variant="outline"', 'variant="secondary"')
adapt_content = adapt_content.replace(
    "  const searchParams = useRouterState({\n    select: (s) => (s.location.search as any) || {},\n  })",
    "  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams()"
)
adapt_content = adapt_content.replace(
    "if (searchParams.courseId) return Number(searchParams.courseId)",
    "const cid = urlParams.get('courseId'); if (cid) return Number(cid)"
)
adaptive_path.write_text(adapt_content, encoding="utf-8")
print("Patched AdaptiveRevision.tsx")

# 8. Update Performance.tsx
perf_path = frontend_dir / "routes" / "Performance.tsx"
perf_content = perf_path.read_text(encoding="utf-8")
perf_content = perf_content.replace(", Calendar", "")
perf_content = perf_content.replace("import { Button, Badge } from '../components/ui'", "")
perf_path.write_text(perf_content, encoding="utf-8")
print("Patched Performance.tsx")
