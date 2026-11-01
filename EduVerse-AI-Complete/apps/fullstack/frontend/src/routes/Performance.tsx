import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { BarChart2, BookOpen, Award, CheckCircle2, TrendingUp, ArrowRight } from 'lucide-react'
import { api } from '../lib/api'


export function PerformancePage() {
  const { data: courses = [], isLoading: coursesLoading } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  const { data: history = [] } = useQuery({
    queryKey: ['simulator-history'],
    queryFn: () => api.getExamHistory(),
  })

  const gradedExams = history.filter((h: any) => h.status === 'graded')
  const avgExamScore =
    gradedExams.length > 0
      ? Math.round(
          gradedExams.reduce((acc: number, curr: any) => acc + (curr.percentage || 0), 0) / gradedExams.length
        )
      : null

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
          <BarChart2 className="h-7 w-7 text-primary" />
          My Academic Performance & Analytics
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Longitudinal progress tracking across all courses, exam simulations, and syllabus mastery.
        </p>
      </div>

      {/* Top Level KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
            <BookOpen className="h-4 w-4 text-primary" /> Enrolled Courses
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">{courses.length}</div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
            <Award className="h-4 w-4 text-emerald-500" /> Simulations Completed
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">{gradedExams.length}</div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
            <TrendingUp className="h-4 w-4 text-amber-500" /> Average Exam Score
          </div>
          <div className="text-2xl font-bold text-amber-500 mt-2">
            {avgExamScore !== null ? `${avgExamScore}%` : 'N/A'}
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-purple-500" /> Readiness Index
          </div>
          <div className="text-2xl font-bold text-purple-500 mt-2">
            {courses.length > 0 ? 'Optimal' : 'Needs Setup'}
          </div>
        </div>
      </div>

      {/* Course Performance Breakdown */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm space-y-6">
        <h2 className="text-lg font-bold text-foreground">Course Readiness Breakdown</h2>
        {coursesLoading ? (
          <div className="h-32 bg-muted/30 animate-pulse rounded-lg" />
        ) : courses.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">No courses created yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {courses.map((c: any) => (
              <div
                key={c.id}
                className="p-5 rounded-xl border border-border bg-muted/20 hover:bg-muted/30 transition-colors flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-primary px-2 py-0.5 rounded bg-primary/10">
                      {c.code}
                    </span>
                    <span className="text-xs text-muted-foreground">{c.semester}</span>
                  </div>
                  <h3 className="text-base font-semibold text-foreground mt-2">{c.name}</h3>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground mt-3">
                    <span>{c.unit_count} Units</span>
                    <span>•</span>
                    <span>{c.topic_count} Topics</span>
                    <span>•</span>
                    <span>{c.paper_count} Past Papers</span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
                  <Link
                    to="/adaptive"
                    search={{ courseId: c.id }}
                    className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
                  >
                    View Mastery Graph <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <Link
                    to="/simulator"
                    search={{ courseId: c.id }}
                    className="text-xs font-medium text-emerald-500 hover:underline flex items-center gap-1"
                  >
                    Simulate Exam <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Exam Simulation Evaluations */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-border bg-muted/20">
          <h3 className="text-sm font-bold text-foreground">Detailed Exam Evaluations</h3>
        </div>
        <div className="p-6">
          {gradedExams.length === 0 ? (
            <p className="text-xs text-muted-foreground italic text-center py-4">
              No graded exam simulations yet. Start an exam simulation from the Exam Simulator tab.
            </p>
          ) : (
            <div className="space-y-3">
              {gradedExams.map((ex: any) => (
                <div
                  key={ex.id}
                  className="p-4 rounded-xl border border-border bg-muted/20 flex items-center justify-between"
                >
                  <div>
                    <div className="text-sm font-semibold text-foreground">{ex.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {ex.course_name} • Submitted {new Date(ex.submitted_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-sm font-bold text-emerald-500">
                      {ex.total_score} / {ex.max_score} ({ex.percentage}%)
                    </span>
                    <Link
                      to="/simulator"
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      View Rubric Report
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
