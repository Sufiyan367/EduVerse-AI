import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import {
  AlertTriangle, Brain, Download, FileText, Layers, ListChecks,
  Pencil, Printer, RefreshCw, Sparkles, Trash2, Send, Search as SearchIcon,
  ChevronLeft, ChevronRight, LayoutGrid, Maximize2, Lightbulb, TrendingUp,
  CheckCircle2, XCircle, ArrowRight, Eye, RotateCcw,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { api, ApiError } from '../lib/api'
import { useJobs, usePlayer } from '../lib/store'
import type {
  Concept, DocumentOutlineItem, Excerpt,
  NoteStyle, QuizDone, QuizQuestion, SourceExplanationResponse,
  PracticeChallenge, PracticeAttemptResult, PracticeAttemptRecord,
} from '../lib/types'
import { openChatSocket } from '../lib/ws'
import { cn, formatDuration, kindLabel } from '../lib/utils'
import { NoteEditor } from '../components/editor/NoteEditor'
import { AudioPlayer } from '../components/player/AudioPlayer'
import {
  Badge, Button, Card, CardBody, Dialog, DialogContent, DialogDescription, DialogTitle,
  EmptyState, Field, Input, Progress, Select, SelectContent, SelectItem, SelectTrigger,
  SelectValue, Skeleton, Spinner, Tabs, TabsContent, TabsList, TabsTrigger, Textarea, Tooltip,
} from '../components/ui'
import { StatusBadge } from './Dashboard'

const STYLES: { value: NoteStyle; label: string; hint: string }[] = [
  { value: 'detailed', label: 'Detailed', hint: 'Prose with worked examples' },
  { value: 'concise', label: 'Concise', hint: 'Bullet-dominant, minimal prose' },
  { value: 'cornell', label: 'Cornell', hint: 'Cue column, notes, summary' },
  { value: 'exam_prep', label: 'Exam prep', hint: 'Definitions and likely-tested content first' },
]

export function SourcePage() {
  const { sourceId } = useParams({ from: '/library/$sourceId' })
  const search = useSearch({ from: '/library/$sourceId' })
  const id = Number(sourceId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Layout mode: 'studio' (3-column) or 'reader' (full notes)
  const [layoutMode, setLayoutMode] = useState<'studio' | 'reader'>('studio')
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)

  // Active studio tool tab
  const [tab, setTab] = useState(search.tab ?? 'outline')
  const [mobileTab, setMobileTab] = useState<'excerpts' | 'chat' | 'studio'>('chat')
  const [selectedTopic, setSelectedTopic] = useState<string>('')
  const [highlightIds, setHighlightIds] = useState<number[]>([])
  const [segmentQuery, setSegmentQuery] = useState('')
  const [regenOpen, setRegenOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [readerView, setReaderView] = useState<'source' | 'notes'>('source')
  const [expandedExcerptIds, setExpandedExcerptIds] = useState<number[]>([])

  const setPlayerSource = usePlayer((state) => state.setSource)
  const jobs = useJobs((state) => state.jobs)
  const lastSection = useJobs((state) => state.lastSection)

  const activeJob = useMemo(
    () =>
      Object.values(jobs).find(
        (job) =>
          job.source_id === id &&
          job.parent_id == null &&
          (job.status === 'running' || job.status === 'queued'),
      ),
    [jobs, id],
  )

  // Unified Document Workspace query
  const { data: workspaceData, isLoading, refetch: refetchWorkspace } = useQuery({
    queryKey: ['source-workspace', id],
    queryFn: () => api.getSourceWorkspace(id),
    refetchInterval: (query) => {
      const status = query.state.data?.processing?.status
      if (status === 'pending' || status === 'processing' || activeJob) {
        return 2000
      }
      return false
    },
  })

  // Segments query for passage viewer
  const { data: segmentData } = useQuery({
    queryKey: ['segments', id],
    queryFn: () => api.getSegments(id),
    enabled: !!workspaceData && workspaceData.processing.segments_count > 0,
  })

  // Scoped chat for this source
  const { data: chatData } = useQuery({
    queryKey: ['chats'],
    queryFn: () => api.listChats(),
  })

  const existingChat = useMemo(() => {
    return chatData?.chats?.find(
      (chat) => chat.scope_type === 'source' && chat.scope_id === id,
    )
  }, [chatData, id])

  const [scopedChatId, setScopedChatId] = useState<number | null>(null)

  useEffect(() => {
    if (existingChat) {
      setScopedChatId(existingChat.id)
    } else if (workspaceData && !scopedChatId) {
      api.createChat('source', id).then((created) => {
        setScopedChatId(created.id)
        void queryClient.invalidateQueries({ queryKey: ['chats'] })
      }).catch(() => {
        // Fallback or offline
      })
    }
  }, [existingChat, workspaceData, id, scopedChatId, queryClient])

  useEffect(() => {
    setPlayerSource(id)
    return () => setPlayerSource(null)
  }, [id, setPlayerSource])

  useEffect(() => {
    if (search.tab) setTab(search.tab)
  }, [search.tab])

  const regenerate = useMutation({
    mutationFn: (body: { target: 'notes' | 'concepts' | 'cards' | 'quiz' | 'all'; style?: string }) =>
      api.regenerate(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries()
      setRegenOpen(false)
      toast.success('Regenerating — watch progress in the top indicator.')
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Failed.'),
  })

  const reprocess = useMutation({
    mutationFn: () => api.reprocess(id),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Reprocessing document extraction pipeline...')
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Failed to reprocess.'),
  })

  const rename = useMutation({
    mutationFn: () => api.updateSource(id, { title: titleDraft.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries()
      setRenaming(false)
    },
  })

  const remove = useMutation({
    mutationFn: () => api.deleteSource(id),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Deleted.')
      navigate({ to: '/library' })
    },
  })

  if (isLoading || !workspaceData) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  const { source, processing, outline, concepts, progress, note } = workspaceData
  const segments = segmentData?.segments ?? []
  const isMedia = source.kind === 'audio' || source.kind === 'video' || source.kind === 'youtube'
  const printMode = search.print === true

  const jumpToSource = (ids: number[]) => {
    setHighlightIds(ids)
    setLeftOpen(true)
    const target = segments.find((segment) => segment.id === ids[0])
    if (target?.start_ms != null) usePlayer.getState().seekTo(target.start_ms)
    setTimeout(() => {
      const el = document.getElementById(`segment-${ids[0]}`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 50)
  }

  const handleExplainTopic = (topicName: string) => {
    setSelectedTopic(topicName)
    setTab('explain')
    setRightOpen(true)
  }

  const filteredSegments = segmentQuery.trim()
    ? segments.filter((s) => s.text.toLowerCase().includes(segmentQuery.toLowerCase()))
    : segments

  if (printMode && note) {
    return (
      <div className="mx-auto max-w-3xl p-8 bg-white text-black min-h-screen">
        <h1 className="mb-6 text-3xl font-semibold">{note.title}</h1>
        <NoteEditor noteId={note.id} doc={note.doc} editable={false} />
        <div className="no-print mt-8 flex gap-2 border-t border-zinc-200 pt-4">
          <Button variant="primary" onClick={() => window.print()}>
            <Printer className="h-4 w-4 mr-1.5" /> Print / Save as PDF
          </Button>
          <Button onClick={() => navigate({ to: '/library/$sourceId', params: { sourceId }, search: {} })}>
            Back to Workspace
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] lg:h-screen overflow-hidden bg-[var(--bg)]">
      {/* Top Header Bar */}
      <header className="shrink-0 border-b border-[var(--border)] bg-[var(--bg-raised)] px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Title and metadata */}
          <div className="flex items-center gap-3 min-w-0">
            {renaming ? (
              <div className="flex items-center gap-2">
                <Input
                  autoFocus
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') rename.mutate()
                    if (e.key === 'Escape') setRenaming(false)
                  }}
                  className="h-8 max-w-xs text-sm"
                />
                <Button size="sm" variant="primary" onClick={() => rename.mutate()} loading={rename.isPending}>
                  Save
                </Button>
                <Button size="sm" onClick={() => setRenaming(false)}>Cancel</Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 min-w-0">
                <h1 className="text-base font-bold tracking-tight text-[var(--text)] truncate max-w-md">
                  {source.title}
                </h1>
                <button
                  onClick={() => { setTitleDraft(source.title); setRenaming(true) }}
                  className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)] transition"
                  aria-label="Rename document"
                >
                  <Pencil className="h-3 w-3" />
                </button>
              </div>
            )}

            <div className="hidden sm:flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
              <StatusBadge status={source.status} />
              <span>· {kindLabel(source.kind)}</span>
              {processing.page_count ? <span>· {processing.page_count} pgs</span> : null}
              {source.duration_sec ? <span>· {formatDuration(source.duration_sec)}</span> : null}
              <span>· {processing.segments_count} passages</span>
              {progress.mastery_score > 0 && (
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  · {progress.mastery_score}% mastery
                </span>
              )}
            </div>
          </div>

          {/* Controls & Actions */}
          <div className="flex items-center gap-2">
            {/* Layout switch */}
            <div className="flex items-center rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setLayoutMode('studio')}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors',
                  layoutMode === 'studio'
                    ? 'bg-[var(--bg-raised)] text-[var(--accent)] font-semibold shadow-xs'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)]',
                )}
                title="DeepTutor 3-column Studio workspace"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Workspace</span>
              </button>
              <button
                type="button"
                onClick={() => setLayoutMode('reader')}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors',
                  layoutMode === 'reader'
                    ? 'bg-[var(--bg-raised)] text-[var(--accent)] font-semibold shadow-xs'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)]',
                )}
                title="Full-page Notes Reader mode"
              >
                <Maximize2 className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Reader</span>
              </button>
            </div>

            <Button size="sm" onClick={() => setRegenOpen(true)} title="Regenerate notes or study assets">
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              <span className="hidden sm:inline">Regen</span>
            </Button>

            {note && <ExportMenu noteId={note.id} sourceId={id} />}

            <Tooltip label="Delete source">
              <Button
                size="sm"
                variant="ghost"
                className="text-red-500 hover:bg-red-500/10"
                onClick={() => {
                  if (confirm(`Delete “${source.title}” and all generated concepts and cards?`)) {
                    remove.mutate()
                  }
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          </div>
        </div>

        {/* Processing Job Progress Alert */}
        {activeJob && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1.5 text-xs">
            <div className="flex items-center gap-2">
              <Spinner className="h-3.5 w-3.5 text-[var(--accent)]" />
              <span className="font-semibold text-[var(--text)]">{activeJob.stage || 'Analyzing course material…'}</span>
              {lastSection?.sourceId === id && lastSection.total > 0 && (
                <span className="text-[var(--text-muted)]">
                  (Section {lastSection.done}/{lastSection.total}: {lastSection.section})
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 w-36">
              <Progress value={activeJob.progress} className="h-1.5 flex-1" />
              <span className="tabular-nums font-mono text-[11px] text-[var(--text-muted)]">{activeJob.progress}%</span>
            </div>
          </div>
        )}

        {/* Unreadable / Scanned Document Error Banner */}
        {processing.is_unreadable && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
              <span>
                <strong>Document Extraction Alert:</strong> No extractable digital text was found in this file (0 passages indexed).
                Scanned images require digital OCR or a text-selectable PDF for AI tutoring and quiz generation.
              </span>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => reprocess.mutate()}
              loading={reprocess.isPending}
              className="shrink-0 text-xs"
            >
              <RefreshCw className="h-3 w-3 mr-1" /> Retry Processing
            </Button>
          </div>
        )}

        {/* Partial Unreadable Pages Notice */}
        {!processing.is_unreadable && processing.unreadable_pages.length > 0 && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-600 dark:text-amber-400">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />
              <span>
                <strong>Partial scan notice:</strong> Pages {processing.unreadable_pages.join(', ')} contain image scans with limited text. Digital pages were successfully indexed for grounded learning.
              </span>
            </div>
            <span className="text-[11px] opacity-80 shrink-0">{processing.segments_count} readable passages</span>
          </div>
        )}

        {/* Partial Processed Notice */}
        {!processing.is_unreadable && source.status === 'partially_processed' && source.error && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-600 dark:text-amber-400">
            <span><strong>Partial extraction notice:</strong> {source.error}</span>
            <span className="text-[11px] opacity-80 shrink-0">Indexed passages available for chat & study</span>
          </div>
        )}
      </header>

      {/* Mobile 3-Mode Switcher */}
      {layoutMode === 'studio' && (
        <div className="flex border-b border-[var(--border)] bg-[var(--bg-raised)] p-1.5 lg:hidden gap-1 shrink-0">
          <button
            type="button"
            onClick={() => setMobileTab('excerpts')}
            className={cn(
              'flex-1 py-1 text-xs font-semibold rounded-md transition-colors',
              mobileTab === 'excerpts' ? 'bg-[var(--accent)] text-white shadow-xs' : 'text-[var(--text-muted)] hover:text-[var(--text)]'
            )}
          >
            Excerpts ({segments.length})
          </button>
          <button
            type="button"
            onClick={() => setMobileTab('chat')}
            className={cn(
              'flex-1 py-1 text-xs font-semibold rounded-md transition-colors',
              mobileTab === 'chat' ? 'bg-[var(--accent)] text-white shadow-xs' : 'text-[var(--text-muted)] hover:text-[var(--text)]'
            )}
          >
            AI Tutor
          </button>
          <button
            type="button"
            onClick={() => setMobileTab('studio')}
            className={cn(
              'flex-1 py-1 text-xs font-semibold rounded-md transition-colors',
              mobileTab === 'studio' ? 'bg-[var(--accent)] text-white shadow-xs' : 'text-[var(--text-muted)] hover:text-[var(--text)]'
            )}
          >
            Studio
          </button>
        </div>
      )}

      {/* Main Workspace Body */}
      {layoutMode === 'reader' ? (
        // Fullscreen Reader Mode with Extracted Source Document & AI Notes Switcher
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 max-w-5xl mx-auto w-full space-y-4">
          {/* Reader View Switcher Header */}
          <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
            <div className="flex items-center gap-1.5 bg-[var(--bg-sunken)] p-1 rounded-lg">
              <button
                onClick={() => setReaderView('source')}
                className={cn(
                  'px-3 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5',
                  readerView === 'source'
                    ? 'bg-[var(--accent)] text-white shadow-xs'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                )}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>Extracted Document ({segments.length} passages)</span>
              </button>
              <button
                onClick={() => setReaderView('notes')}
                className={cn(
                  'px-3 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5',
                  readerView === 'notes'
                    ? 'bg-[var(--accent)] text-white shadow-xs'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                )}
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>AI Syllabus Notes</span>
              </button>
            </div>
            <span className="text-xs text-[var(--text-muted)] font-mono truncate max-w-xs">
              {source.title}
            </span>
          </div>

          {readerView === 'source' || !note ? (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
              <div className="space-y-4">
                {segments.map((seg, idx) => {
                  const isHeading = seg.text.trim().startsWith('#')
                  const isCode = seg.text.includes('def ') || seg.text.includes('print(') || seg.text.includes('class ') || seg.text.includes('SELECT ')
                  return (
                    <Card key={seg.id} id={`segment-${seg.id}`} className="transition-all hover:border-[var(--accent)]/50">
                      <CardBody className="p-4 sm:p-5 space-y-2">
                        <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] border-b border-[var(--border)] pb-1.5 mb-2">
                          <span className="font-mono font-bold text-[var(--accent)]">
                            Passage #{idx + 1}
                          </span>
                          <div className="flex items-center gap-2">
                            {seg.page_no && (
                              <Badge className="text-[10px]">Page {seg.page_no}</Badge>
                            )}
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(seg.text)
                                toast.success('Passage copied to clipboard')
                              }}
                              className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text)]"
                              title="Copy text"
                            >
                              Copy
                            </button>
                          </div>
                        </div>

                        {isCode ? (
                          <pre className="p-3 rounded bg-[var(--bg-sunken)] border border-[var(--border)] font-mono text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap text-[var(--text)]">
                            {seg.text}
                          </pre>
                        ) : (
                          <div className={cn("text-xs leading-relaxed text-[var(--text)] whitespace-pre-wrap", isHeading && "font-bold text-sm")}>
                            {seg.text}
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  )
                })}
              </div>

              {outline.length > 0 && (
                <aside className="hidden lg:block">
                  <div className="sticky top-4 space-y-2">
                    <p className="px-2 text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Outline ({outline.length})
                    </p>
                    <nav className="space-y-0.5 max-h-[75vh] overflow-y-auto pr-1">
                      {outline.map((item, index) => (
                        <button
                          key={index}
                          onClick={() => {
                            if (item.segment_id) {
                              const el = document.getElementById(`segment-${item.segment_id}`)
                              el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                            }
                          }}
                          className={cn(
                            'block w-full text-left truncate rounded px-2 py-1 text-xs text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)] transition-colors',
                            item.level >= 2 && 'pl-4 text-[11px]',
                          )}
                          title={item.title}
                        >
                          {item.title}
                        </button>
                      ))}
                    </nav>
                  </div>
                </aside>
              )}
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
              <Card>
                <CardBody className="px-6 py-6 sm:px-10 sm:py-8">
                  <NoteEditor
                    noteId={note.id}
                    doc={note.doc}
                    onAnchorClick={jumpToSource}
                    onDirty={() => queryClient.setQueryData(['source-workspace', id], (old: typeof workspaceData) =>
                      old?.note ? { ...old, note: { ...old.note, is_dirty: true } } : old,
                    )}
                  />
                </CardBody>
              </Card>

              {outline.length > 0 && (
                <aside className="hidden lg:block">
                  <div className="sticky top-4 space-y-2">
                    <p className="px-2 text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Outline
                    </p>
                    <nav className="space-y-0.5">
                      {outline.map((item, index) => (
                        <button
                          key={index}
                          onClick={() => {
                            if (item.segment_id) jumpToSource([item.segment_id])
                          }}
                          className={cn(
                            'block w-full text-left truncate rounded px-2 py-1 text-xs text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)] transition-colors',
                            item.level >= 3 && 'pl-4 text-[11px]',
                          )}
                        >
                          {item.title}
                        </button>
                      ))}
                    </nav>
                  </div>
                </aside>
              )}
            </div>
          )}
        </div>
      ) : (
        // DeepTutor 3-Column Studio Workspace
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Column 1: Source & Excerpts Inspector (Collapsible Left) */}
          <div
            className={cn(
              'border-r border-[var(--border)] bg-[var(--bg-raised)] flex-col transition-all duration-200',
              mobileTab === 'excerpts' ? 'flex w-full flex-1' : 'hidden',
              'lg:flex lg:flex-initial lg:shrink-0',
              leftOpen ? 'lg:w-80 xl:w-96' : 'lg:w-10 lg:items-center',
            )}
          >
            {leftOpen ? (
              <div className="flex flex-col h-full overflow-hidden">
                <div className="flex items-center justify-between p-3 border-b border-[var(--border)] bg-[var(--bg-sunken)]/40">
                  <div className="flex items-center gap-2 text-xs font-bold text-[var(--text)]">
                    <Layers className="h-4 w-4 text-[var(--accent)]" />
                    <span>Source Excerpts ({segments.length})</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-[var(--text-muted)]"
                    onClick={() => setLeftOpen(false)}
                    title="Collapse source panel"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                </div>

                {isMedia && source.has_media && (
                  <div className="p-3 border-b border-[var(--border)] bg-[var(--bg-sunken)]/20">
                    <AudioPlayer src={api.audioUrl(id)} />
                  </div>
                )}

                <div className="p-2.5 border-b border-[var(--border)]">
                  <div className="relative">
                    <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-muted)]" />
                    <Input
                      placeholder="Search passages..."
                      value={segmentQuery}
                      onChange={(e) => setSegmentQuery(e.target.value)}
                      className="h-8 pl-8 text-xs bg-[var(--bg-sunken)]"
                    />
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                  {filteredSegments.length === 0 ? (
                    <p className="text-center text-xs text-[var(--text-muted)] py-6">
                      {segments.length === 0 ? 'Extracting segments...' : 'No matching passages found.'}
                    </p>
                  ) : (
                    filteredSegments.map((segment) => {
                      const isHighlighted = highlightIds.includes(segment.id)
                      const isExpanded = isHighlighted || expandedExcerptIds.includes(segment.id)
                      return (
                        <div
                          key={segment.id}
                          id={`segment-${segment.id}`}
                          onClick={() => {
                            setHighlightIds([segment.id])
                            if (segment.start_ms != null) usePlayer.getState().seekTo(segment.start_ms)
                            api.recordPassageRead(id, segment.id).then(() => refetchWorkspace()).catch(() => {})
                          }}
                          className={cn(
                            'p-2.5 rounded-lg border text-xs cursor-pointer transition-all',
                            isHighlighted
                              ? 'border-[var(--accent)] bg-[var(--accent-soft)] shadow-xs ring-1 ring-[var(--accent)]/30'
                              : 'border-[var(--border)] bg-[var(--bg-raised)] hover:border-[var(--accent)]/40 hover:bg-[var(--bg-sunken)]',
                          )}
                        >
                          <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] mb-1">
                            <span className="font-mono font-semibold text-[var(--accent)]">
                              Passage #{segment.index + 1}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {segment.page_no && (
                                <Badge className="text-[9px] px-1 py-0">Page {segment.page_no}</Badge>
                              )}
                              {segment.timestamp && (
                                <span className="font-mono text-[10px]">{segment.timestamp}</span>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setExpandedExcerptIds((prev) =>
                                    prev.includes(segment.id)
                                      ? prev.filter((x) => x !== segment.id)
                                      : [...prev, segment.id]
                                  )
                                }}
                                className="text-[10px] text-[var(--accent)] hover:underline ml-1 font-medium"
                              >
                                {isExpanded ? 'Collapse' : 'Expand'}
                              </button>
                            </div>
                          </div>
                          <div className={cn("text-[12px] leading-relaxed text-[var(--text)] whitespace-pre-wrap", !isExpanded && "line-clamp-4")}>
                            {segment.text}
                          </div>
                          {isExpanded && (
                            <div className="pt-2 mt-1.5 border-t border-[var(--border)]/50 flex items-center justify-between text-[10px]">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  navigator.clipboard.writeText(segment.text)
                                  toast.success('Passage text copied to clipboard')
                                }}
                                className="text-[var(--text-muted)] hover:text-[var(--text)]"
                              >
                                Copy passage
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleExplainTopic(`Passage #${segment.index + 1}`)
                                }}
                                className="text-[var(--accent)] hover:underline font-semibold"
                              >
                                Ask AI about this →
                              </button>
                            </div>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            ) : (
              <div className="py-4 flex flex-col items-center gap-4">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-[var(--text-muted)]"
                  onClick={() => setLeftOpen(true)}
                  title="Expand source excerpts"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <span className="[writing-mode:vertical-rl] text-xs font-semibold text-[var(--text-muted)] tracking-wider">
                  SOURCES
                </span>
              </div>
            )}
          </div>

          {/* Column 2: Grounded AI Tutor Chat (Center Column) */}
          <div
            className={cn(
              'flex-col min-w-0 bg-[var(--bg)] border-r border-[var(--border)] relative',
              mobileTab === 'chat' ? 'flex flex-1 w-full' : 'hidden',
              'lg:flex lg:flex-1'
            )}
          >
            <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] bg-[var(--bg-raised)]">
              <div className="flex items-center gap-2">
                <div className="grid h-6 w-6 place-items-center rounded-md bg-[var(--accent)] text-black text-xs font-bold">
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
                <div>
                  <h2 className="text-xs font-bold text-[var(--text)]">Grounded AI Tutor</h2>
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Directly scoped to “{source.title}” · Answers cite exact passages
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {!leftOpen && (
                  <Button size="icon-sm" variant="ghost" onClick={() => setLeftOpen(true)} title="Show sources">
                    <Layers className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  </Button>
                )}
                {!rightOpen && (
                  <Button size="icon-sm" variant="ghost" onClick={() => setRightOpen(true)} title="Show studio tools">
                    <FileText className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  </Button>
                )}
              </div>
            </div>

            {/* Embedded Source Chat */}
            {scopedChatId ? (
              <SourceChatArea
                chatId={scopedChatId}
                sourceTitle={source.title}
                onSelectCitation={(segmentId) => jumpToSource([segmentId])}
              />
            ) : (
              <div className="grid flex-1 place-items-center p-6">
                <Spinner className="h-6 w-6 text-[var(--accent)]" />
              </div>
            )}
          </div>

          {/* Column 3: DeepTutor Interactive Learning Workspace (Right Column) */}
          <div
            className={cn(
              'bg-[var(--bg-raised)] flex-col transition-all duration-200',
              mobileTab === 'studio' ? 'flex w-full flex-1' : 'hidden',
              'lg:flex lg:flex-initial lg:shrink-0',
              rightOpen ? 'lg:w-96 xl:w-[30rem]' : 'lg:w-10 lg:items-center lg:border-l lg:border-[var(--border)]',
            )}
          >
            {rightOpen ? (
              <div className="flex flex-col h-full overflow-hidden">
                <div className="p-2 border-b border-[var(--border)] bg-[var(--bg-sunken)]/40">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Learning Workspace
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-[var(--text-muted)]"
                      onClick={() => setRightOpen(false)}
                      title="Collapse workspace panel"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>

                  <Tabs value={tab} onValueChange={setTab} className="w-full">
                    <TabsList className="h-8 w-full justify-start overflow-x-auto no-scrollbar gap-1">
                      <TabsTrigger value="outline" className="text-xs px-2 py-1">
                        <Layers className="h-3 w-3 mr-1" /> Outline
                      </TabsTrigger>
                      <TabsTrigger value="notes" className="text-xs px-2 py-1">
                        <FileText className="h-3 w-3 mr-1" /> Notes
                      </TabsTrigger>
                      <TabsTrigger value="explain" className="text-xs px-2 py-1">
                        <Sparkles className="h-3 w-3 mr-1" /> Explain
                      </TabsTrigger>
                      <TabsTrigger value="quiz" className="text-xs px-2 py-1">
                        <ListChecks className="h-3 w-3 mr-1" /> Quiz
                      </TabsTrigger>
                      <TabsTrigger value="cards" className="text-xs px-2 py-1">
                        <Brain className="h-3 w-3 mr-1" /> Cards
                        <Badge className="ml-1 text-[9px] px-1">{progress.cards_total}</Badge>
                      </TabsTrigger>
                      <TabsTrigger value="practice" className="text-xs px-2 py-1">
                        <Lightbulb className="h-3 w-3 mr-1" /> Practice
                      </TabsTrigger>
                      <TabsTrigger value="progress" className="text-xs px-2 py-1">
                        <TrendingUp className="h-3 w-3 mr-1" /> Progress
                      </TabsTrigger>
                    </TabsList>

                    <div className="mt-2" />

                    {/* Tab 1: Outline & Topics */}
                    <TabsContent value="outline" className="m-0 flex-1 overflow-y-auto p-3">
                      <OutlineTab
                        outline={outline}
                        concepts={concepts}
                        onJump={jumpToSource}
                        onExplain={handleExplainTopic}
                      />
                    </TabsContent>

                    {/* Tab 2: Structured Notes */}
                    <TabsContent value="notes" className="m-0 flex-1 overflow-y-auto">
                      {note ? (
                        <div className="p-4 space-y-4">
                          <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                            <span className="text-xs font-semibold text-[var(--text-muted)]">Structured Notes</span>
                            <button
                              onClick={() => setLayoutMode('reader')}
                              className="text-[11px] text-[var(--accent)] hover:underline font-medium"
                            >
                              Expand Reader View ↗
                            </button>
                          </div>
                          <NoteEditor
                            noteId={note.id}
                            doc={note.doc}
                            onAnchorClick={jumpToSource}
                            onDirty={() => queryClient.setQueryData(['source-workspace', id], (old: typeof workspaceData) =>
                              old?.note ? { ...old, note: { ...old.note, is_dirty: true } } : old,
                            )}
                          />
                        </div>
                      ) : (
                        <div className="p-6 text-center">
                          <EmptyState
                            icon={FileText}
                            title="No notes generated yet"
                            description="Generate structured notes with math equations and diagrams."
                            action={
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => regenerate.mutate({ target: 'notes' })}
                                disabled={regenerate.isPending || !!activeJob}
                              >
                                Generate Notes
                              </Button>
                            }
                          />
                        </div>
                      )}
                    </TabsContent>

                    {/* Tab 3: Explain This Concept */}
                    <TabsContent value="explain" className="m-0 flex-1 overflow-y-auto p-3">
                      <ExplainTab
                        sourceId={id}
                        initialTopic={selectedTopic}
                        concepts={concepts}
                        onJump={jumpToSource}
                      />
                    </TabsContent>

                    {/* Tab 4: In-Workspace Interactive Quiz */}
                    <TabsContent value="quiz" className="m-0 flex-1 overflow-y-auto p-3">
                      <DocumentQuizTab
                        sourceId={id}
                        onJump={jumpToSource}
                        onQuizCompleted={() => refetchWorkspace()}
                      />
                    </TabsContent>

                    {/* Tab 5: Active Recall Flashcards */}
                    <TabsContent value="cards" className="m-0 flex-1 overflow-y-auto p-3">
                      <DocumentCardsTab
                        sourceId={id}
                        cardsTotal={progress.cards_total}
                        onGenerate={() => regenerate.mutate({ target: 'cards' })}
                        onReviewDone={() => refetchWorkspace()}
                      />
                    </TabsContent>

                    {/* Tab 6: Practice Mode */}
                    <TabsContent value="practice" className="m-0 flex-1 overflow-y-auto p-3">
                      <PracticeTab
                        sourceId={id}
                        concepts={concepts}
                        onJump={jumpToSource}
                        onPracticeDone={() => refetchWorkspace()}
                      />
                    </TabsContent>

                    {/* Tab 7: Document Learning Progress */}
                    <TabsContent value="progress" className="m-0 flex-1 overflow-y-auto p-3">
                      <DocumentProgressTab
                        progress={progress}
                        processing={processing}
                      />
                    </TabsContent>
                  </Tabs>
                </div>
              </div>
            ) : (
              <div className="py-4 flex flex-col items-center gap-4">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-[var(--text-muted)]"
                  onClick={() => setRightOpen(true)}
                  title="Expand workspace panel"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="[writing-mode:vertical-rl] text-xs font-semibold text-[var(--text-muted)] tracking-wider">
                  STUDY WORKSPACE
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Regenerate Dialog */}
      <RegenerateDialog
        open={regenOpen}
        onOpenChange={setRegenOpen}
        noteWasEdited={note?.is_dirty ?? false}
        pending={regenerate.isPending}
        onConfirm={(target, style) => regenerate.mutate({ target, style })}
      />
    </div>
  )
}

/**
 * Tab 1: Outline & Document Structure
 */
function OutlineTab({
  outline,
  concepts,
  onJump,
  onExplain,
}: {
  outline: DocumentOutlineItem[]
  concepts: Concept[]
  onJump: (ids: number[]) => void
  onExplain: (topic: string) => void
}) {
  return (
    <div className="space-y-4">
      {/* Document Headings / Chapters */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
            Document Outline ({outline.length})
          </span>
        </div>

        {outline.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)] italic py-2">
            No explicit outline detected. Passages have been indexed by page number.
          </p>
        ) : (
          <div className="space-y-1.5">
            {outline.map((item, idx) => (
              <div
                key={idx}
                className={cn(
                  'group flex items-center justify-between p-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] hover:border-[var(--accent)] text-xs transition-colors',
                  item.level >= 2 && 'ml-3',
                )}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[10px] font-mono text-[var(--text-muted)] shrink-0">#{idx + 1}</span>
                  <span className="truncate text-[var(--text)] font-medium">{item.title}</span>
                  {item.page_no && (
                    <Badge className="text-[9px] px-1 py-0 shrink-0">P.{item.page_no}</Badge>
                  )}
                </div>

                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {item.segment_id && (
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      onClick={() => onJump([item.segment_id!])}
                      title="Jump to passage"
                    >
                      <Layers className="h-3 w-3 text-[var(--accent)]" />
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onExplain(item.title.replace(/^Page \d+:\s*/, ''))}
                    className="h-6 text-[10px] px-1.5 text-[var(--accent)]"
                    title="Explain this topic"
                  >
                    Explain
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Extracted Key Concepts */}
      {concepts.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-[var(--border)]">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
            Key Concepts ({concepts.length})
          </span>
          <div className="space-y-1.5">
            {concepts.slice(0, 15).map((concept) => (
              <div
                key={concept.id}
                className="flex items-start justify-between gap-2 p-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-xs"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-[var(--text)]">{concept.name}</span>
                    <Badge tone={concept.importance >= 4 ? 'accent' : 'neutral'} className="text-[9px]">
                      {'★'.repeat(concept.importance)}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-[var(--text-muted)] line-clamp-2 mt-0.5">
                    {concept.definition}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => onExplain(concept.name)}
                  className="h-6 text-[10px] px-1.5 text-[var(--accent)] shrink-0"
                >
                  Explain
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Tab 3: Explain This Concept
 */
function ExplainTab({
  sourceId,
  initialTopic,
  concepts,
  onJump,
}: {
  sourceId: number
  initialTopic: string
  concepts: Concept[]
  onJump: (ids: number[]) => void
}) {
  const [topic, setTopic] = useState(initialTopic)
  const [depth, setDepth] = useState<'principle' | 'analogy' | 'worked_example' | 'compare'>('principle')
  const [result, setResult] = useState<SourceExplanationResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (initialTopic) {
      setTopic(initialTopic)
      void handleExplain(initialTopic, depth)
    }
  }, [initialTopic])

  const handleExplain = async (t: string, d: 'principle' | 'analogy' | 'worked_example' | 'compare') => {
    if (!t.trim()) return
    setLoading(true)
    try {
      const res = await api.explainSourceTopic(sourceId, { topic: t.trim(), depth: d })
      setResult(res)
    } catch (err) {
      toast.error('Failed to generate document-grounded explanation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Topic selection and depth controls */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Enter any concept from this document..."
            className="h-8 text-xs bg-[var(--bg-sunken)] flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleExplain(topic, depth)
            }}
          />
          <Button
            size="sm"
            variant="primary"
            onClick={() => void handleExplain(topic, depth)}
            disabled={!topic.trim() || loading}
            loading={loading}
          >
            Explain
          </Button>
        </div>

        {/* Depth Selector Pills */}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {[
            { id: 'principle', label: 'Core Principle' },
            { id: 'analogy', label: 'Simple Analogy' },
            { id: 'worked_example', label: 'Worked Example' },
            { id: 'compare', label: 'Compare & Contrast' },
          ].map((mode) => (
            <button
              key={mode.id}
              onClick={() => {
                const nextDepth = mode.id as typeof depth
                setDepth(nextDepth)
                if (topic.trim()) void handleExplain(topic, nextDepth)
              }}
              className={cn(
                'rounded-md px-2 py-1 text-[11px] font-medium border transition-colors',
                depth === mode.id
                  ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                  : 'border-[var(--border)] bg-[var(--bg)] text-[var(--text-muted)] hover:text-[var(--text)]',
              )}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Suggested concepts shortcut pills */}
      {concepts.length > 0 && !result && (
        <div className="space-y-1.5 pt-2">
          <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
            Suggested Document Topics
          </span>
          <div className="flex flex-wrap gap-1.5">
            {concepts.slice(0, 8).map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setTopic(c.name)
                  void handleExplain(c.name, depth)
                }}
                className="rounded-full border border-[var(--border)] bg-[var(--bg)] px-2.5 py-0.5 text-xs text-[var(--text)] hover:border-[var(--accent)] hover:bg-[var(--bg-sunken)] transition-colors"
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading indicator */}
      {loading && (
        <div className="flex items-center justify-center p-8 text-xs text-[var(--text-muted)] gap-2">
          <Spinner className="h-4 w-4 text-[var(--accent)]" />
          <span>Searching document and synthesizing {depth} explanation...</span>
        </div>
      )}

      {/* Structured Explanation Output */}
      {result && !loading && (
        <div className="space-y-4">
          <Card>
            <CardBody className="p-3.5 space-y-3">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <h3 className="text-xs font-bold text-[var(--text)]">{result.topic}</h3>
                <Badge tone="accent" className="text-[10px] capitalize">{result.depth.replace('_', ' ')}</Badge>
              </div>

              {/* Summary */}
              <div className="text-xs leading-relaxed text-[var(--text)] whitespace-pre-wrap">
                {result.summary}
              </div>

              {/* Key Definitions */}
              {result.definitions.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-[var(--border)]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    Key Definitions
                  </span>
                  <div className="grid gap-1.5">
                    {result.definitions.map((def, idx) => (
                      <div key={idx} className="p-2 rounded bg-[var(--bg-sunken)] text-xs">
                        <span className="font-bold text-[var(--accent)]">{def.term}: </span>
                        <span className="text-[var(--text)]">{def.definition}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Worked Example */}
              {result.worked_example && (
                <div className="space-y-1.5 pt-2 border-t border-[var(--border)]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    Step-by-Step Scenario Analysis
                  </span>
                  <div className="p-2.5 rounded bg-[var(--bg-sunken)] border border-[var(--border)] text-xs font-mono text-[var(--text)] leading-relaxed whitespace-pre-wrap">
                    {result.worked_example}
                  </div>
                </div>
              )}

              {/* Verified Citations */}
              {result.citations.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-[var(--border)]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    Verified Citations ({result.citations.length})
                  </span>
                  <div className="space-y-1">
                    {result.citations.map((cite, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded border border-[var(--border)] bg-[var(--bg)] text-xs"
                      >
                        <div className="min-w-0 pr-2">
                          <span className="font-semibold text-[var(--accent)]">
                            {cite.page_no ? `Page ${cite.page_no}` : `Passage #${cite.segment_id}`}
                          </span>
                          <p className="text-[11px] text-[var(--text-muted)] truncate">{cite.quote}</p>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onJump([cite.segment_id])}
                          className="h-6 text-[10px] px-1.5 text-[var(--accent)] shrink-0"
                        >
                          Jump ↗
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  )
}

/**
 * Tab 4: In-Workspace Interactive Quiz
 */
function DocumentQuizTab({
  sourceId,
  onJump,
  onQuizCompleted,
}: {
  sourceId: number
  onJump: (ids: number[]) => void
  onQuizCompleted: () => void
}) {
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [currentQuestion, setCurrentQuestion] = useState<QuizQuestion | null>(null)
  const [quizDone, setQuizDone] = useState<QuizDone | null>(null)
  const [selectedOption, setSelectedOption] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)
  const [lastFeedback, setLastFeedback] = useState<{
    is_correct: boolean
    feedback: string
    correct_answer: string
    explanation: string
    segment_ids?: number[]
  } | null>(null)
  const [scoreCount, setScoreCount] = useState(0)
  const [totalAnswered, setTotalAnswered] = useState(0)

  const startQuiz = async () => {
    setLoading(true)
    setLastFeedback(null)
    setScoreCount(0)
    setTotalAnswered(0)
    setQuizDone(null)
    try {
      const sess = await api.createQuizSession({ mode: 'practice', source_ids: [sourceId] })
      setSessionId(sess.session_id)
      const firstQ = await api.nextQuestion(sess.session_id)
      if ('done' in firstQ && firstQ.done) {
        setQuizDone(firstQ as QuizDone)
      } else {
        setCurrentQuestion(firstQ as QuizQuestion)
      }
    } catch (err) {
      toast.error('Unable to start quiz. Check if concepts have been extracted.')
    } finally {
      setLoading(false)
    }
  }

  const submitAnswer = async () => {
    if (!sessionId || !currentQuestion || !selectedOption) return
    setSubmitting(true)
    try {
      const res = await api.answerQuestion(sessionId, currentQuestion.id, selectedOption)
      setLastFeedback({
        is_correct: !!res.is_correct,
        feedback: res.feedback || (res.is_correct ? 'Correct answer!' : 'Incorrect.'),
        correct_answer: res.correct_answer || '',
        explanation: res.explanation || '',
        segment_ids: res.segment_ids,
      })
      if (res.is_correct) setScoreCount((s) => s + 1)
      setTotalAnswered((t) => t + 1)
      onQuizCompleted()
    } catch (err) {
      toast.error('Failed to submit answer.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleNext = async () => {
    if (!sessionId) return
    setLoading(true)
    setLastFeedback(null)
    setSelectedOption('')
    try {
      const next = await api.nextQuestion(sessionId)
      if ('done' in next && next.done) {
        setQuizDone(next as QuizDone)
        setCurrentQuestion(null)
      } else {
        setCurrentQuestion(next as QuizQuestion)
      }
    } catch (err) {
      toast.error('Failed to fetch next question.')
    } finally {
      setLoading(false)
    }
  }

  if (!sessionId) {
    return (
      <Card>
        <EmptyState
          icon={ListChecks}
          title="Interactive Document Quiz"
          description="Take an assessment generated directly from this document's text and concepts."
          action={
            <Button variant="primary" size="sm" onClick={startQuiz} loading={loading}>
              <ListChecks className="h-4 w-4 mr-1.5" /> Start Assessment
            </Button>
          }
        />
      </Card>
    )
  }

  if (quizDone) {
    const accuracy = totalAnswered > 0 ? Math.round((scoreCount / totalAnswered) * 100) : 0
    return (
      <Card>
        <CardBody className="p-4 text-center space-y-3">
          <div className="grid h-12 w-12 place-items-center rounded-full bg-emerald-500/10 text-emerald-500 mx-auto">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-bold text-[var(--text)]">Assessment Complete</h3>
          <p className="text-xs text-[var(--text-muted)]">
            You scored {scoreCount} out of {totalAnswered} questions ({accuracy}%).
          </p>
          <Badge tone={accuracy >= 80 ? 'accent' : accuracy >= 70 ? 'neutral' : 'danger'}>
            {accuracy >= 80 ? 'Mastered (80%+)' : accuracy >= 70 ? 'Practicing (70–79%)' : 'Needs Review (<70%)'}
          </Badge>
          <div className="pt-2">
            <Button size="sm" variant="primary" onClick={startQuiz}>
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> Retake Quiz
            </Button>
          </div>
        </CardBody>
      </Card>
    )
  }

  if (!currentQuestion) {
    return (
      <div className="p-6 text-center">
        <Spinner className="h-5 w-5 text-[var(--accent)] mx-auto" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Quiz Progress Header */}
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)] border-b border-[var(--border)] pb-2">
        <span>Question #{totalAnswered + 1}</span>
        <div className="flex items-center gap-2">
          {currentQuestion.concept?.name && (
            <Badge className="text-[9px] px-1 py-0">{currentQuestion.concept.name}</Badge>
          )}
          <span className="font-semibold text-[var(--accent)]">Score: {scoreCount}/{totalAnswered}</span>
        </div>
      </div>

      {/* Question Card */}
      <Card>
        <CardBody className="p-4 space-y-3">
          <h4 className="text-xs font-bold text-[var(--text)] leading-relaxed">
            {currentQuestion.question}
          </h4>

          {/* Multiple choice options */}
          <div className="space-y-1.5">
            {currentQuestion.options.map((opt, idx) => {
              const letter = ['A', 'B', 'C', 'D'][idx] || String(idx)
              const isSelected = selectedOption === opt
              return (
                <button
                  key={idx}
                  type="button"
                  disabled={!!lastFeedback}
                  onClick={() => setSelectedOption(opt)}
                  className={cn(
                    'w-full text-left p-2.5 rounded-lg border text-xs transition-all flex items-start gap-2',
                    isSelected
                      ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--text)] font-medium ring-1 ring-[var(--accent)]/30'
                      : 'border-[var(--border)] bg-[var(--bg)] text-[var(--text)] hover:bg-[var(--bg-sunken)]',
                    lastFeedback && opt === lastFeedback.correct_answer && 'border-emerald-500 bg-emerald-500/10 font-semibold',
                    lastFeedback && isSelected && !lastFeedback.is_correct && 'border-red-500 bg-red-500/10 line-through',
                  )}
                >
                  <span className="font-mono font-bold text-[var(--accent)]">{letter}.</span>
                  <span className="flex-1">{opt}</span>
                </button>
              )
            })}
          </div>

          {/* Action buttons */}
          {!lastFeedback ? (
            <Button
              size="sm"
              variant="primary"
              onClick={submitAnswer}
              disabled={!selectedOption || submitting}
              loading={submitting}
              className="w-full"
            >
              Submit Answer
            </Button>
          ) : (
            <div className="space-y-3 pt-2">
              <div
                className={cn(
                  'p-3 rounded-lg border text-xs',
                  lastFeedback.is_correct
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                    : 'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400',
                )}
              >
                <div className="flex items-center gap-2 font-bold mb-1">
                  {lastFeedback.is_correct ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      <span>Correct!</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-red-500" />
                      <span>Incorrect — Correct Answer: {lastFeedback.correct_answer}</span>
                    </>
                  )}
                </div>
                <p className="text-[11px] leading-relaxed text-[var(--text)] mt-1">{lastFeedback.explanation}</p>
                {lastFeedback.segment_ids && lastFeedback.segment_ids.length > 0 && (
                  <div className="mt-2 pt-1 border-t border-[var(--border)] flex items-center justify-between">
                    <span className="text-[10px] text-[var(--text-muted)] italic">Grounded in source passages</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onJump(lastFeedback.segment_ids!)}
                      className="h-5 text-[10px] text-[var(--accent)] px-1"
                    >
                      View Passage #{lastFeedback.segment_ids[0]} ↗
                    </Button>
                  </div>
                )}
              </div>

              <Button size="sm" variant="primary" onClick={handleNext} className="w-full">
                Next Question <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

/**
 * Tab 5: Active Recall Flashcards
 */
function DocumentCardsTab({
  sourceId,
  cardsTotal,
  onGenerate,
  onReviewDone,
}: {
  sourceId: number
  cardsTotal: number
  onGenerate: () => void
  onReviewDone: () => void
}) {
  const [mode, setMode] = useState<'due' | 'all'>('due')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Query due cards for spaced repetition
  const { data: dueData, refetch: refetchDue } = useQuery({
    queryKey: ['cards-due', sourceId],
    queryFn: () => api.dueCards({ source_id: sourceId, limit: 50 }),
  })

  // Query all cards for comprehensive study/browsing
  const { data: allData, refetch: refetchAll } = useQuery({
    queryKey: ['cards-all', sourceId],
    queryFn: () => api.listCards(sourceId),
  })

  const dueCards = dueData?.cards ?? []
  const allCards = allData?.cards ?? []

  const activeCards = mode === 'due' ? dueCards : allCards
  const currentCard = activeCards[currentIndex]

  // Reset due schedule mutation
  const resetDue = useMutation({
    mutationFn: () => api.resetDueCards(sourceId),
    onSuccess: () => {
      void refetchDue()
      void refetchAll()
      setCurrentIndex(0)
      setRevealed(false)
      toast.success('Spaced repetition queue reset for today!')
    },
    onError: () => toast.error('Failed to reset schedule.'),
  })

  const handleRating = async (rating: number) => {
    if (!currentCard) return
    setSubmitting(true)
    try {
      await api.reviewCard(currentCard.id, rating)
      setRevealed(false)
      if (currentIndex + 1 < activeCards.length) {
        setCurrentIndex((i) => i + 1)
      } else {
        await refetchDue()
        await refetchAll()
        setCurrentIndex(0)
      }
      onReviewDone()
    } catch {
      toast.error('Failed to submit card review.')
    } finally {
      setSubmitting(false)
    }
  }

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.code === 'Space') {
        e.preventDefault()
        setRevealed((r) => !r)
      } else if (e.code === 'ArrowRight' && currentIndex + 1 < activeCards.length) {
        e.preventDefault()
        setRevealed(false)
        setCurrentIndex((i) => i + 1)
      } else if (e.code === 'ArrowLeft' && currentIndex > 0) {
        e.preventDefault()
        setRevealed(false)
        setCurrentIndex((i) => i - 1)
      } else if (revealed && mode === 'due') {
        if (e.key === '1') handleRating(1)
        if (e.key === '2') handleRating(2)
        if (e.key === '3') handleRating(3)
        if (e.key === '4') handleRating(4)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [revealed, currentIndex, activeCards.length, mode])

  if (allCards.length === 0 && cardsTotal === 0) {
    return (
      <Card>
        <EmptyState
          icon={Brain}
          title="No flashcards generated yet"
          description="Synthesize high-yield study flashcards directly from this document's concepts and sections."
          action={
            <Button size="sm" variant="primary" onClick={onGenerate}>
              <Sparkles className="h-3.5 w-3.5 mr-1.5" />
              Generate Flashcards Now
            </Button>
          }
        />
      </Card>
    )
  }

  if (mode === 'due' && dueCards.length === 0) {
    return (
      <Card>
        <CardBody className="p-5 text-center space-y-3">
          <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
          <h3 className="text-sm font-bold text-[var(--text)]">All Scheduled Reviews Complete!</h3>
          <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
            You are 100% caught up on your spaced repetition queue for this document ({allCards.length} total cards available).
          </p>
          <div className="pt-2 flex flex-wrap justify-center gap-2">
            <Button size="sm" variant="primary" onClick={() => { setMode('all'); setCurrentIndex(0); setRevealed(false); }}>
              <Eye className="h-3.5 w-3.5 mr-1" />
              Browse & Study All Cards ({allCards.length})
            </Button>
            <Button size="sm" variant="secondary" onClick={() => resetDue.mutate()} loading={resetDue.isPending}>
              <RotateCcw className="h-3.5 w-3.5 mr-1" />
              Restart Review Queue
            </Button>
          </div>
        </CardBody>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {/* Mode Switcher and Card Counter */}
      <div className="flex items-center justify-between text-xs border-b border-[var(--border)] pb-2.5">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => { setMode('due'); setCurrentIndex(0); setRevealed(false); }}
            className={cn(
              'px-2 py-0.5 rounded text-[11px] font-semibold transition-colors',
              mode === 'due'
                ? 'bg-[var(--accent)] text-white shadow-xs'
                : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg-sunken)]'
            )}
          >
            Due for Review ({dueCards.length})
          </button>
          <button
            onClick={() => { setMode('all'); setCurrentIndex(0); setRevealed(false); }}
            className={cn(
              'px-2 py-0.5 rounded text-[11px] font-semibold transition-colors',
              mode === 'all'
                ? 'bg-[var(--accent)] text-white shadow-xs'
                : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg-sunken)]'
            )}
          >
            All Cards ({allCards.length})
          </button>
        </div>
        <span className="text-[11px] font-mono text-[var(--text-muted)]">
          {currentIndex + 1} / {activeCards.length}
        </span>
      </div>

      {currentCard && (
        <Card className="min-h-[14rem] flex flex-col justify-between shadow-xs border-[var(--border)]">
          <CardBody className="p-4 space-y-3">
            <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)]">
              <span className="font-semibold uppercase tracking-wider text-[var(--accent)]">
                {currentCard.type || 'BASIC'}
              </span>
              <span className="text-[10px] text-[var(--text-muted)]">
                Press Space to Flip
              </span>
            </div>

            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Prompt</span>
              <p className="text-xs font-semibold text-[var(--text)] mt-1 leading-relaxed whitespace-pre-wrap">
                {currentCard.front}
              </p>
            </div>

            {revealed && (
              <div className="pt-3 border-t border-[var(--border)] animate-in fade-in">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-500">Solution / Answer</span>
                <p className="text-xs text-[var(--text)] mt-1.5 leading-relaxed whitespace-pre-wrap">
                  {currentCard.back}
                </p>
              </div>
            )}
          </CardBody>

          {/* Action Footer */}
          <div className="p-3 border-t border-[var(--border)] bg-[var(--bg-sunken)]/40 space-y-2">
            {!revealed ? (
              <Button
                size="sm"
                variant="primary"
                className="w-full"
                onClick={() => setRevealed(true)}
              >
                <Eye className="h-3.5 w-3.5 mr-1" /> Reveal Answer
              </Button>
            ) : mode === 'due' ? (
              <div className="space-y-1.5">
                <span className="text-[10px] text-center block text-[var(--text-muted)]">Rate Recall (FSRS):</span>
                <div className="grid grid-cols-4 gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={submitting}
                    onClick={() => handleRating(1)}
                    className="text-red-500 text-[10px] px-1"
                  >
                    Again (1)
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={submitting}
                    onClick={() => handleRating(2)}
                    className="text-amber-500 text-[10px] px-1"
                  >
                    Hard (2)
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={submitting}
                    onClick={() => handleRating(3)}
                    className="text-blue-500 text-[10px] px-1"
                  >
                    Good (3)
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={submitting}
                    onClick={() => handleRating(4)}
                    className="text-emerald-500 text-[10px] px-1"
                  >
                    Easy (4)
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={currentIndex === 0}
                  onClick={() => { setRevealed(false); setCurrentIndex((i) => Math.max(0, i - 1)); }}
                  className="flex-1 text-xs"
                >
                  <ChevronLeft className="h-3.5 w-3.5 mr-1" /> Previous
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  disabled={currentIndex + 1 >= activeCards.length}
                  onClick={() => { setRevealed(false); setCurrentIndex((i) => Math.min(activeCards.length - 1, i + 1)); }}
                  className="flex-1 text-xs"
                >
                  Next <ChevronRight className="h-3.5 w-3.5 ml-1" />
                </Button>
              </div>
            )}

            {/* Bottom Nav Buttons */}
            {mode === 'due' && (
              <div className="flex items-center justify-between pt-1 text-[11px] text-[var(--text-muted)]">
                <button
                  disabled={currentIndex === 0}
                  onClick={() => { setRevealed(false); setCurrentIndex((i) => Math.max(0, i - 1)); }}
                  className="hover:text-[var(--text)] disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-0.5"
                >
                  <ChevronLeft className="h-3 w-3" /> Prev
                </button>
                <button
                  onClick={() => resetDue.mutate()}
                  className="text-[10px] text-[var(--accent)] hover:underline flex items-center gap-1"
                  title="Reset review schedule"
                >
                  <RotateCcw className="h-2.5 w-2.5" /> Reset Queue
                </button>
                <button
                  disabled={currentIndex + 1 >= activeCards.length}
                  onClick={() => { setRevealed(false); setCurrentIndex((i) => Math.min(activeCards.length - 1, i + 1)); }}
                  className="hover:text-[var(--text)] disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-0.5"
                >
                  Skip <ChevronRight className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}

/**
 * Tab 6: Interactive Practice Mode
 */
function PracticeTab({
  sourceId,
  concepts,
  onJump,
  onPracticeDone,
}: {
  sourceId: number
  concepts: Concept[]
  onJump: (ids: number[]) => void
  onPracticeDone: () => void
}) {
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [studentAnswer, setStudentAnswer] = useState('')
  const [revealedHints, setRevealedHints] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [evaluation, setEvaluation] = useState<PracticeAttemptResult | null>(null)
  const [viewHistory, setViewHistory] = useState(false)
  const [showModelSolution, setShowModelSolution] = useState(false)

  const { data: challengesData, isLoading: challengesLoading } = useQuery({
    queryKey: ['practice-challenges', sourceId],
    queryFn: () => api.getPracticeChallenges(sourceId),
  })

  const { data: historyData, refetch: refetchHistory } = useQuery({
    queryKey: ['practice-history', sourceId],
    queryFn: () => api.getPracticeHistory(sourceId),
  })

  const challenges: PracticeChallenge[] = challengesData?.challenges ?? []
  const history: PracticeAttemptRecord[] = historyData?.attempts ?? []
  const activeChallenge = challenges[selectedIdx] || null

  const handleSelectChallenge = (idx: number) => {
    setSelectedIdx(idx)
    setStudentAnswer('')
    setRevealedHints(0)
    setEvaluation(null)
    setShowModelSolution(false)
  }

  const handleRevealHint = () => {
    if (activeChallenge && revealedHints < activeChallenge.hints.length) {
      setRevealedHints((h) => h + 1)
    }
  }

  const handleSubmit = async () => {
    if (!activeChallenge || !studentAnswer.trim() || submitting) return
    setSubmitting(true)
    try {
      const res = await api.evaluatePractice(sourceId, {
        challenge_id: (activeChallenge.id || activeChallenge.challenge_id || ''),
        question: (activeChallenge.problem_statement || activeChallenge.prompt || ''),
        student_answer: studentAnswer.trim(),
        concept: (activeChallenge.concept || activeChallenge.related_concept || '') || '',
      })
      setEvaluation(res)
      await refetchHistory()
      onPracticeDone()
      if (res.is_passing) {
        toast.success(`Passed with score ${res.score}/100!`)
      } else {
        toast.info(`Score: ${res.score}/100. Review feedback below.`)
      }
    } catch {
      toast.error('Evaluation failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (challengesLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-xs text-[var(--text-muted)] gap-2">
        <Spinner className="h-4 w-4 text-[var(--accent)]" />
        <span>Synthesizing interactive challenges from document passages...</span>
      </div>
    )
  }

  if (challenges.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={Brain}
          title="No practice challenges available yet"
          description="Challenges are generated from extracted document concepts and key technical passages."
        />
      </Card>
    )
  }

  return (
    <div className="space-y-3.5">
      {/* Header with History Toggle */}
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)] border-b border-[var(--border)] pb-2">
        <span className="font-semibold text-[var(--text)]">
          Interactive Challenges ({challenges.length})
        </span>
        <button
          onClick={() => setViewHistory(!viewHistory)}
          className="text-[11px] text-[var(--accent)] hover:underline font-medium"
        >
          {viewHistory ? 'Back to Challenge' : `History (${history.length})`}
        </button>
      </div>

      {viewHistory ? (
        /* History View */
        <div className="space-y-2">
          {history.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)] italic py-4 text-center">
              No previous attempts recorded yet.
            </p>
          ) : (
            history.map((att) => (
              <Card key={att.id}>
                <CardBody className="p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--text)]">{att.topic}</span>
                    <Badge tone={att.is_passing ? 'accent' : 'danger'} className="text-[10px]">
                      {att.score}/100 {att.is_passing ? 'Passed' : 'Needs Work'}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">{att.feedback}</p>
                  <span className="text-[9px] text-[var(--text-muted)] block">{att.created_at}</span>
                </CardBody>
              </Card>
            ))
          )}
        </div>
      ) : (
        /* Active Challenge View */
        <div className="space-y-3">
          {/* Challenge Selector Chips */}
          <div className="flex gap-1.5 overflow-x-auto pb-1">
            {challenges.map((c, idx) => (
              <button
                key={c.id || c.challenge_id || idx}
                onClick={() => handleSelectChallenge(idx)}
                className={cn(
                  'px-2.5 py-1 rounded-full text-[11px] font-medium whitespace-nowrap border transition-colors',
                  selectedIdx === idx
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                    : 'border-[var(--border)] bg-[var(--bg-raised)] text-[var(--text-muted)] hover:text-[var(--text)]',
                )}
              >
                #{idx + 1} {c.title.slice(0, 18)}...
              </button>
            ))}
          </div>

          {activeChallenge && (
            <Card>
              <CardBody className="p-4 space-y-3">
                {/* Challenge Header */}
                <div className="flex items-start justify-between gap-2 border-b border-[var(--border)] pb-2.5">
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Badge
                        tone={
                          activeChallenge.difficulty === 'advanced'
                            ? 'danger'
                            : activeChallenge.difficulty === 'intermediate'
                            ? 'neutral'
                            : 'accent'
                        }
                        className="text-[9px] uppercase tracking-wider font-semibold"
                      >
                        {activeChallenge.difficulty}
                      </Badge>
                      {(activeChallenge.concept || activeChallenge.related_concept || '') && (
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-[var(--text-muted)]">
                            Topic: {(activeChallenge.concept || activeChallenge.related_concept || '')}
                          </span>
                          {(() => {
                            const matchingConcept = concepts.find(
                              (c) => c.name.toLowerCase() === (activeChallenge.concept || activeChallenge.related_concept || '')?.toLowerCase()
                            )
                            if (matchingConcept && matchingConcept.segment_ids.length > 0) {
                              return (
                                <button
                                  type="button"
                                  onClick={() => onJump(matchingConcept.segment_ids)}
                                  className="text-[9px] text-[var(--accent)] hover:underline ml-1"
                                >
                                  View Passage ↗
                                </button>
                              )
                            }
                            return null
                          })()}
                        </div>
                      )}
                    </div>
                    <h3 className="text-xs font-bold text-[var(--text)]">
                      {activeChallenge.title}
                    </h3>
                  </div>
                </div>

                {/* Challenge Prompt */}
                <div className="p-2.5 rounded-lg bg-[var(--bg-sunken)] text-xs text-[var(--text)] leading-relaxed border border-[var(--border)]">
                  {(activeChallenge.problem_statement || activeChallenge.prompt || '')}
                </div>

                {/* Sample Input / Concrete Scenario */}
                {activeChallenge.sample_input && (
                  <div className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Given Context / Parameters:
                    </span>
                    <pre className="p-2 rounded bg-[var(--bg)] border border-[var(--border)] text-[11px] font-mono text-[var(--text)] overflow-x-auto">
                      {activeChallenge.sample_input}
                    </pre>
                  </div>
                )}

                {/* Evaluation Criteria Checklist */}
                {activeChallenge.expected_criteria.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Rubric Criteria:
                    </span>
                    <ul className="space-y-0.5 text-[11px] text-[var(--text-muted)] list-disc pl-4">
                      {activeChallenge.expected_criteria.map((crit, i) => (
                        <li key={i}>{crit}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Progressive Hints */}
                {activeChallenge.hints.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--accent)]">
                        Progressive Hints ({revealedHints}/{activeChallenge.hints.length})
                      </span>
                      {revealedHints < activeChallenge.hints.length && (
                        <button
                          onClick={handleRevealHint}
                          className="text-[10px] text-[var(--accent)] hover:underline font-medium"
                        >
                          Reveal Hint #{revealedHints + 1}
                        </button>
                      )}
                    </div>
                    {revealedHints > 0 && (
                      <div className="space-y-1">
                        {activeChallenge.hints.slice(0, revealedHints).map((hint, i) => (
                          <div
                            key={i}
                            className="p-2 rounded border border-[var(--accent)]/30 bg-[var(--accent-soft)] text-xs text-[var(--text)] animate-in fade-in"
                          >
                            <span className="font-semibold text-[var(--accent)]">Hint {i + 1}: </span>
                            {hint}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Student Submission Area */}
                <div className="space-y-2 pt-2 border-t border-[var(--border)]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    Your Solution / Reasoning:
                  </span>
                  <Textarea
                    rows={4}
                    value={studentAnswer}
                    onChange={(e) => setStudentAnswer(e.target.value)}
                    placeholder="Write your step-by-step solution, mathematical working, or technical explanation here..."
                    className="text-xs font-mono bg-[var(--bg-sunken)]"
                  />
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={handleSubmit}
                    disabled={!studentAnswer.trim() || submitting}
                    loading={submitting}
                    className="w-full"
                  >
                    Evaluate Solution with Rubric
                  </Button>
                </div>

                {/* Evaluation Feedback Card */}
                {evaluation && (
                  <div className="space-y-3 pt-3 border-t border-[var(--border)] animate-in fade-in">
                    <div
                      className={cn(
                        'p-3 rounded-lg border text-xs space-y-2',
                        evaluation.is_passing
                          ? 'border-emerald-500/30 bg-emerald-500/10'
                          : 'border-amber-500/30 bg-amber-500/10',
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-bold">
                          {evaluation.is_passing ? (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                              <span className="text-emerald-600 dark:text-emerald-400">Passing Grade</span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="h-4 w-4 text-amber-500" />
                              <span className="text-amber-600 dark:text-amber-400">Needs Revision</span>
                            </>
                          )}
                        </div>
                        <Badge tone={evaluation.is_passing ? 'accent' : 'danger'}>
                          Score: {evaluation.score}/100
                        </Badge>
                      </div>

                      <p className="text-[11px] text-[var(--text)] leading-relaxed">
                        {evaluation.feedback}
                      </p>

                      {evaluation.strengths.length > 0 && (
                        <div>
                          <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 block mb-0.5">
                            Demonstrated Strengths:
                          </span>
                          <ul className="list-disc pl-4 space-y-0.5 text-[10px] text-[var(--text)]">
                            {evaluation.strengths.map((s, i) => (
                              <li key={i}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {evaluation.missed_points.length > 0 && (
                        <div>
                          <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 block mb-0.5">
                            Areas for Improvement:
                          </span>
                          <ul className="list-disc pl-4 space-y-0.5 text-[10px] text-[var(--text)]">
                            {evaluation.missed_points.map((m, i) => (
                              <li key={i}>{m}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Model Solution Toggle */}
                    {evaluation.model_solution && (
                      <div className="pt-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setShowModelSolution(!showModelSolution)}
                          className="text-[11px] text-[var(--accent)] px-0"
                        >
                          {showModelSolution ? 'Hide Model Solution' : 'View Verified Model Solution'}
                        </Button>
                        {showModelSolution && (
                          <div className="mt-2 p-2.5 rounded bg-[var(--bg-sunken)] border border-[var(--border)] text-xs font-mono text-[var(--text)] whitespace-pre-wrap leading-relaxed animate-in fade-in">
                            {evaluation.model_solution}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Tab 7: Document Learning Progress
 */
function DocumentProgressTab({
  progress,
  processing,
}: {
  progress: {
    cards_total: number
    cards_reviewed: number
    quiz_items_total: number
    quiz_attempts: number
    quiz_correct: number
    quiz_accuracy_pct: number | null
    passages_read?: number
    practice_completed?: number
    mastery_score: number
  }
  processing: {
    page_count: number | null
    segments_count: number
  }
}) {
  return (
    <div className="space-y-4">
      {/* Overall Mastery Gauge */}
      <Card>
        <CardBody className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Document Mastery
              </span>
              <h3 className="text-xl font-bold text-[var(--text)] mt-0.5">
                {progress.mastery_score}%
              </h3>
            </div>
            <Badge
              tone={progress.mastery_score >= 80 ? 'accent' : progress.mastery_score >= 70 ? 'neutral' : 'danger'}
            >
              {progress.mastery_score >= 80 ? 'Mastered' : progress.mastery_score >= 70 ? 'Practicing' : 'Needs Study'}
            </Badge>
          </div>

          <Progress value={progress.mastery_score} className="h-2" />
          <p className="text-[10px] text-[var(--text-muted)]">
            Computed strictly from verified flashcard retention, quiz accuracy, passage reading, and practice completion. Initial is strictly 0.0%.
          </p>
        </CardBody>
      </Card>

      {/* Metric Breakdown Grid */}
      <div className="grid grid-cols-2 gap-2">
        <Card>
          <CardBody className="p-3">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Passages Read</span>
            <p className="text-sm font-bold text-[var(--text)] mt-0.5">
              {progress.passages_read ?? 0} / {processing.segments_count}
            </p>
            <span className="text-[10px] text-[var(--text-muted)]">Studied passages</span>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-3">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Flashcards</span>
            <p className="text-sm font-bold text-[var(--text)] mt-0.5">
              {progress.cards_reviewed} / {progress.cards_total}
            </p>
            <span className="text-[10px] text-[var(--text-muted)]">Reviewed (FSRS)</span>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-3">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Quiz Attempts</span>
            <p className="text-sm font-bold text-[var(--text)] mt-0.5">{progress.quiz_attempts}</p>
            <span className="text-[10px] text-[var(--text-muted)]">Questions answered</span>
          </CardBody>
        </Card>

        <Card>
          <CardBody className="p-3">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Practice Challenges</span>
            <p className="text-sm font-bold text-[var(--text)] mt-0.5">
              {progress.practice_completed ?? 0}
            </p>
            <span className="text-[10px] text-[var(--text-muted)]">Passing attempts</span>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

/**
 * Embedded Grounded AI Tutor Chat component inside the Studio
 */
function SourceChatArea({
  chatId,
  sourceTitle,
  onSelectCitation,
}: {
  chatId: number
  sourceTitle: string
  onSelectCitation: (segmentId: number) => void
}) {
  const queryClient = useQueryClient()
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const [busy, setBusy] = useState(false)
  const [excerpts, setExcerpts] = useState<Excerpt[]>([])
  const socketRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['chat', chatId],
    queryFn: () => api.chatMessages(chatId),
  })
  const messages = data?.messages ?? []

  useEffect(() => {
    const socket = openChatSocket(chatId, {
      onExcerpts: (items) => setExcerpts(items as Excerpt[]),
      onToken: (text) => setStreaming((current) => current + text),
      onDone: () => {
        setStreaming('')
        setBusy(false)
        void queryClient.invalidateQueries({ queryKey: ['chat', chatId] })
        void queryClient.invalidateQueries({ queryKey: ['chats'] })
      },
      onError: (message) => {
        setStreaming('')
        setBusy(false)
        toast.error(message)
      },
    })
    socketRef.current = socket
    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [chatId, queryClient])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, streaming])

  const send = (text: string) => {
    if (!text.trim() || busy) return
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast.error('Chat connection offline. Reconnecting...')
      return
    }
    setBusy(true)
    setStreaming('')
    setExcerpts([])
    ws.send(JSON.stringify({ text: text.trim() }))
    setInput('')
  }

  const SUGGESTED_PROMPTS = [
    `Summarize the key principles and formulas in ${sourceTitle}`,
    'What are the core definitions and their prerequisites?',
    'What failure modes or edge cases are discussed in this document?',
    'Generate 3 practice questions with step-by-step reasoning',
  ]

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-[var(--bg)]">
      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !streaming && (
          <div className="mx-auto max-w-md text-center py-8 space-y-3">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[var(--accent)]/10 text-[var(--accent)] mx-auto">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--text)]">DeepTutor Grounded Assistant</h3>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Ask any question about “{sourceTitle}”. Answers are grounded strictly in your source excerpts.
              </p>
            </div>
            <div className="space-y-1.5 pt-2">
              <p className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">Suggested Queries</p>
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => send(prompt)}
                  className="w-full text-left p-2 rounded-lg border border-[var(--border)] bg-[var(--bg-raised)] hover:border-[var(--accent)] text-xs text-[var(--text)] transition-colors shadow-xs"
                >
                  💬 {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={cn('flex flex-col', message.role === 'user' ? 'items-end' : 'items-start')}>
            <div
              className={cn(
                'rounded-2xl px-3.5 py-2.5 max-w-[85%] text-xs leading-relaxed',
                message.role === 'user'
                  ? 'bg-[var(--accent)] text-black font-medium rounded-br-xs'
                  : 'bg-[var(--bg-raised)] border border-[var(--border)] text-[var(--text)] rounded-bl-xs shadow-xs',
              )}
            >
              {message.role === 'user' ? (
                message.content
              ) : (
                <RenderGroundedContent content={message.content} onSelectCitation={onSelectCitation} />
              )}
            </div>

            {/* Citations metadata */}
            {message.role === 'assistant' && message.citations.length > 0 && (
              <div className="flex items-center gap-1.5 mt-1 text-[10px] text-[var(--text-muted)]">
                <span>Cited {message.citations.length} passage{message.citations.length === 1 ? '' : 's'}:</span>
                {message.citations.map((c) => (
                  <button
                    key={c}
                    onClick={() => onSelectCitation(c)}
                    className="font-mono px-1 rounded bg-[var(--accent-soft)] text-[var(--accent)] hover:underline"
                  >
                    #{c}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Live Token Streaming Output */}
        {streaming && (
          <div className="flex flex-col items-start">
            <div className="rounded-2xl rounded-bl-xs px-3.5 py-2.5 max-w-[85%] text-xs leading-relaxed bg-[var(--bg-raised)] border border-[var(--border)] text-[var(--text)] shadow-xs">
              <RenderGroundedContent content={streaming} onSelectCitation={onSelectCitation} />
              <span className="inline-block h-3.5 w-1.5 ml-1 animate-pulse bg-[var(--accent)]" />
            </div>
          </div>
        )}

        {/* Searching Status */}
        {busy && !streaming && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] p-2">
            <Spinner className="h-3.5 w-3.5 text-[var(--accent)]" />
            <span>
              {excerpts.length > 0
                ? `Synthesizing answer from ${excerpts.length} passages...`
                : 'Searching source knowledge...'}
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input Box */}
      <div className="p-3 border-t border-[var(--border)] bg-[var(--bg-raised)]">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          className="flex items-center gap-2"
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Ask a question about this source (Enter to send)..."
            rows={1}
            className="flex-1 min-h-[2.4rem] max-h-24 resize-none text-xs py-2 px-3 bg-[var(--bg-sunken)]"
          />
          <Button
            type="submit"
            variant="primary"
            size="icon"
            disabled={!input.trim() || busy}
            className="h-9 w-9 shrink-0"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  )
}

/**
 * Parses bracketed citations like [1] or [12] and renders clickable interactive pill badges
 */
function RenderGroundedContent({
  content,
  onSelectCitation,
}: {
  content: string
  onSelectCitation: (segmentId: number) => void
}) {
  const parts = useMemo(() => content.split(/(\[\d+\])/g), [content])

  return (
    <span className="whitespace-pre-wrap">
      {parts.map((part, index) => {
        const match = /^\[(\d+)\]$/.exec(part)
        if (match) {
          const segId = Number(match[1])
          return (
            <button
              key={index}
              type="button"
              onClick={() => onSelectCitation(segId)}
              className="mx-0.5 inline-flex items-center justify-center rounded px-1.5 py-0.2 bg-[var(--accent-soft)] hover:bg-[var(--accent)] hover:text-black text-[var(--accent)] font-mono font-bold text-[10px] transition-colors"
              title={`Jump to passage #${segId}`}
            >
              [{segId}]
            </button>
          )
        }
        return <span key={index}>{part}</span>
      })}
    </span>
  )
}

function ExportMenu({ noteId, sourceId }: { noteId: number; sourceId: number }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const formats = [
    { id: 'md', label: 'Markdown' },
    { id: 'docx', label: 'Word (.docx)' },
    { id: 'html', label: 'HTML' },
    { id: 'txt', label: 'Plain text' },
  ]
  return (
    <div className="relative">
      <Button size="sm" onClick={() => setOpen(!open)}>
        <Download className="h-3.5 w-3.5 mr-1" />
        <span className="hidden sm:inline">Export</span>
      </Button>
      {open && (
        <>
          <button className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-9 z-20 w-44 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-raised)] py-1 shadow-xl">
            {formats.map((format) => (
              <a
                key={format.id}
                href={api.exportUrl(noteId, format.id)}
                onClick={() => setOpen(false)}
                className="block px-3 py-1.5 text-xs hover:bg-[var(--bg-sunken)] text-[var(--text)]"
              >
                {format.label}
              </a>
            ))}
            <button
              onClick={() => {
                setOpen(false)
                navigate({
                  to: '/library/$sourceId',
                  params: { sourceId: String(sourceId) },
                  search: { print: true },
                })
              }}
              className="flex w-full items-center gap-2 border-t border-[var(--border)] px-3 py-1.5 text-left text-xs hover:bg-[var(--bg-sunken)] text-[var(--text)]"
            >
              <Printer className="h-3 w-3" /> Print / PDF
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function RegenerateDialog({
  open, onOpenChange, noteWasEdited, pending, onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  noteWasEdited: boolean
  pending: boolean
  onConfirm: (target: 'notes' | 'concepts' | 'cards' | 'quiz' | 'all', style: string) => void
}) {
  const [style, setStyle] = useState<string>('detailed')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Regenerate Course Materials</DialogTitle>
        <DialogDescription>
          Re-run AI processing for this source with current model providers.
        </DialogDescription>

        {noteWasEdited && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <p className="text-xs text-amber-400">
              You have manually edited these notes. Regenerating will replace existing notes.
            </p>
          </div>
        )}

        <Field label="Note style" hint={STYLES.find((s) => s.value === style)?.hint}>
          <Select value={style} onValueChange={setStyle}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STYLES.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          <Button variant="primary" loading={pending} onClick={() => onConfirm('notes', style)}>
            <FileText className="h-4 w-4 mr-1.5" /> Notes only
          </Button>
          <Button onClick={() => onConfirm('concepts', style)} disabled={pending}>
            <Sparkles className="h-4 w-4 mr-1.5" /> Concepts
          </Button>
          <Button onClick={() => onConfirm('cards', style)} disabled={pending}>
            <Brain className="h-4 w-4 mr-1.5" /> Flashcards
          </Button>
          <Button onClick={() => onConfirm('quiz', style)} disabled={pending}>
            <ListChecks className="h-4 w-4 mr-1.5" /> Quiz questions
          </Button>
          <Button className="sm:col-span-2" onClick={() => onConfirm('all', style)} disabled={pending}>
            <RefreshCw className="h-4 w-4 mr-1.5" /> Regenerate Everything
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
