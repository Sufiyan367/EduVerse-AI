import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearch, Link } from '@tanstack/react-router'
import {
  BarChart2, BookOpen, Brain, Calendar, FileText,
  ListChecks, TrendingUp, Sparkles, AlertCircle, Clock
} from 'lucide-react'
import { api } from '../lib/api'
import { Badge, Button, Progress } from '../components/ui'
import { useActiveCourse } from '../lib/store'
import { formatRelative } from '../lib/utils'

export function ProgressPage() {
  const search: any = useSearch({ strict: false })
  const { activeCourseId } = useActiveCourse()
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(() => {
    if (search?.courseId) return Number(search.courseId)
    return activeCourseId || null
  })

  const { data: courses = [] } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  const courseList = courses as any[]
  const currentCourse = courseList.find((c) => c.id === selectedCourseId) || courseList[0] || null
  const effectiveCourseId = currentCourse?.id || null

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.dashboardStats(),
    refetchInterval: 30000,
  })

  const { data: courseProgress } = useQuery({
    queryKey: ['course-progress', effectiveCourseId],
    queryFn: () => (effectiveCourseId ? api.getCourseProgress(effectiveCourseId) : null),
    enabled: !!effectiveCourseId,
  })

  const { data: examHistory = [] } = useQuery({
    queryKey: ['exam-attempts-history', effectiveCourseId],
    queryFn: () => api.getExamHistory(),
  })

  const { data: forecastData } = useQuery({
    queryKey: ['cards-forecast'],
    queryFn: () => api.forecast(14),
  })

  const hasQuizData = stats && stats.total_quiz_attempts > 0
  const hasCardData = stats && stats.total_cards > 0
  const hasExamData = examHistory.length > 0

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <BarChart2 className="h-6 w-6 text-primary" />
            Learning Analytics & Progress
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Verifiable academic intelligence: syllabus mastery, quiz accuracy trends, exam evaluations, and memory retention.
          </p>
        </div>

        {/* Course Scope Filter */}
        {courseList.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-medium hidden sm:inline">Scope:</span>
            <select
              value={effectiveCourseId || ''}
              onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : null)}
              className="bg-card border border-border rounded-lg px-3 py-1.5 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {courseList.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} — {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Top Level Metric Cards (100% Real Data with Documented Calculation Source) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Flashcard Mastery (FSRS-6 State) */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Flashcard Mastery</span>
            <Brain className="h-4 w-4 text-primary" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {hasCardData ? (
              <>
                {stats.cards_mastered}
                <span className="text-xs text-muted-foreground font-normal ml-1.5">
                  / {stats.total_cards} cards
                </span>
              </>
            ) : (
              <span className="text-base font-semibold text-muted-foreground">Not enough data</span>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {hasCardData
              ? `Source: FSRS-6 scheduler (${stats.cards_learning} learning)`
              : 'Add study notes to extract flashcards'}
          </div>
        </div>

        {/* Metric 2: Quiz Accuracy (Actual attempts) */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Quiz Accuracy</span>
            <ListChecks className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {hasQuizData ? (
              `${stats.average_quiz_accuracy}%`
            ) : (
              <span className="text-base font-semibold text-muted-foreground">Not enough data</span>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {hasQuizData
              ? `Source: ${stats.total_quiz_attempts} attempts across ${stats.total_quiz_sessions} quizzes`
              : 'No quiz attempts recorded yet'}
          </div>
        </div>

        {/* Metric 3: Exam Simulations */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Exam Simulations</span>
            <TrendingUp className="h-4 w-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {hasExamData ? (
              <>
                {examHistory.length}
                <span className="text-xs text-muted-foreground font-normal ml-1.5">evaluated</span>
              </>
            ) : (
              <span className="text-base font-semibold text-muted-foreground">0 taken</span>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {hasExamData
              ? 'Source: Graded rubric evaluation sessions'
              : 'Launch Exam Simulator under Practice to test'}
          </div>
        </div>

        {/* Metric 4: Knowledge Gaps */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Knowledge Gaps</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {stats && stats.critical_gaps_count > 0 ? (
              <>
                {stats.critical_gaps_count}
                <span className="text-xs text-rose-400 font-semibold ml-1.5 text-[11px]">critical</span>
              </>
            ) : (
              <span className="text-base font-semibold text-emerald-400">0 critical</span>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            Source: Concepts scoring below 50% threshold
          </div>
        </div>
      </div>

      {/* Main Analytics Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Course Readiness & Topic Lifecycle */}
        <div className="space-y-6 lg:col-span-2">
          {/* Syllabus & Topic Completion Breakdown */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-foreground">
                  {currentCourse ? `${currentCourse.code} — Curriculum Readiness & Topic Lifecycle` : 'Curriculum Coverage'}
                </h2>
              </div>
              {currentCourse && (
                <Link
                  to="/courses"
                  search={{ courseId: currentCourse.id, tab: 'syllabus' } as any}
                  className="text-xs text-primary hover:underline"
                >
                  View syllabus map &rarr;
                </Link>
              )}
            </div>

            {currentCourse ? (
              <div className="space-y-4">
                {/* 4 Topic Lifecycle Stages */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
                  <div className="bg-muted/30 p-2.5 rounded-lg border border-border/50">
                    <span className="text-[11px] text-muted-foreground">Not Started</span>
                    <p className="text-base font-bold text-foreground mt-0.5">
                      {courseProgress?.topics_by_status?.not_started ?? currentCourse.topic_count ?? 0}
                    </p>
                  </div>
                  <div className="bg-sky-500/10 p-2.5 rounded-lg border border-sky-500/20">
                    <span className="text-[11px] text-sky-400">Learning</span>
                    <p className="text-base font-bold text-sky-300 mt-0.5">
                      {courseProgress?.topics_by_status?.learning ?? 0}
                    </p>
                  </div>
                  <div className="bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
                    <span className="text-[11px] text-rose-400">Needs Review</span>
                    <p className="text-base font-bold text-rose-300 mt-0.5">
                      {courseProgress?.topics_by_status?.needs_review ?? 0}
                    </p>
                  </div>
                  <div className="bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/20">
                    <span className="text-[11px] text-emerald-400">Mastered</span>
                    <p className="text-base font-bold text-emerald-300 mt-0.5">
                      {courseProgress?.topics_by_status?.mastered ?? 0}
                    </p>
                  </div>
                </div>

                {/* Documented Course Readiness Formula Display */}
                <div className="space-y-2 pt-2 border-t border-border/60">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground font-semibold">Course Readiness Index</span>
                    <span className="font-bold text-foreground">
                      {courseProgress?.has_sufficient_data && courseProgress.readiness_percentage != null
                        ? `${courseProgress.readiness_percentage}%`
                        : 'Not enough data'}
                    </span>
                  </div>

                  <Progress
                    value={courseProgress?.has_sufficient_data && courseProgress.readiness_percentage != null ? courseProgress.readiness_percentage : 0}
                    tone={
                      (courseProgress?.readiness_percentage ?? 0) >= 70
                        ? 'success'
                        : (courseProgress?.readiness_percentage ?? 0) >= 40
                        ? 'accent'
                        : 'danger'
                    }
                    className="h-2"
                  />

                  {/* Explicit Calculation Basis Citation */}
                  <div className="p-3 rounded-lg bg-muted/20 border border-border/50 text-[11px] text-muted-foreground space-y-1">
                    <p className="font-medium text-foreground">
                      {courseProgress?.calculation_basis || 'Not enough data to calculate readiness. Complete topic quizzes or an exam simulation to evaluate readiness.'}
                    </p>
                    <p className="text-[10px] text-muted-foreground font-mono">
                      Formula: {courseProgress?.formula_documentation}
                    </p>
                  </div>
                </div>

                {/* Per-Unit Progress List */}
                {courseProgress?.unit_progress && courseProgress.unit_progress.length > 0 && (
                  <div className="space-y-2 pt-2">
                    <span className="text-xs font-semibold text-foreground">Unit-Level Topic Breakdown</span>
                    <div className="space-y-1.5">
                      {courseProgress.unit_progress.map((u: any) => (
                        <div key={u.unit_id} className="p-2.5 rounded-lg border border-border/60 bg-card flex items-center justify-between text-xs">
                          <div>
                            <span className="font-semibold text-foreground">Unit {u.unit_number}: {u.title}</span>
                            <span className="text-muted-foreground ml-2 text-[11px]">
                              ({u.assessed_topics}/{u.total_topics} assessed · {u.mastered_topics} mastered)
                            </span>
                          </div>
                          <span className="font-mono text-xs font-bold text-primary">
                            {u.unit_readiness != null ? `${u.unit_readiness}%` : 'Not assessed'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="py-6 text-center text-xs text-muted-foreground">
                No active course selected. Select a course workspace to view syllabus mastery.
              </p>
            )}
          </div>

          {/* Exam Simulator History & Rubrics */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-emerald-400" />
                <h2 className="text-sm font-semibold text-foreground">Recent Exam Simulation Attempts</h2>
              </div>
              <Link to="/practice" search={{ tab: 'simulator' } as any} className="text-xs text-primary hover:underline">
                New simulation &rarr;
              </Link>
            </div>

            {examHistory.length === 0 ? (
              <div className="py-8 text-center text-xs text-muted-foreground">
                No exam simulations taken yet. Launch the Exam Simulator under Practice to test with university timing and AI rubric grading.
              </div>
            ) : (
              <div className="divide-y divide-border/60">
                {examHistory.slice(0, 5).map((attempt: any) => (
                  <div key={attempt.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-foreground">
                          {attempt.paper_title || `Attempt #${attempt.id}`}
                        </span>
                        <Badge tone={attempt.status === 'evaluated' ? 'success' : 'accent'} className="text-[10px]">
                          {attempt.status}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Duration: {attempt.time_spent_minutes || 0}m · Completed {formatRelative(attempt.created_at)}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="text-sm font-bold text-foreground">
                        {attempt.total_score != null ? `${attempt.total_score} marks` : 'Pending'}
                      </div>
                      {attempt.percentage != null && (
                        <span className="text-[11px] font-mono text-muted-foreground">
                          {Math.round(attempt.percentage)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: 14-Day Memory Decay Forecast & Traceable Activity */}
        <div className="space-y-6 lg:col-span-1">
          {/* 14-Day Memory Retention / Due Schedule Forecast */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-purple-400" />
                <h2 className="text-sm font-semibold text-foreground">Memory Decay Forecast</h2>
              </div>
              <span className="text-[10px] text-muted-foreground font-mono">FSRS-6 Algorithm</span>
            </div>

            <p className="text-xs text-muted-foreground">
              Review schedule calculated from card difficulty, stability, and retrieval retention:
            </p>

            {forecastData?.forecast && forecastData.forecast.length > 0 ? (
              <div className="space-y-2 pt-1">
                {forecastData.forecast.slice(0, 7).map((day: any) => (
                  <div key={day.date} className="flex items-center justify-between text-xs py-1 border-b border-border/40">
                    <span className="text-muted-foreground font-mono">
                      {new Date(day.date).toLocaleDateString(undefined, { weekday: 'short', month: 'numeric', day: 'numeric' })}
                    </span>
                    <span className="font-semibold text-foreground bg-muted/40 px-2 py-0.5 rounded text-[11px]">
                      {day.count} due
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-4 text-center text-xs text-muted-foreground italic">
                Not enough data — no spaced repetition reviews scheduled yet.
              </p>
            )}

            <div className="pt-2">
              <Link to="/practice" search={{ tab: 'flashcards' } as any}>
                <Button size="sm" variant="secondary" className="w-full justify-center text-xs">
                  Open Flashcard Deck
                </Button>
              </Link>
            </div>
          </div>

          {/* Traceable Learning Audit Log */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold text-foreground">Activity Audit Trail</h2>
              </div>
              <Sparkles className="h-3.5 w-3.5 text-primary" />
            </div>

            {stats && stats.recent_activities.length > 0 ? (
              <div className="divide-y divide-border/60 text-xs">
                {stats.recent_activities.slice(0, 5).map((act) => (
                  <div key={act.id} className="py-2.5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-foreground truncate">{act.title}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0 ml-1">
                        {formatRelative(act.created_at)}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted-foreground font-mono uppercase bg-muted/30 px-1.5 py-0.2 rounded inline-block">
                      {act.entity_type}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-6 text-center text-xs text-muted-foreground italic">
                No activity recorded yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
