import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, CheckCircle2, Clock, Cpu, Database,
  Layers, Play, RefreshCw, RotateCcw, Server, ShieldCheck,
  ToggleLeft, ToggleRight, XCircle, Sparkles, Eye,
} from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Badge, Button, Modal } from '../components/ui'
import { cn } from '../lib/utils'

export function AutomationCenterPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'all' | 'running' | 'queued' | 'succeeded' | 'failed' | 'review'>('all')
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [detailModalOpen, setDetailModalOpen] = useState(false)

  // 1. Fetch system health
  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 5000,
  })

  // 2. Fetch jobs & counts with 3s polling fallback
  const { data: jobsData, refetch: refetchJobs } = useQuery({
    queryKey: ['automation-jobs', activeTab],
    queryFn: () => api.getAutomationJobs({
      status: activeTab === 'all' || activeTab === 'review' ? undefined : activeTab,
      limit: 100,
    }),
    refetchInterval: 3000,
  })

  // 3. Fetch automation rules
  const { data: rules = [] } = useQuery({
    queryKey: ['automation-rules'],
    queryFn: () => api.getAutomationRules(),
  })

  // 4. Fetch evidence audit issues
  const { data: auditIssues = [], refetch: refetchAudit } = useQuery({
    queryKey: ['automation-audit-issues'],
    queryFn: () => api.getAuditIssues('open'),
    refetchInterval: 5000,
  })

  // 5. Fetch user notifications
  const { refetch: refetchNotifs } = useQuery({
    queryKey: ['automation-notifications'],
    queryFn: () => api.getNotifications(),
    refetchInterval: 6000,
  })

  // Mutations
  const toggleRuleMutation = useMutation({
    mutationFn: ({ ruleName, isEnabled }: { ruleName: string; isEnabled: boolean }) =>
      api.toggleAutomationRule(ruleName, { is_enabled: isEnabled }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['automation-rules'] })
      toast.success(`Rule '${vars.ruleName}' ${vars.isEnabled ? 'enabled' : 'disabled'}`)
    },
    onError: (err: any) => toast.error(err.message || 'Failed to update rule'),
  })

  const retryJobMutation = useMutation({
    mutationFn: (jobId: number) => api.retryAutomationJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
      toast.success('Job requeued for execution')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to retry job'),
  })

  const cancelJobMutation = useMutation({
    mutationFn: (jobId: number) => api.cancelAutomationJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
      toast.info('Job cancelled')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to cancel job'),
  })

  const triggerWorkflowMutation = useMutation({
    mutationFn: (eventName: string) => api.triggerAutomationWorkflow({ event_name: eventName }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['automation-jobs'] })
      toast.success(`Workflow triggered (Job #${data.job_id})`)
    },
    onError: (err: any) => toast.error(err.message || 'Failed to trigger workflow'),
  })

  const resolveAuditMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) => api.resolveAuditIssue(id, action),
    onSuccess: () => {
      refetchAudit()
      toast.success('Audit issue updated')
    },
    onError: (err: any) => toast.error(err.message || 'Failed to resolve issue'),
  })

  const jobsList = jobsData?.jobs || []
  const counts = jobsData?.counts || { all: 0, queued: 0, running: 0, failed: 0, succeeded: 0, review_required: 0 }
  const selectedJob = jobsList.find((j: any) => j.id === selectedJobId)

  return (
    <div className="space-y-8 p-6 max-w-7xl mx-auto">
      {/* 1. Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/40 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Automation Center</h1>
            <Badge tone="accent" className="text-xs">
              Autonomous v2.4
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Real background engine executing syllabus intelligence, paper analytics, adaptive drills, and data audits.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              refetchJobs()
              refetchAudit()
              refetchNotifs()
              toast.info('Refreshed queue status')
            }}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => triggerWorkflowMutation.mutate('audit_check_due')}
            disabled={triggerWorkflowMutation.isPending}
          >
            <ShieldCheck className="w-3.5 h-3.5 mr-1.5 text-blue-500" />
            Run Audit
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => triggerWorkflowMutation.mutate('scheduled_revision_due')}
            disabled={triggerWorkflowMutation.isPending}
          >
            <Play className="w-3.5 h-3.5 mr-1.5" />
            Run Daily Revision
          </Button>
        </div>
      </div>

      {/* 2. System Health Status Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Web Server */}
        <div className="p-4 rounded-xl border border-border/60 bg-card/50 shadow-sm flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Server className="w-4 h-4 text-emerald-500" />
              Web Server
            </div>
            <div className="mt-2 text-base font-semibold text-foreground">
              {health?.server?.status === 'healthy' ? 'Operational' : 'Starting...'}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              FastAPI {health?.server?.version || 'v2.4.0'} • Port 8080
            </div>
          </div>
          <span className="flex h-2.5 w-2.5 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
        </div>

        {/* PostgreSQL Database */}
        <div className="p-4 rounded-xl border border-border/60 bg-card/50 shadow-sm flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Database className="w-4 h-4 text-blue-500" />
              PostgreSQL
            </div>
            <div className="mt-2 text-base font-semibold text-foreground">
              {health?.database?.status === 'healthy' ? 'PostgreSQL 18.6' : 'Connecting...'}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              DB: {health?.database?.database_name || 'eduverse_db'} • SKIP LOCKED
            </div>
          </div>
          <Badge tone="accent" className="text-[10px]">
            DBeaver Ready
          </Badge>
        </div>

        {/* Worker Pool */}
        <div className="p-4 rounded-xl border border-border/60 bg-card/50 shadow-sm flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Activity className="w-4 h-4 text-indigo-500" />
              Worker Pool
            </div>
            <div className="mt-2 text-base font-semibold text-foreground">
              {health?.worker?.status === 'healthy' ? 'Active Workers' : 'Idle'}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              Queue: {health?.worker?.queue_depth ?? 0} • Concurrency: 1 LLM / 2 CPU
            </div>
          </div>
          <Badge tone="neutral" className="text-[10px]">
            {health?.worker?.registered_handlers_count || 20} Handlers
          </Badge>
        </div>

        {/* Local Ollama LLM */}
        <div className="p-4 rounded-xl border border-border/60 bg-card/50 shadow-sm flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <Cpu className="w-4 h-4 text-purple-500" />
              Local AI Engine
            </div>
            <div className="mt-2 text-base font-semibold text-foreground">
              {health?.ollama?.status === 'healthy' ? 'Ollama Online' : 'Offline / Standby'}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {health?.ollama?.active_model || 'qwen3.5:4b'} • RTX 3050 GPU
            </div>
          </div>
          <Badge
            tone={health?.ollama?.status === 'healthy' ? 'accent' : 'warning'}
            className="text-[10px]"
          >
            {health?.ollama?.status === 'healthy' ? 'GPU Ready' : 'Standby'}
          </Badge>
        </div>
      </div>

      {/* 3. Next Scheduled Automations */}
      <div className="rounded-xl border border-border/60 bg-card/30 p-5">
        <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-primary" />
          Scheduled Autonomous Tasks
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 flex items-start gap-3">
            <span className="text-xl">🌅</span>
            <div>
              <div className="text-sm font-medium text-foreground">Daily Adaptive Drill</div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Every morning at 07:00 IST (Asia/Kolkata). Prioritizes weak topics & exam targets.
              </p>
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" /> Next trigger: Tomorrow 07:00 IST
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 flex items-start gap-3">
            <span className="text-xl">📊</span>
            <div>
              <div className="text-sm font-medium text-foreground">Weekly Academic Intelligence</div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Every Sunday at 20:00 IST. Aggregates weekly mastery deltas and repeated mistakes.
              </p>
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-primary font-medium">
                <Clock className="w-3.5 h-3.5" /> Scheduled for Sunday 20:00 IST
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 flex items-start gap-3">
            <span className="text-xl">🔍</span>
            <div>
              <div className="text-sm font-medium text-foreground">Data Quality & Citation Audit</div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Runs automatically on ingestion. Verifies page bounds, topic links & rubric integrity.
              </p>
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-blue-600 dark:text-blue-400 font-medium">
                <ShieldCheck className="w-3.5 h-3.5" /> Real-time active guard
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Autonomous Rules Controls */}
      <div className="rounded-xl border border-border/60 bg-card/30 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary" />
              Autonomous Workflow Triggers
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Toggle specific autonomous pipelines. Background workers only execute enabled triggers.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {rules.map((rule: any) => (
            <div
              key={rule.rule_name}
              className={cn(
                'p-3.5 rounded-lg border transition-all flex flex-col justify-between',
                rule.is_enabled
                  ? 'border-border/60 bg-background/60'
                  : 'border-border/30 bg-muted/20 opacity-70'
              )}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground capitalize">
                    {rule.rule_name.replace(/_/g, ' ')}
                  </span>
                  <button
                    onClick={() =>
                      toggleRuleMutation.mutate({
                        ruleName: rule.rule_name,
                        isEnabled: !rule.is_enabled,
                      })
                    }
                    className="text-primary hover:text-primary/80 transition-colors"
                  >
                    {rule.is_enabled ? (
                      <ToggleRight className="w-6 h-6 text-emerald-500" />
                    ) : (
                      <ToggleLeft className="w-6 h-6 text-muted-foreground" />
                    )}
                  </button>
                </div>
                <div className="text-[11px] font-mono text-muted-foreground mt-1">
                  Trigger: {rule.trigger_event}
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between text-[11px]">
                <span className={cn('font-medium', rule.is_enabled ? 'text-emerald-500' : 'text-muted-foreground')}>
                  {rule.is_enabled ? 'Enabled' : 'Disabled'}
                </span>
                <button
                  onClick={() => triggerWorkflowMutation.mutate(rule.trigger_event)}
                  className="text-primary hover:underline font-medium text-[11px]"
                >
                  Run once →
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Job Tray & Queue Monitor */}
      <div className="rounded-xl border border-border/60 bg-card/40 shadow-sm overflow-hidden">
        {/* Tabs */}
        <div className="flex items-center justify-between border-b border-border/40 px-4 bg-muted/20">
          <div className="flex items-center gap-1 overflow-x-auto py-2">
            {[
              { id: 'all', label: 'All Jobs', count: counts.all },
              { id: 'running', label: 'Active', count: counts.running },
              { id: 'queued', label: 'Queued', count: counts.queued },
              { id: 'succeeded', label: 'Completed', count: counts.succeeded },
              { id: 'failed', label: 'Failed', count: counts.failed },
              { id: 'review', label: 'Review Required', count: counts.review_required },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5',
                  activeTab === tab.id
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                )}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span
                    className={cn(
                      'px-1.5 py-0.2 rounded-full text-[10px]',
                      tab.id === 'failed'
                        ? 'bg-destructive/15 text-destructive font-semibold'
                        : tab.id === 'running'
                        ? 'bg-emerald-500/15 text-emerald-600 font-semibold'
                        : tab.id === 'review'
                        ? 'bg-amber-500/15 text-amber-600 font-semibold'
                        : 'bg-muted text-muted-foreground'
                    )}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          <span className="text-[11px] text-muted-foreground font-mono hidden sm:inline">
            Auto-polling: 3s
          </span>
        </div>

        {/* Content: If Review Required tab selected, show Audit Issues */}
        {activeTab === 'review' ? (
          <div className="p-4">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Flagged Items Requiring Student Verification
            </h4>
            {auditIssues.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground text-sm">
                <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500 opacity-80" />
                No ambiguous mappings or evidence warnings. All data verified!
              </div>
            ) : (
              <div className="divide-y divide-border/40">
                {auditIssues.map((issue: any) => (
                  <div key={issue.id} className="py-3 flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          tone={issue.severity === 'error' ? 'danger' : 'warning'}
                          className="text-[10px] font-mono"
                        >
                          {issue.issue_type}
                        </Badge>
                        <span className="text-xs font-medium text-foreground">{issue.description}</span>
                      </div>
                      {issue.evidence_context?.candidates && (
                        <div className="text-xs text-muted-foreground pl-2 border-l border-border/60 mt-1">
                          Candidate topics: {issue.evidence_context.candidates.map((c: any) => `${c.topic_name} (${(c.score * 100).toFixed(0)}%)`).join(', ')}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-7 text-xs"
                        onClick={() => resolveAuditMutation.mutate({ id: issue.id, action: 'resolve' })}
                      >
                        Accept
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-muted-foreground"
                        onClick={() => resolveAuditMutation.mutate({ id: issue.id, action: 'dismiss' })}
                      >
                        Dismiss
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Jobs List Table */
          <div className="overflow-x-auto">
            {jobsList.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">
                <Layers className="w-8 h-8 mx-auto mb-2 opacity-50" />
                No jobs found in this category.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground font-medium bg-muted/10">
                    <th className="py-2.5 px-4">Job ID</th>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Progress / Stage</th>
                    <th className="py-2.5 px-4">Priority</th>
                    <th className="py-2.5 px-4">Attempts</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {jobsList.map((job: any) => (
                    <tr key={job.id} className="hover:bg-muted/10 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-foreground">
                        #{job.id}
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-mono text-xs font-semibold text-foreground">
                          {job.type}
                        </span>
                        {job.idempotency_key && (
                          <div className="text-[10px] text-muted-foreground font-mono truncate max-w-[140px]">
                            {job.idempotency_key}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider',
                            job.status === 'succeeded' && 'bg-emerald-500/15 text-emerald-600',
                            job.status === 'running' && 'bg-blue-500/15 text-blue-600 animate-pulse',
                            job.status === 'queued' && 'bg-muted text-muted-foreground',
                            job.status === 'failed' && 'bg-destructive/15 text-destructive',
                            job.status === 'cancelled' && 'bg-muted text-muted-foreground'
                          )}
                        >
                          {job.status === 'succeeded' && <CheckCircle2 className="w-3 h-3" />}
                          {job.status === 'running' && <RefreshCw className="w-3 h-3 animate-spin" />}
                          {job.status === 'failed' && <XCircle className="w-3 h-3" />}
                          {job.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 min-w-[200px]">
                        <div className="flex items-center justify-between text-[11px] mb-1">
                          <span className="text-muted-foreground truncate max-w-[150px]">
                            {job.stage || 'In queue'}
                          </span>
                          <span className="font-mono font-medium">{job.progress}%</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                          <div
                            className={cn(
                              'h-full transition-all duration-300',
                              job.status === 'failed'
                                ? 'bg-destructive'
                                : job.status === 'succeeded'
                                ? 'bg-emerald-500'
                                : 'bg-primary'
                            )}
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge tone="neutral" className="text-[10px]">
                          P{job.priority}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 font-mono text-muted-foreground">
                        {job.attempts} / {job.max_attempts}
                      </td>
                      <td className="py-3 px-4 text-right space-x-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => {
                            setSelectedJobId(job.id)
                            setDetailModalOpen(true)
                          }}
                        >
                          <Eye className="w-3.5 h-3.5 mr-1" /> Inspect
                        </Button>
                        {job.status === 'failed' && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="h-7 px-2 text-xs text-primary"
                            onClick={() => retryJobMutation.mutate(job.id)}
                            disabled={retryJobMutation.isPending}
                          >
                            <RotateCcw className="w-3 h-3 mr-1" /> Retry
                          </Button>
                        )}
                        {(job.status === 'running' || job.status === 'queued') && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs text-destructive hover:bg-destructive/10"
                            onClick={() => cancelJobMutation.mutate(job.id)}
                            disabled={cancelJobMutation.isPending}
                          >
                            Cancel
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* 6. Job Detail Modal */}
      {selectedJob && (
        <Modal
          open={detailModalOpen}
          onClose={() => setDetailModalOpen(false)}
          title={`Job #${selectedJob.id} Details — ${selectedJob.type}`}
        >
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2 text-xs">
            <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-muted/30 border border-border/40">
              <div>
                <span className="text-muted-foreground">Status:</span>{' '}
                <span className="font-semibold capitalize text-foreground">{selectedJob.status}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Priority:</span>{' '}
                <span className="font-mono font-semibold">{selectedJob.priority}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Created:</span>{' '}
                <span className="font-mono">{selectedJob.created_at || '—'}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Finished:</span>{' '}
                <span className="font-mono">{selectedJob.finished_at || '—'}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Attempts:</span>{' '}
                <span className="font-mono">{selectedJob.attempts} of {selectedJob.max_attempts}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Locked by:</span>{' '}
                <span className="font-mono">{selectedJob.locked_by || 'None'}</span>
              </div>
            </div>

            {selectedJob.error && (
              <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4" /> Error Description:
                </div>
                <div className="font-mono whitespace-pre-wrap">{selectedJob.error}</div>
                {selectedJob.error_details && Object.keys(selectedJob.error_details).length > 0 && (
                  <pre className="mt-2 p-2 rounded bg-background/50 text-[11px] overflow-x-auto text-foreground">
                    {JSON.stringify(selectedJob.error_details, null, 2)}
                  </pre>
                )}
              </div>
            )}

            <div>
              <h5 className="font-semibold text-muted-foreground uppercase tracking-wider text-[11px] mb-1">
                Input Payload
              </h5>
              <pre className="p-3 rounded-lg bg-muted/40 border border-border/40 font-mono text-[11px] overflow-x-auto text-foreground">
                {JSON.stringify(selectedJob.payload, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/40">
              {selectedJob.status === 'failed' && (
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    retryJobMutation.mutate(selectedJob.id)
                    setDetailModalOpen(false)
                  }}
                >
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Re-enqueue Job
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={() => setDetailModalOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
