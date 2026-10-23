import { useQuery } from '@tanstack/react-query'
import { AlertCircle, AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, HelpCircle, RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { api } from '../lib/api'
import type { TopicGap } from '../lib/types'
import { Badge, Button } from '../components/ui'

export function KnowledgeGapPage() {
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null)
  const [scheduledMessage, setScheduledMessage] = useState<string | null>(null)

  const { data: summary, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['knowledge-gap-summary'],
    queryFn: () => api.knowledgeGapSummary(),
  })

  const handleSchedule = async (topic: TopicGap) => {
    try {
      await api.scheduleRevisionSession({
        topic: `Remediate: ${topic.topic_name}`,
        priority: topic.status === 'CRITICAL' ? 'HIGH' : 'MEDIUM',
        recommended_duration_min: topic.status === 'CRITICAL' ? 25 : 15,
        reason: `Targeted knowledge gap practice (${topic.accuracy_pct}% accuracy on ${topic.total_questions} questions).`,
        source_id: topic.source_id,
        concept_id: topic.topic_id,
      })
      setScheduledMessage(`Revision scheduled for "${topic.topic_name}"!`)
      setTimeout(() => setScheduledMessage(null), 4000)
    } catch {
      setScheduledMessage('Failed to schedule revision session.')
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
          <RefreshCw className="h-4 w-4 animate-spin text-[var(--accent)]" />
          Analyzing quiz error history and concept mastery…
        </div>
      </div>
    )
  }

  const topics = summary?.topics ?? []

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text)]">Knowledge Gap Detector</h1>
            <Badge tone="accent" className="text-xs">Evidence-Based</Badge>
          </div>
          <p className="text-sm text-[var(--text-muted)]">
            Algorithmic weakness identification computed from actual quiz errors and FSRS recall lapses.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          className="gap-1.5 self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh Analysis
        </Button>
      </div>

      {scheduledMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-400">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{scheduledMessage}</span>
          <Link to="/revision" className="ml-auto text-xs underline font-medium">View Revision Planner</Link>
        </div>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
            <span>Overall Accuracy</span>
            <Sparkles className="h-4 w-4 text-[var(--accent)]" />
          </div>
          <p className="mt-2 text-2xl font-bold text-[var(--text)]">
            {summary?.overall_accuracy_pct ?? 0}%
          </p>
          <p className="text-[11px] text-[var(--text-muted)] mt-1">Across all assessed topics</p>
        </div>

        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-rose-400">
            <span>Critical Gaps</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-rose-400">
            {summary?.critical_gaps_count ?? 0}
          </p>
          <p className="text-[11px] text-rose-400/80 mt-1">Accuracy below 50%</p>
        </div>

        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-amber-400">
            <span>Needs Review</span>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-amber-400">
            {summary?.moderate_gaps_count ?? 0}
          </p>
          <p className="text-[11px] text-amber-400/80 mt-1">Accuracy 50% - 69%</p>
        </div>

        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-emerald-400">
            <span>Mastered Topics</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-400">
            {summary?.mastered_count ?? 0}
          </p>
          <p className="text-[11px] text-emerald-400/80 mt-1">Accuracy 70% or higher</p>
        </div>
      </div>

      {/* Main Content: Topic List with Evidence Breakdown */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-[var(--text)]">Conceptual Breakdown & Error Evidence</h2>

        {topics.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
            <HelpCircle className="mx-auto h-8 w-8 text-[var(--text-muted)]" />
            <h3 className="mt-2 text-sm font-semibold text-[var(--text)]">No quiz attempts recorded yet</h3>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Complete quizzes from your study documents to generate real knowledge gap assessments.
            </p>
            <Link to="/quiz" className="mt-4 inline-block">
              <Button size="sm" variant="primary">Take a Quiz</Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {topics.map((topic) => {
              const isExpanded = selectedTopic === topic.topic_name
              const isCritical = topic.status === 'CRITICAL'
              const isModerate = topic.status === 'MODERATE'
              const isMastered = topic.status === 'MASTERED' || topic.status === 'PROFICIENT'

              const borderTone = isCritical
                ? 'border-rose-500/40 bg-rose-500/5'
                : isModerate
                ? 'border-amber-500/40 bg-amber-500/5'
                : isMastered
                ? 'border-emerald-500/40 bg-emerald-500/5'
                : 'border-[var(--border)] bg-[var(--bg-raised)]'

              return (
                <div
                  key={topic.topic_name}
                  className={`rounded-xl border p-4 transition-all ${borderTone}`}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                      <button
                        onClick={() => setSelectedTopic(isExpanded ? null : topic.topic_name)}
                        className="mt-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
                      >
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-[var(--text)]">{topic.topic_name}</span>
                          <Badge
                            tone={isCritical ? 'danger' : isModerate ? 'warning' : isMastered ? 'success' : 'neutral'}
                            className="text-[10px]"
                          >
                            {topic.status}
                          </Badge>
                          {topic.source_title && (
                            <span className="text-xs text-[var(--text-muted)] hidden sm:inline">
                              • {topic.source_title}
                            </span>
                          )}
                        </div>
                        {topic.definition && (
                          <p className="mt-1 text-xs text-[var(--text-muted)] line-clamp-1">
                            {topic.definition}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pl-7 sm:pl-0">
                      <div className="text-right">
                        <span className="text-sm font-bold text-[var(--text)]">{topic.accuracy_pct}%</span>
                        <p className="text-[10px] text-[var(--text-muted)]">
                          {topic.correct_questions}/{topic.total_questions} correct
                        </p>
                      </div>

                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleSchedule(topic)}
                        className="text-xs shrink-0"
                      >
                        Schedule Revision
                      </Button>
                    </div>
                  </div>

                  {/* Expanded Evidence Details */}
                  {isExpanded && (
                    <div className="mt-4 border-t border-[var(--border)] pt-3 pl-7 space-y-3">
                      {topic.definition && (
                        <div className="text-xs bg-[var(--bg-sunken)] p-2.5 rounded-lg border border-[var(--border)]">
                          <span className="font-semibold text-[var(--text)]">Concept Definition: </span>
                          <span className="text-[var(--text-muted)]">{topic.definition}</span>
                        </div>
                      )}

                      <div>
                        <h4 className="text-xs font-semibold text-[var(--text)] mb-2">
                          Error Evidence ({topic.evidence.length} incorrect answers recorded):
                        </h4>

                        {topic.evidence.length === 0 ? (
                          <p className="text-xs text-[var(--text-muted)] italic">
                            No error history recorded for this topic.
                          </p>
                        ) : (
                          <div className="space-y-2">
                            {topic.evidence.map((ev, idx) => (
                              <div
                                key={idx}
                                className="rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] p-3 text-xs space-y-1.5"
                              >
                                <p className="font-medium text-[var(--text)]">{ev.question}</p>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                                  <div className="text-rose-400">
                                    <span className="font-semibold">Your Answer: </span>
                                    <span>{ev.user_answer}</span>
                                  </div>
                                  <div className="text-emerald-400">
                                    <span className="font-semibold">Correct Answer: </span>
                                    <span>{ev.correct_answer}</span>
                                  </div>
                                </div>
                                {ev.explanation && (
                                  <p className="text-[11px] text-[var(--text-muted)] italic pt-1 border-t border-[var(--border)]/50">
                                    {ev.explanation}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
