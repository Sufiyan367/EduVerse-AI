import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  AlertCircle, AlertTriangle, ArrowRight, Brain, CalendarCheck,
  Clock, Flame, ListChecks, Mic, Plus, Sparkles, TrendingDown,
  Upload,
} from 'lucide-react'
import { api } from '../lib/api'
import { useJobs } from '../lib/store'
import { formatRelative, kindLabel } from '../lib/utils'
import { AddSourceDialog } from '../components/AddSourceDialog'
import { Badge, Button, Card, CardBody, EmptyState, Progress, Skeleton } from '../components/ui'

export function DashboardPage() {
  const navigate = useNavigate()
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

  const noProviders = !data.providers_configured.llm
  const dueTotal = data.due.due + data.due.new

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Student Dashboard</h1>
            <Badge tone="accent" className="text-xs">EduVerse AI</Badge>
          </div>
          <p className="text-sm text-[var(--text-muted)]">
            {data.totals.sources === 0
              ? 'Add your first study document or lecture notes to begin personalized learning.'
              : `${data.totals.sources} study material${data.totals.sources === 1 ? '' : 's'} · ${data.totals.cards} flashcards · ${data.totals.concepts} concepts extracted`}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/record">
            <Button variant="secondary">
              <Mic className="h-4 w-4" /> Record
            </Button>
          </Link>
          <AddSourceDialog
            trigger={
              <Button variant="primary">
                <Plus className="h-4 w-4" /> Upload Document
              </Button>
            }
          />
        </div>
      </header>

      {/* Critical Knowledge Gaps Alert */}
      {stats && stats.critical_gaps_count > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-300">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
            <div>
              <p className="font-semibold text-rose-200">
                {stats.critical_gaps_count} Critical Knowledge Gap{stats.critical_gaps_count === 1 ? '' : 's'} Identified
              </p>
              <p className="text-xs text-rose-300/80 mt-0.5">
                Quiz attempt history reveals concepts scoring below 50% accuracy.
              </p>
            </div>
          </div>
          <Link to="/knowledge-gap">
            <Button size="sm" variant="secondary" className="gap-1 border-rose-500/30 text-rose-200">
              <span>View Evidence & Remediate</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      )}

      {/* Pending Revision Sessions Alert */}
      {stats && stats.pending_revision_count > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-300">
          <div className="flex items-center gap-3">
            <CalendarCheck className="h-5 w-5 shrink-0 text-amber-400" />
            <div>
              <p className="font-semibold text-amber-200">
                {stats.pending_revision_count} Revision Session{stats.pending_revision_count === 1 ? '' : 's'} Scheduled
              </p>
              <p className="text-xs text-amber-300/80 mt-0.5">
                Adaptive study sessions queued based on memory decay and knowledge gaps.
              </p>
            </div>
          </div>
          <Link to="/revision">
            <Button size="sm" variant="secondary" className="gap-1 border-amber-500/30 text-amber-200">
              <span>Open Planner</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      )}

      {noProviders && (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardBody className="flex flex-wrap items-center gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">No language model configured yet</p>
              <p className="text-xs text-[var(--text-muted)]">
                Switch to local Ollama, LM Studio, or offline Mock in Settings to enable tutoring and card generation.
              </p>
            </div>
            <Link to="/settings">
              <Button variant="primary" size="sm">Open settings</Button>
            </Link>
          </CardBody>
        </Card>
      )}

      {/* Top 4 Core Metrics */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Due today"
          value={dueTotal}
          hint={`${data.due.due} review · ${data.due.new} new`}
          icon={Brain}
          onClick={() => navigate({ to: '/review' })}
          accent={dueTotal > 0}
        />
        <StatCard
          label="Quiz Accuracy"
          value={stats ? `${stats.average_quiz_accuracy}%` : '0%'}
          hint={stats ? `${stats.total_quiz_attempts} questions answered` : 'No attempts yet'}
          icon={ListChecks}
          onClick={() => navigate({ to: '/quiz' })}
        />
        <StatCard
          label="Mastery Index"
          value={`${Math.round(data.mastery.average_mastery * 100)}%`}
          hint={`${data.mastery.mastered}/${data.mastery.concepts} concepts mastered`}
          icon={Sparkles}
          onClick={() => navigate({ to: '/knowledge-gap' })}
        />
        <StatCard
          label="Study streak"
          value={data.stats.streak_days}
          hint={data.stats.streak_days === 1 ? 'day active' : 'days active'}
          icon={Flame}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Recent Sources List */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <h2 className="text-sm font-semibold text-[var(--text)]">Recent Study Materials</h2>
            <Link to="/library" className="text-xs text-[var(--accent)] hover:underline">
              View all
            </Link>
          </div>
          {data.recent_sources.length === 0 ? (
            <EmptyState
              icon={Upload}
              title="No study materials yet"
              description="Upload lecture PDFs, slides, or notes to extract concepts, generate quizzes, and start learning."
              action={<AddSourceDialog trigger={<Button variant="primary">Add your first source</Button>} />}
            />
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {data.recent_sources.map((source) => (
                <li key={source.id}>
                  <Link
                    to="/library/$sourceId"
                    params={{ sourceId: String(source.id) }}
                    className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-[var(--bg-sunken)]"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[var(--text)]">{source.title}</p>
                      <p className="text-xs text-[var(--text-muted)]">
                        {kindLabel(source.kind)} · {formatRelative(source.created_at)}
                      </p>
                    </div>
                    <StatusBadge status={source.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Knowledge Health / Weak Concepts */}
        <Card>
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-[var(--text-muted)]" />
              <h2 className="text-sm font-semibold text-[var(--text)]">Focus Areas</h2>
            </div>
            <Link to="/knowledge-gap" className="text-xs text-[var(--accent)] hover:underline">
              Gap Details
            </Link>
          </div>
          {data.weak_concepts.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-[var(--text-muted)]">
              {data.totals.concepts === 0
                ? 'Concepts appear once a study document has been uploaded.'
                : 'All concepts are currently above the mastery threshold.'}
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {data.weak_concepts.map((concept) => (
                <li key={concept.id} className="px-4 py-2.5">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="truncate text-sm font-medium text-[var(--text)]">{concept.name}</p>
                    <span className="shrink-0 tabular-nums text-xs text-[var(--text-muted)]">
                      {Math.round(concept.mastery * 100)}%
                    </span>
                  </div>
                  <Progress
                    value={concept.mastery * 100}
                    tone={concept.mastery < 0.35 ? 'danger' : 'accent'}
                    className="mt-1.5"
                  />
                  <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">
                    {concept.source_title}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {data.weak_concepts.length > 0 && (
            <div className="border-t border-[var(--border)] p-3 flex gap-2">
              <Link to="/quiz" className="flex-1">
                <Button variant="secondary" size="sm" className="w-full justify-center">
                  Take Quiz
                </Button>
              </Link>
              <Link to="/revision" className="flex-1">
                <Button variant="primary" size="sm" className="w-full justify-center">
                  Plan Revision
                </Button>
              </Link>
            </div>
          )}
        </Card>
      </div>

      {/* Real Chronological Activity Timeline */}
      {stats && stats.recent_activities.length > 0 && (
        <Card>
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-[var(--text-muted)]" />
              <h2 className="text-sm font-semibold text-[var(--text)]">Recent Learning History</h2>
            </div>
            <span className="text-xs text-[var(--text-muted)]">Real operations</span>
          </div>
          <div className="divide-y divide-[var(--border)] px-4 py-2">
            {stats.recent_activities.map((act) => (
              <div key={act.id} className="flex items-center justify-between py-2.5 text-xs">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="h-2 w-2 rounded-full bg-[var(--accent)] shrink-0" />
                  <span className="font-medium text-[var(--text)] truncate">{act.title}</span>
                  <Badge tone="neutral" className="text-[10px] hidden sm:inline-block">
                    {act.entity_type}
                  </Badge>
                </div>
                <span className="text-[11px] text-[var(--text-muted)] shrink-0 ml-2">
                  {formatRelative(act.created_at)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

function StatCard({
  label, value, hint, icon: Icon, onClick, accent,
}: {
  label: string
  value: string | number
  hint?: string
  icon: React.ComponentType<{ className?: string }>
  onClick?: () => void
  accent?: boolean
}) {
  const inner = (
    <CardBody className="flex items-start gap-3">
      <span
        className={
          accent
            ? 'rounded-lg bg-[var(--accent-soft)] p-2 text-[var(--accent)]'
            : 'rounded-lg bg-[var(--bg-sunken)] p-2 text-[var(--text-muted)]'
        }
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-xs text-[var(--text-muted)]">{label}</p>
        <p className="text-xl font-semibold tabular-nums">{value}</p>
        {hint && <p className="truncate text-[11px] text-[var(--text-muted)]">{hint}</p>}
      </div>
    </CardBody>
  )
  return onClick ? (
    <Card className="cursor-pointer transition-colors hover:border-[var(--accent)]/40" onClick={onClick}>
      {inner}
    </Card>
  ) : (
    <Card>{inner}</Card>
  )
}

export function StatusBadge({ status }: { status: string }) {
  if (status === 'ready') return <Badge tone="success">ready</Badge>
  if (status === 'failed') return <Badge tone="danger">failed</Badge>
  if (status === 'processing') return <Badge tone="accent">processing</Badge>
  if (status === 'recording') return <Badge tone="warning">recording</Badge>
  return <Badge>{status}</Badge>
}
