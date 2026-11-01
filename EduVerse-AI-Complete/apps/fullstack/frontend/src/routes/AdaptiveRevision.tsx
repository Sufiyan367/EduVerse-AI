import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { CalendarCheck, Target, CheckCircle, Clock, Sparkles, Brain, ListChecks } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Button,  } from '../components/ui'

export function AdaptiveRevisionPage() {
  const queryClient = useQueryClient()
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams()

  const { data: courses = [] } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(() => {
    const cid = urlParams.get('courseId'); if (cid) return Number(cid)
    return null
  })

  useEffect(() => {
    if (!selectedCourseId && courses.length > 0) {
      setSelectedCourseId(courses[0].id)
    }
  }, [courses, selectedCourseId])

  // Mastery Profile Query
  const { data: masteryProfile, isLoading: masteryLoading } = useQuery({
    queryKey: ['adaptive-mastery', selectedCourseId],
    queryFn: () => (selectedCourseId ? api.getMasteryProfile(selectedCourseId) : null),
    enabled: !!selectedCourseId,
  })

  // Active Plan Query
  const { data: planData } = useQuery({
    queryKey: ['adaptive-plan', selectedCourseId],
    queryFn: () => (selectedCourseId ? api.getCurrentPlan(selectedCourseId) : null),
    enabled: !!selectedCourseId,
  })

  // Generate Plan Mutation
  const generatePlanMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId) throw new Error('Select a course first')
      return api.generateAdaptivePlan(selectedCourseId, {
        title: 'Targeted Exam Mastery Plan',
      })
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['adaptive-plan', selectedCourseId] })
      toast.success(`Personalized plan generated with ${data.tasks_generated || 0} high-priority tasks!`)
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to generate plan')
    },
  })

  // Toggle Task Mutation
  const toggleTaskMutation = useMutation({
    mutationFn: (taskId: number) => api.toggleTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adaptive-plan', selectedCourseId] })
    },
  })

  // Remediate Task Mutation
  const remediateTaskMutation = useMutation({
    mutationFn: ({ taskId, actionType }: { taskId: number; actionType: string }) =>
      api.remediateTask(taskId, { action_type: actionType, delta: 0.15 }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adaptive-mastery', selectedCourseId] })
      queryClient.invalidateQueries({ queryKey: ['adaptive-plan', selectedCourseId] })
      toast.success('Remediation completed! Topic mastery boosted by +15%')
    },
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <CalendarCheck className="h-7 w-7 text-primary" />
            Adaptive Revision & Student Mastery Graph
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Topic knowledge gap analysis, exam urgency weighting, and personalized remedial study tasks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedCourseId || ''}
            onChange={(e) => setSelectedCourseId(Number(e.target.value))}
            className="h-9 px-3 py-1 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
          >
            {courses.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.code}: {c.name}
              </option>
            ))}
          </select>

          <Button
            onClick={() => generatePlanMutation.mutate()}
            disabled={generatePlanMutation.isPending}
            className="flex items-center gap-2"
          >
            <Sparkles className="h-4 w-4" />
            {generatePlanMutation.isPending ? 'Optimizing...' : 'Generate Adaptive Plan'}
          </Button>
        </div>
      </div>

      {masteryLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 rounded-xl border border-border bg-card animate-pulse" />
          ))}
        </div>
      ) : !masteryProfile ? (
        <div className="text-center py-16 border border-dashed border-border rounded-xl bg-card/50">
          <Target className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4" />
          <h3 className="text-lg font-medium text-foreground">Select a course to view mastery graph</h3>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Top Metrics Row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Overall Course Mastery</div>
              <div className="text-2xl font-bold text-primary mt-1">
                {masteryProfile.overall_mastery_percentage}%
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Syllabus Topics Tracked</div>
              <div className="text-2xl font-bold text-foreground mt-1">{masteryProfile.total_topics}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">High-Confidence Topics</div>
              <div className="text-2xl font-bold text-emerald-500 mt-1">
                {masteryProfile.strong_topics_count}
              </div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Knowledge Gaps (Needs Work)</div>
              <div className="text-2xl font-bold text-amber-500 mt-1">{masteryProfile.weak_topics_count}</div>
            </div>
          </div>

          {/* Active Adaptive Plan Tasks */}
          <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border bg-muted/20 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <Target className="h-4 w-4 text-primary" />
                  {planData?.has_plan ? planData.title : 'Personalized Daily Revision Tasks'}
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Ordered by exam weightage and student mastery deficiency.
                </p>
              </div>
              {planData?.has_plan && (
                <div className="text-xs font-semibold text-primary font-mono">
                  {planData.completion_rate}% Complete
                </div>
              )}
            </div>

            <div className="p-6">
              {!planData?.has_plan || planData.tasks.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-xs text-muted-foreground mb-4">
                    No active revision plan generated yet for this course. Click below to synthesize tasks.
                  </p>
                  <Button onClick={() => generatePlanMutation.mutate()} size="sm">
                    Generate Plan Now
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {planData.tasks.map((t: any) => (
                    <div
                      key={t.id}
                      className={`flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 rounded-xl border transition-all ${
                        t.is_completed
                          ? 'bg-muted/20 border-border/60 opacity-60'
                          : 'bg-card border-border hover:border-primary/40 shadow-sm'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <button
                          onClick={() => toggleTaskMutation.mutate(t.id)}
                          className={`mt-0.5 h-5 w-5 rounded flex items-center justify-center border transition-colors ${
                            t.is_completed
                              ? 'bg-primary text-primary-foreground border-primary'
                              : 'border-muted-foreground/40 hover:border-primary'
                          }`}
                        >
                          {t.is_completed && <CheckCircle className="h-4 w-4" />}
                        </button>
                        <div>
                          <div
                            className={`text-sm font-semibold text-foreground ${
                              t.is_completed ? 'line-through text-muted-foreground' : ''
                            }`}
                          >
                            {t.title}
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                                t.priority === 1
                                  ? 'bg-rose-500/15 text-rose-500'
                                  : t.priority === 2
                                  ? 'bg-amber-500/15 text-amber-500'
                                  : 'bg-blue-500/15 text-blue-500'
                              }`}
                            >
                              Priority {t.priority}
                            </span>
                            <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {t.estimated_minutes} mins
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Remediation Action Buttons */}
                      {!t.is_completed && (
                        <div className="flex items-center gap-2 mt-3 sm:mt-0 pt-2 sm:pt-0 border-t sm:border-0 border-border">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              remediateTaskMutation.mutate({
                                taskId: t.id,
                                actionType: 'flashcards',
                              })
                            }
                            className="h-8 text-xs gap-1"
                          >
                            <Brain className="h-3.5 w-3.5 text-purple-500" />
                            Flashcards Drill
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              remediateTaskMutation.mutate({
                                taskId: t.id,
                                actionType: 'mini_quiz',
                              })
                            }
                            className="h-8 text-xs gap-1"
                          >
                            <ListChecks className="h-3.5 w-3.5 text-emerald-500" />
                            Quick Quiz
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Detailed Unit Mastery Profile Breakdown */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm space-y-6">
            <h3 className="text-base font-semibold text-foreground">Unit Mastery Distribution</h3>
            <div className="space-y-6">
              {masteryProfile.units.map((u: any) => (
                <div key={u.unit_number} className="space-y-3">
                  <div className="flex justify-between items-center text-xs font-semibold">
                    <span className="text-foreground">
                      Unit {u.unit_number}: {u.unit_title}
                    </span>
                    <span className="text-primary font-mono">{Math.round(u.average_mastery * 100)}% Mastery</span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        u.average_mastery >= 0.75
                          ? 'bg-emerald-500'
                          : u.average_mastery >= 0.5
                          ? 'bg-primary'
                          : 'bg-amber-500'
                      }`}
                      style={{ width: `${Math.max(5, u.average_mastery * 100)}%` }}
                    />
                  </div>

                  {/* Topic pills */}
                  <div className="flex flex-wrap gap-2 pt-1">
                    {u.topics.map((top: any) => (
                      <span
                        key={top.id}
                        className={`text-[11px] px-2.5 py-1 rounded-md border flex items-center gap-1.5 ${
                          top.mastery_score >= 0.75
                            ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                            : top.mastery_score >= 0.5
                            ? 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                            : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                        }`}
                      >
                        <span>{top.name}</span>
                        <strong className="font-mono text-[10px]">{Math.round(top.mastery_score * 100)}%</strong>
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
