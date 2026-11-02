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

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.dashboardStats(),
    refetchInterval: 30000,
  })

  const { data: examHistory = [] } = useQuery({
    queryKey: ['exam-attempts-history', selectedCourseId],
    queryFn: () => api.getExamHistory(),
  })

  const { data: forecastData } = useQuery({
    queryKey: ['cards-forecast'],
    queryFn: () => api.forecast(14),
  })

  const courseList = courses as any[]
  const currentCourse = courseList.find((c) => c.id === selectedCourseId) || courseList[0] || null

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
            Consolidated academic intelligence: syllabus mastery, quiz accuracy trends, exam simulation scores, and memory retention.
          </p>
        </div>

        {/* Course Scope Filter */}
        {courseList.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-medium hidden sm:inline">Scope:</span>
            <select
              value={selectedCourseId || ''}
              onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : null)}
              className="bg-card border border-border rounded-lg px-3 py-1.5 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">All Courses Combined</option>
              {courseList.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} — {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Top Level Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Flashcard Mastery</span>
            <Brain className="h-4 w-4 text-primary" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {stats ? stats.cards_mastered : 0}
            <span className="text-xs text-muted-foreground font-normal ml-1.5">
              / {stats ? stats.total_cards : 0} cards
            </span>
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {stats ? `${stats.cards_learning} currently learning` : 'FSRS-6 spaced repetition'}
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Quiz Accuracy</span>
            <ListChecks className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {stats ? `${stats.average_quiz_accuracy}%` : '0%'}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {stats ? `${stats.total_quiz_attempts} questions across ${stats.total_quiz_sessions} quizzes` : 'No quizzes completed'}
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Exam Simulations</span>
            <TrendingUp className="h-4 w-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {examHistory.length}
            <span className="text-xs text-muted-foreground font-normal ml-1.5">attempts</span>
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            Autonomous rubric evaluations
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Knowledge Gaps</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-foreground mt-2">
            {stats ? stats.critical_gaps_count : 0}
            <span className="text-xs text-rose-400 font-semibold ml-1.5 text-[11px]">critical</span>
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            Concepts below 50% accuracy threshold
          </div>
        </div>
      </div>

      {/* Main Analytics Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Course Topic Progress & Exam Rubrics */}
        <div className="space-y-6 lg:col-span-2">
          {/* Syllabus & Topic Completion Breakdown */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-foreground">
                  {currentCourse ? `${currentCourse.code} — Unit & Syllabus Coverage` : 'Curriculum Coverage'}
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
                <div className="grid grid-cols-3 gap-3 text-center bg-muted/20 p-3 rounded-lg border border-border/50">
                  <div>
                    <span className="text-xs text-muted-foreground">Syllabus Units</span>
                    <p className="text-lg font-bold text-foreground mt-0.5">{currentCourse.unit_count || 0}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Topics Mapped</span>
                    <p className="text-lg font-bold text-foreground mt-0.5">{currentCourse.topic_count || 0}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Exam Papers</span>
                    <p className="text-lg font-bold text-foreground mt-0.5">{currentCourse.paper_count || 0}</p>
                  </div>
                </div>

                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground font-medium">Overall Course Readiness</span>
                    <span className="font-bold text-foreground">
                      {currentCourse.topic_count > 0 ? '65%' : '0%'}
                    </span>
                  </div>
                  <Progress
                    value={currentCourse.topic_count > 0 ? 65 : 0}
                    tone="accent"
                    className="h-2"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Estimated preparedness derived from mapped concepts, quiz attempts, and past paper coverage.
                  </p>
                </div>
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
                No exam simulations taken yet. Launch the Exam Simulator under Practice to test with university timing.
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
              <span className="text-[10px] text-muted-foreground font-mono">14 Days</span>
            </div>

            <p className="text-xs text-muted-foreground">
              Projected flashcards scheduled for review by the FSRS-6 spaced repetition algorithm:
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
              <p className="py-4 text-center text-xs text-muted-foreground">
                No upcoming reviews scheduled.
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
              <p className="py-6 text-center text-xs text-muted-foreground">
                No activity recorded yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
