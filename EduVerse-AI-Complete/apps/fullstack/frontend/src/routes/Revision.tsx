import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck, CheckCircle2, Clock, Plus, Trash2, ArrowRight, Sparkles, BookOpen } from 'lucide-react'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { api } from '../lib/api'
import type { RevisionRecommendation } from '../lib/types'
import { Badge, Button, Input } from '../components/ui'

export function RevisionPage() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<'ALL' | 'PENDING' | 'COMPLETED'>('ALL')
  const [isCreatingCustom, setIsCreatingCustom] = useState(false)
  const [customTopic, setCustomTopic] = useState('')
  const [customDuration, setCustomDuration] = useState(25)
  const [customPriority, setCustomPriority] = useState<'HIGH' | 'MEDIUM' | 'LOW'>('MEDIUM')
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // 1. Fetch recommendations
  const { data: recommendations = [], isLoading: loadingRecs } = useQuery({
    queryKey: ['revision-recommendations'],
    queryFn: () => api.revisionRecommendations(),
  })

  // 2. Fetch scheduled sessions
  const { data: sessions = [], isLoading: loadingSessions } = useQuery({
    queryKey: ['revision-sessions', filter],
    queryFn: () => api.revisionSessions(filter === 'ALL' ? undefined : filter),
  })

  // Mutations
  const scheduleMutation = useMutation({
    mutationFn: (data: Parameters<typeof api.scheduleRevisionSession>[0]) => api.scheduleRevisionSession(data),
    onSuccess: (newSession) => {
      queryClient.invalidateQueries({ queryKey: ['revision-sessions'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setActionSuccess(`Scheduled session: "${newSession.topic}"`)
      setTimeout(() => setActionSuccess(null), 3000)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: number; status?: string; notes?: string }) =>
      api.updateRevisionSession(id, { status, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revision-sessions'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteRevisionSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revision-sessions'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const handleScheduleRec = (rec: RevisionRecommendation) => {
    scheduleMutation.mutate({
      topic: rec.topic,
      priority: rec.priority,
      recommended_duration_min: rec.recommended_duration_min,
      reason: rec.reason,
      source_id: rec.source_id,
      concept_id: rec.concept_id,
    })
  }

  const handleCreateCustom = (e: React.FormEvent) => {
    e.preventDefault()
    if (!customTopic.trim()) return
    scheduleMutation.mutate({
      topic: customTopic.trim(),
      priority: customPriority,
      recommended_duration_min: customDuration,
      reason: 'Custom student revision plan.',
    })
    setCustomTopic('')
    setIsCreatingCustom(false)
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Adaptive Revision Planner</h1>
            <Badge tone="accent" className="text-xs">FSRS-6 + Knowledge Gap Driven</Badge>
          </div>
          <p className="text-sm text-[var(--text-muted)]">
            Personalized study intervals dynamically prioritized from test errors, memory retention, and course materials.
          </p>
        </div>
        <Button
          size="sm"
          variant="primary"
          onClick={() => setIsCreatingCustom(!isCreatingCustom)}
          className="gap-1.5 self-start sm:self-auto"
        >
          <Plus className="h-3.5 w-3.5" />
          {isCreatingCustom ? 'Cancel' : 'Plan Custom Session'}
        </Button>
      </div>

      {actionSuccess && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-400">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Custom Session Form */}
      {isCreatingCustom && (
        <form onSubmit={handleCreateCustom} className="rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-5 space-y-4">
          <h3 className="text-sm font-semibold text-[var(--text)]">Schedule Custom Revision Session</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className="text-xs text-[var(--text-muted)] block mb-1">Revision Topic / Focus Area</label>
              <Input
                placeholder="e.g. Tree Traversal Algorithms, Chapter 4 Notes..."
                value={customTopic}
                onChange={(e) => setCustomTopic(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="text-xs text-[var(--text-muted)] block mb-1">Duration (minutes)</label>
              <Input
                type="number"
                min={5}
                max={180}
                value={customDuration}
                onChange={(e) => setCustomDuration(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-3 text-xs">
              <span className="text-[var(--text-muted)]">Priority:</span>
              {(['HIGH', 'MEDIUM', 'LOW'] as const).map((p) => (
                <label key={p} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    name="priority"
                    checked={customPriority === p}
                    onChange={() => setCustomPriority(p)}
                    className="accent-[var(--accent)]"
                  />
                  <span>{p}</span>
                </label>
              ))}
            </div>
            <Button type="submit" size="sm" variant="primary" disabled={scheduleMutation.isPending}>
              Schedule Session
            </Button>
          </div>
        </form>
      )}

      {/* Recommended Sessions Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-[var(--text)] flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[var(--accent)]" />
            Recommended for Revision Today
          </h2>
          <span className="text-xs text-[var(--text-muted)]">Based on actual learning data</span>
        </div>

        {loadingRecs ? (
          <div className="p-4 text-xs text-[var(--text-muted)]">Analyzing revision priorities…</div>
        ) : recommendations.length === 0 ? (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-5 text-center text-xs text-[var(--text-muted)]">
            No urgent revisions recommended right now. All concept retention is on track!
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {recommendations.slice(0, 4).map((rec, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-4 flex flex-col justify-between space-y-3 hover:border-[var(--accent)]/40 transition-colors"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-sm text-[var(--text)]">{rec.topic}</span>
                    <Badge
                      tone={rec.priority === 'HIGH' ? 'danger' : rec.priority === 'MEDIUM' ? 'warning' : 'neutral'}
                      className="text-[10px]"
                    >
                      {rec.priority}
                    </Badge>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mt-1.5">{rec.reason}</p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]/60 text-xs">
                  <span className="text-[var(--text-muted)] flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {rec.recommended_duration_min} min session
                  </span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleScheduleRec(rec)}
                    disabled={scheduleMutation.isPending}
                    className="text-xs gap-1"
                  >
                    <span>Schedule</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Scheduled Sessions Section */}
      <div className="space-y-3 pt-2">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <h2 className="text-base font-semibold text-[var(--text)] flex items-center gap-2">
            <CalendarCheck className="h-4 w-4 text-[var(--accent)]" />
            Your Study Sessions ({sessions.length})
          </h2>

          <div className="flex items-center gap-1.5 bg-[var(--bg-raised)] p-1 rounded-lg border border-[var(--border)] text-xs">
            {(['ALL', 'PENDING', 'COMPLETED'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  filter === tab ? 'bg-[var(--accent)] text-black font-semibold' : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {loadingSessions ? (
          <div className="p-4 text-xs text-[var(--text-muted)]">Loading study sessions…</div>
        ) : sessions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center text-xs text-[var(--text-muted)]">
            No study sessions found for filter: {filter}. Schedule one from the recommendations above!
          </div>
        ) : (
          <div className="space-y-2.5">
            {sessions.map((sess) => {
              const isDone = sess.status === 'COMPLETED'
              return (
                <div
                  key={sess.id}
                  className={`rounded-xl border p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 transition-colors ${
                    isDone ? 'border-[var(--border)] bg-[var(--bg-sunken)]/60 opacity-80' : 'border-[var(--border)] bg-[var(--bg-raised)]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() =>
                        updateMutation.mutate({
                          id: sess.id,
                          status: isDone ? 'PENDING' : 'COMPLETED',
                        })
                      }
                      className="mt-0.5"
                    >
                      <CheckCircle2
                        className={`h-5 w-5 transition-colors ${
                          isDone ? 'text-emerald-400 fill-emerald-400/20' : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                        }`}
                      />
                    </button>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-sm font-semibold ${isDone ? 'line-through text-[var(--text-muted)]' : 'text-[var(--text)]'}`}>
                          {sess.topic}
                        </span>
                        <Badge tone={sess.priority === 'HIGH' ? 'danger' : sess.priority === 'MEDIUM' ? 'warning' : 'neutral'} className="text-[10px]">
                          {sess.priority}
                        </Badge>
                        <Badge tone={isDone ? 'success' : 'neutral'} className="text-[10px]">
                          {sess.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-[var(--text-muted)] mt-1">
                        {sess.reason || 'Scheduled study session'} • {sess.recommended_duration_min} mins
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    {sess.source_id && (
                      <Link to="/library/$sourceId" params={{ sourceId: String(sess.source_id) }}>
                        <Button size="sm" variant="ghost" className="text-xs gap-1">
                          <BookOpen className="h-3 w-3" />
                          View Source
                        </Button>
                      </Link>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteMutation.mutate(sess.id)}
                      className="text-xs text-rose-400 hover:text-rose-300"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
