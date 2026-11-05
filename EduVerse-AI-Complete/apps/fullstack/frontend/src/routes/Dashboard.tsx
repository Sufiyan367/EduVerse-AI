import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  AlertCircle, ArrowRight, BookOpen, Brain, CalendarCheck,
  CheckCircle2, Clock, Layers, ListChecks, MessageSquare,
  Plus, Sparkles, TrendingDown, Zap
} from 'lucide-react'
import { api } from '../lib/api'
import { useJobs, useActiveCourse } from '../lib/store'
import { formatRelative, kindLabel } from '../lib/utils'
import { AddSourceDialog } from '../components/AddSourceDialog'
import { Badge, Button, Progress, Skeleton } from '../components/ui'

export function DashboardPage() {
  const { activeCourseId } = useActiveCourse()
  const jobs = useJobs((state) => state.jobs)
  const activeCount = Object.values(jobs).filter(
    (job) => job.parent_id == null && (job.status === 'running' || job.status === 'queued'),
  ).length

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.dashboard(),
    refetchInterval: (query) => {
      const hasProcessing = query.state.data?.recent_sources?.some(
        (s) => s.status === 'processing' || s.status === 'pending'
      )
      return hasProcessing || activeCount > 0 ? 2500 : 30_000
    },
  })

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.dashboardStats(),
    refetchInterval: 30_000,
  })

  const { data: courses = [] } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  const activeCourse = courses.find((c: any) => c.id === activeCourseId) || courses[0] || null

  const { data: activeCourseProgress } = useQuery({
    queryKey: ['course-progress', activeCourse?.id],
    queryFn: () => api.getCourseProgress(activeCourse!.id),
    enabled: !!activeCourse?.id,
  })

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6">
        <Skeleton className="h-9 w-52" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  const user = typeof localStorage !== 'undefined' && localStorage.getItem('eduverse_user')
    ? JSON.parse(localStorage.getItem('eduverse_user') || '{}')
    : null
  const studentName = user?.full_name || user?.username || 'Student'

  const dueTotal = (data.due?.due || 0) + (data.due?.new || 0)
// activeCourse defined above

  // Determine top priority action
  let primaryAction = {
    title: 'Review Due Flashcards',
    description: `${dueTotal} card${dueTotal === 1 ? '' : 's'} scheduled for spaced repetition review today.`,
    buttonText: 'Start Flashcard Review',
    icon: Brain,
    to: '/practice',
    search: { tab: 'flashcards' },
    active: dueTotal > 0,
  }

  if (dueTotal === 0 && stats && stats.critical_gaps_count > 0) {
    primaryAction = {
      title: 'Remediate Critical Knowledge Gaps',
      description: `${stats.critical_gaps_count} concept${stats.critical_gaps_count === 1 ? '' : 's'} scoring below 50% accuracy need attention.`,
      buttonText: 'Resolve Gaps Now',
      icon: AlertCircle,
      to: '/practice',
      search: { tab: 'gaps' },
      active: true,
    }
  } else if (dueTotal === 0 && (!stats || stats.critical_gaps_count === 0) && activeCourse) {
    primaryAction = {
      title: `Continue ${activeCourse.code}: ${activeCourse.name}`,
      description: `Resume curriculum study with ${activeCourse.unit_count || 0} units and past paper intelligence.`,
      buttonText: 'Open Course Workspace',
      icon: BookOpen,
      to: '/courses',
      search: { courseId: activeCourse.id, tab: 'overview' } as any,
      active: true,
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      {/* Launchpad Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Welcome back, {studentName}
            </h1>
            <Badge tone="accent" className="text-xs">Academic Launchpad</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            {courses.length > 0
              ? `${courses.length} active course workspace${courses.length === 1 ? '' : 's'} · ${data.totals.sources} materials indexed · ${dueTotal} review items due`
              : 'Add your university courses and study materials to begin personalized learning.'}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/chat">
            <Button variant="secondary" size="sm" className="gap-1.5 text-xs">
              <MessageSquare className="h-4 w-4 text-primary" />
              <span>Ask Tutor</span>
            </Button>
          </Link>
          <AddSourceDialog
            trigger={
              <Button variant="primary" size="sm" className="gap-1.5 text-xs shadow-sm">
                <Plus className="h-4 w-4" />
                <span>Upload PDF</span>
              </Button>
            }
          />
        </div>
      </div>

      {/* Primary Action Hero: What one thing should I do next? */}
      <div className="rounded-2xl border border-primary/30 bg-gradient-to-r from-primary/10 via-card to-card p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="flex items-start gap-4">
            <div className="p-3 rounded-xl bg-primary/20 text-primary shrink-0 mt-0.5">
              <primaryAction.icon className="h-6 w-6" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary uppercase tracking-wide">
                <Zap className="h-3.5 w-3.5" />
                Recommended Next Step
              </div>
              <h2 className="text-lg font-bold text-foreground mt-0.5">
                {primaryAction.title}
              </h2>
              <p className="text-sm text-muted-foreground mt-1 max-w-xl">
                {primaryAction.description}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Link to={primaryAction.to as any} search={primaryAction.search as any}>
              <Button size="md" className="gap-2 shadow-sm font-semibold">
                <span>{primaryAction.buttonText}</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Active Course Card + Daily Action Plan Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Active Course Context & Quick Switcher */}
        <div className="space-y-4 lg:col-span-1">
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground uppercase tracking-wider">
                <BookOpen className="h-4 w-4 text-primary" />
                Active Course
              </div>
              <Link to="/courses" className="text-xs text-primary hover:underline font-medium">
                All Courses ({courses.length})
              </Link>
            </div>

            {activeCourse ? (
              <div className="space-y-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge tone="accent" className="font-mono text-xs font-bold">
                      {activeCourse.code}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{activeCourse.semester}</span>
                  </div>
                  <h3 className="text-base font-bold text-foreground mt-1 line-clamp-1">
                    {activeCourse.name}
                  </h3>
                </div>

                {/* Truthful Readiness & Lifecycle Summary */}
                <div className="p-3 rounded-lg bg-muted/30 border border-border/70 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground font-medium">Exam Readiness:</span>
                    {activeCourseProgress?.readiness_percentage !== null && activeCourseProgress?.readiness_percentage !== undefined ? (
                      <span className="font-bold text-primary">
                        {Math.round(activeCourseProgress.readiness_percentage)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground font-medium text-[11px]">Not enough data</span>
                    )}
                  </div>
                  {activeCourseProgress?.readiness_percentage !== null && activeCourseProgress?.readiness_percentage !== undefined && (
                    <div className="w-full bg-muted/80 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-primary h-1.5 rounded-full"
                        style={{ width: `${Math.min(100, Math.max(0, activeCourseProgress.readiness_percentage))}%` }}
                      />
                    </div>
                  )}
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                    <span>Mastered: <strong className="text-foreground">{activeCourseProgress?.topics_by_status?.mastered || 0}</strong></span>
                    <span>Learning: <strong className="text-foreground">{(activeCourseProgress?.topics_by_status?.learning || 0) + (activeCourseProgress?.topics_by_status?.practicing || 0)}</strong></span>
                    <span>Review: <strong className="text-foreground">{activeCourseProgress?.topics_by_status?.needs_review || 0}</strong></span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 py-1.5 text-center text-xs">
                  <div>
                    <span className="font-bold text-foreground text-xs">{activeCourse.unit_count || 0}</span>
                    <span className="block text-[10px] text-muted-foreground">Units</span>
                  </div>
                  <div>
                    <span className="font-bold text-foreground text-xs">{activeCourse.topic_count || 0}</span>
                    <span className="block text-[10px] text-muted-foreground">Topics</span>
                  </div>
                  <div>
                    <span className="font-bold text-foreground text-xs">{activeCourse.paper_count || 0}</span>
                    <span className="block text-[10px] text-muted-foreground">Papers</span>
                  </div>
                </div>

                <div className="pt-1 flex flex-col gap-2">
                  <Link
                    to="/courses"
                    search={{ courseId: activeCourse.id, tab: 'syllabus' } as any}
                    className="flex items-center justify-between p-2 rounded-lg bg-muted/40 hover:bg-muted text-xs font-medium text-foreground transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Layers className="h-3.5 w-3.5 text-primary" />
                      Open Syllabus & Topics
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </Link>
                  <Link
                    to="/courses"
                    search={{ courseId: activeCourse.id, tab: 'simulator' } as any}
                    className="flex items-center justify-between p-2 rounded-lg bg-muted/40 hover:bg-muted text-xs font-medium text-foreground transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                      Exam Simulator
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </Link>
                </div>
              </div>
            ) : (
              <div className="text-center py-6">
                <p className="text-xs text-muted-foreground mb-3">No course workspace created yet.</p>
                <Link to="/courses">
                  <Button size="sm" variant="secondary" className="text-xs">
                    Create Course Workspace
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {/* Quick Tutor Prompt Card */}
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <MessageSquare className="h-4 w-4 text-teal-400" />
              <span>Ask Academic Tutor</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Ground your queries on indexed lecture PDFs and course notes with exact citations.
            </p>
            <div className="space-y-1.5">
              <Link
                to="/chat"
                className="block text-xs p-2 rounded-lg border border-border/60 hover:border-primary/40 text-muted-foreground hover:text-foreground transition-colors"
              >
                &ldquo;What are the most frequent exam questions in my active course?&rdquo;
              </Link>
              <Link
                to="/chat"
                className="block text-xs p-2 rounded-lg border border-border/60 hover:border-primary/40 text-muted-foreground hover:text-foreground transition-colors"
              >
                &ldquo;Summarize Unit 1 core definitions and provide key formulas.&rdquo;
              </Link>
            </div>
          </div>
        </div>

        {/* Right 2 Columns: Today's Action Items & Weak Concepts */}
        <div className="space-y-4 lg:col-span-2">
          {/* Today's Concrete Action Plan */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-foreground">Today&apos;s Academic Plan</h2>
              </div>
              <span className="text-xs text-muted-foreground font-mono">
                {new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
              </span>
            </div>

            <div className="space-y-2.5">
              {/* Task 1: Due Flashcards */}
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/70 bg-muted/20 hover:bg-muted/40 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`p-2 rounded-lg ${dueTotal > 0 ? 'bg-amber-500/10 text-amber-500' : 'bg-emerald-500/10 text-emerald-400'}`}>
                    <Brain className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-foreground truncate">
                      {dueTotal > 0 ? `${dueTotal} Due Spaced-Repetition Cards` : 'Spaced Repetition Complete'}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {dueTotal > 0 ? 'FSRS-6 algorithm review to retain key formulas' : 'All scheduled flashcards completed for today'}
                    </p>
                  </div>
                </div>
                <Link to="/practice" search={{ tab: 'flashcards' } as any}>
                  <Button size="sm" variant={dueTotal > 0 ? 'primary' : 'secondary'} className="text-xs shrink-0">
                    {dueTotal > 0 ? 'Review' : 'Practice'}
                  </Button>
                </Link>
              </div>

              {/* Task 2: Quiz Knowledge Gaps */}
              {stats && stats.critical_gaps_count > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 hover:bg-rose-500/10 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
                      <AlertCircle className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-rose-200 truncate">
                        {stats.critical_gaps_count} Low-Mastery Concepts Identified
                      </p>
                      <p className="text-[11px] text-rose-300/80">
                        Accuracy below 50% in past quizzes
                      </p>
                    </div>
                  </div>
                  <Link to="/practice" search={{ tab: 'gaps' } as any}>
                    <Button size="sm" variant="secondary" className="text-xs border-rose-500/30 text-rose-200 shrink-0">
                      Strengthen
                    </Button>
                  </Link>
                </div>
              )}

              {/* Task 3: Adaptive Revision */}
              {stats && stats.pending_revision_count > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
                      <CalendarCheck className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-amber-200 truncate">
                        {stats.pending_revision_count} Adaptive Revision Session Scheduled
                      </p>
                      <p className="text-[11px] text-amber-300/80">
                        Calculated from memory decay and previous exam performance
                      </p>
                    </div>
                  </div>
                  <Link to="/practice" search={{ tab: 'adaptive' } as any}>
                    <Button size="sm" variant="secondary" className="text-xs border-amber-500/30 text-amber-200 shrink-0">
                      Start Session
                    </Button>
                  </Link>
                </div>
              )}

              {/* Task 4: Practice Quiz */}
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/70 bg-muted/20 hover:bg-muted/40 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary">
                    <ListChecks className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-foreground truncate">
                      Evidence-Grounded Practice Quiz
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Test concept comprehension with citations from uploaded materials
                    </p>
                  </div>
                </div>
                <Link to="/practice" search={{ tab: 'quiz' } as any}>
                  <Button size="sm" variant="secondary" className="text-xs shrink-0">
                    Generate Quiz
                  </Button>
                </Link>
              </div>
            </div>
          </div>

          {/* Weak Topics & Knowledge Gaps Section */}
          <div className="rounded-xl border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-amber-500" />
                <h2 className="text-sm font-semibold text-foreground">Weak Concepts & Gaps</h2>
              </div>
              <Link to="/practice" search={{ tab: 'gaps' } as any} className="text-xs text-primary hover:underline">
                View all gaps
              </Link>
            </div>

            {data.weak_concepts.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                {data.totals.concepts === 0
                  ? 'Concepts appear once study documents have been indexed.'
                  : 'All concepts currently exceed the 60% mastery threshold.'}
              </p>
            ) : (
              <div className="space-y-3">
                {data.weak_concepts.slice(0, 3).map((concept) => (
                  <div key={concept.id} className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-foreground truncate">{concept.name}</span>
                      <span className="text-xs font-mono font-medium text-amber-500">
                        {Math.round(concept.mastery * 100)}% mastery
                      </span>
                    </div>
                    <Progress
                      value={concept.mastery * 100}
                      tone={concept.mastery < 0.4 ? 'danger' : 'accent'}
                      className="mt-1.5 h-1.5"
                    />
                    <div className="flex items-center justify-between mt-1 text-[11px] text-muted-foreground">
                      <span className="truncate">{concept.source_title}</span>
                      <Link
                        to="/practice"
                        search={{ tab: 'quiz' } as any}
                        className="text-primary hover:underline font-medium"
                      >
                        Practice topic &rarr;
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Materials & Real Activity Feed */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recent Study Materials */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <h2 className="text-sm font-semibold text-foreground">Recent Study Materials</h2>
            <Link to="/library" className="text-xs text-primary hover:underline">
              Library ({data.totals.sources})
            </Link>
          </div>

          {data.recent_sources.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              No study materials yet. Upload lecture notes or PDFs above.
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {data.recent_sources.slice(0, 4).map((source) => (
                <li key={source.id}>
                  <Link
                    to="/library/$sourceId"
                    params={{ sourceId: String(source.id) }}
                    className="flex items-center justify-between gap-3 py-2.5 hover:bg-muted/30 px-2 rounded-md transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-foreground">{source.title}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {kindLabel(source.kind)} · {formatRelative(source.created_at)}
                      </p>
                    </div>
                    <StatusBadge status={source.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Real Chronological Activity Stream */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Recent Activity</h2>
            </div>
            <Link to="/progress" className="text-xs text-primary hover:underline">
              Full Analytics
            </Link>
          </div>

          {stats && stats.recent_activities.length > 0 ? (
            <div className="divide-y divide-border/60">
              {stats.recent_activities.slice(0, 4).map((act) => (
                <div key={act.id} className="flex items-center justify-between py-2.5 text-xs px-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                    <span className="font-medium text-foreground truncate">{act.title}</span>
                  </div>
                  <span className="text-[11px] text-muted-foreground shrink-0 ml-2">
                    {formatRelative(act.created_at)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-muted-foreground">
              No recent activity recorded yet.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function StatusBadge({ status }: { status: string }) {
  if (status === 'ready') return <Badge tone="success">ready</Badge>
  if (status === 'partially_processed') return <Badge tone="warning">partial</Badge>
  if (status === 'failed') return <Badge tone="danger">failed</Badge>
  if (status === 'processing') return <Badge tone="accent">processing</Badge>
  if (status === 'recording') return <Badge tone="warning">recording</Badge>
  return <Badge>{status}</Badge>
}
