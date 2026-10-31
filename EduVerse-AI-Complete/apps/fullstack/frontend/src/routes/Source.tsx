import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import {
  AlertTriangle, Brain, Download, FileText, Layers, ListChecks,
  Pencil, Printer, RefreshCw, Sparkles, Trash2, Send, Search as SearchIcon,
  ChevronLeft, ChevronRight, LayoutGrid, Maximize2,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { api, ApiError } from '../lib/api'
import { useJobs, usePlayer } from '../lib/store'
import type { ChatMessage, Excerpt, NoteStyle } from '../lib/types'
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

  // View Layout Modes: 'studio' (Google NotebookLM 3-column) or 'reader' (full notes)
  const [layoutMode, setLayoutMode] = useState<'studio' | 'reader'>('studio')
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)

  const [tab, setTab] = useState(search.tab ?? 'notes')
  const [highlightIds, setHighlightIds] = useState<number[]>([])
  const [segmentQuery, setSegmentQuery] = useState('')
  const [regenOpen, setRegenOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

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

  const { data, isLoading } = useQuery({
    queryKey: ['source', id],
    queryFn: () => api.getSource(id),
    refetchInterval: (query) => {
      const status = query.state.data?.source?.status
      if (status === 'pending' || status === 'processing' || activeJob) {
        return 2000
      }
      return false
    },
  })

  const { data: segmentData } = useQuery({
    queryKey: ['segments', id],
    queryFn: () => api.getSegments(id),
    enabled: !!data && data.counts.segments > 0,
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
    } else if (data && !scopedChatId) {
      api.createChat('source', id).then((created) => {
        setScopedChatId(created.id)
        void queryClient.invalidateQueries({ queryKey: ['chats'] })
      }).catch(() => {
        // Fallback or offline
      })
    }
  }, [existingChat, data, id, scopedChatId, queryClient])

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

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  const { source, note, counts } = data
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
              {source.page_count ? <span>· {source.page_count} pgs</span> : null}
              {source.duration_sec ? <span>· {formatDuration(source.duration_sec)}</span> : null}
              <span>· {counts.segments} passages</span>
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
                title="NotebookLM 3-column Studio workspace"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span className="hidden md:inline">NotebookLM Studio</span>
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

            <Button
              size="sm"
              variant="secondary"
              onClick={() => navigate({ to: '/quiz', search: { source: id } })}
              title="Practice adaptive quiz on this source"
            >
              <ListChecks className="h-3.5 w-3.5 mr-1" />
              <span className="hidden sm:inline">Quiz</span>
            </Button>

            <Button
              size="sm"
              variant="secondary"
              disabled={counts.cards === 0}
              onClick={() => navigate({ to: '/review', search: { source: id } })}
              title="Review FSRS spaced repetition cards"
            >
              <Brain className="h-3.5 w-3.5 mr-1" />
              <span className="hidden sm:inline">Cards</span>
            </Button>

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
      </header>

      {/* Main Workspace Body */}
      {layoutMode === 'reader' ? (
        // Fullscreen Reader Mode
        <div className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full">
          {note ? (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
              <Card>
                <CardBody className="px-6 py-6 sm:px-10 sm:py-8">
                  <NoteEditor
                    noteId={note.id}
                    doc={note.doc}
                    onAnchorClick={jumpToSource}
                    onDirty={() => queryClient.setQueryData(['source', id], (old: typeof data) =>
                      old?.note ? { ...old, note: { ...old.note, is_dirty: true } } : old,
                    )}
                  />
                </CardBody>
              </Card>

              {note.outline.length > 0 && (
                <aside className="hidden lg:block">
                  <div className="sticky top-4 space-y-2">
                    <p className="px-2 text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Outline
                    </p>
                    <nav className="space-y-0.5">
                      {note.outline.map((item, index) => (
                        <a
                          key={index}
                          href={`#heading-${item.index}`}
                          onClick={(e) => {
                            e.preventDefault()
                            const headings = document.querySelectorAll('.ProseMirror h1, .ProseMirror h2, .ProseMirror h3')
                            const seen = Array.from(headings).find((h) => h.textContent === item.text)
                            seen?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                          }}
                          className={cn(
                            'block truncate rounded px-2 py-1 text-xs text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)] transition-colors',
                            item.level >= 3 && 'pl-4 text-[11px]',
                          )}
                        >
                          {item.text}
                        </a>
                      ))}
                    </nav>
                  </div>
                </aside>
              )}
            </div>
          ) : (
            <Card className="mt-8">
              <EmptyState
                icon={FileText}
                title="No notes written yet"
                description="Generate structured syllabus notes for this document with our AI pipeline."
                action={
                  <Button variant="primary" onClick={() => regenerate.mutate({ target: 'notes' })}>
                    Generate notes now
                  </Button>
                }
              />
            </Card>
          )}
        </div>
      ) : (
        // Google NotebookLM 3-Column Studio Workspace
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Column 1: Source & Excerpts Inspector (Collapsible Left) */}
          <div
            className={cn(
              'shrink-0 border-r border-[var(--border)] bg-[var(--bg-raised)] flex flex-col transition-all duration-200',
              leftOpen ? 'w-80 md:w-84 xl:w-96' : 'w-10 items-center',
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
                      return (
                        <div
                          key={segment.id}
                          id={`segment-${segment.id}`}
                          onClick={() => {
                            setHighlightIds([segment.id])
                            if (segment.start_ms != null) usePlayer.getState().seekTo(segment.start_ms)
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
                            {segment.page_no && (
                              <Badge className="text-[9px] px-1 py-0">Page {segment.page_no}</Badge>
                            )}
                            {segment.timestamp && (
                              <span className="font-mono text-[10px]">{segment.timestamp}</span>
                            )}
                          </div>
                          <p className="text-[12px] leading-relaxed text-[var(--text)] line-clamp-4">
                            {segment.text}
                          </p>
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
          <div className="flex-1 flex flex-col min-w-0 bg-[var(--bg)] border-r border-[var(--border)] relative">
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

          {/* Column 3: Studio & Study Tools (Collapsible Right) */}
          <div
            className={cn(
              'shrink-0 bg-[var(--bg-raised)] flex flex-col transition-all duration-200',
              rightOpen ? 'w-96 xl:w-[28rem]' : 'w-10 items-center border-l border-[var(--border)]',
            )}
          >
            {rightOpen ? (
              <div className="flex flex-col h-full overflow-hidden">
                <div className="flex items-center justify-between p-2.5 border-b border-[var(--border)] bg-[var(--bg-sunken)]/40">
                  <Tabs value={tab} onValueChange={setTab} className="w-full">
                    <div className="flex items-center justify-between">
                      <TabsList className="h-8">
                        <TabsTrigger value="notes" className="text-xs px-2.5 py-1">
                          <FileText className="h-3 w-3 mr-1" /> Notes
                        </TabsTrigger>
                        <TabsTrigger value="concepts" className="text-xs px-2.5 py-1">
                          <Sparkles className="h-3 w-3 mr-1" /> Concepts
                          <Badge className="ml-1 text-[9px] px-1">{counts.concepts}</Badge>
                        </TabsTrigger>
                        <TabsTrigger value="cards" className="text-xs px-2.5 py-1">
                          <Brain className="h-3 w-3 mr-1" /> Cards
                          <Badge className="ml-1 text-[9px] px-1">{counts.cards}</Badge>
                        </TabsTrigger>
                      </TabsList>

                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-[var(--text-muted)]"
                        onClick={() => setRightOpen(false)}
                        title="Collapse studio panel"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="mt-2" />

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
                            onDirty={() => queryClient.setQueryData(['source', id], (old: typeof data) =>
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

                    <TabsContent value="concepts" className="m-0 flex-1 overflow-y-auto p-3">
                      <ConceptsTab
                        sourceId={id}
                        onJump={jumpToSource}
                        onExtract={() => regenerate.mutate({ target: 'concepts' })}
                        isExtracting={regenerate.isPending || !!activeJob}
                      />
                    </TabsContent>

                    <TabsContent value="cards" className="m-0 flex-1 overflow-y-auto p-3">
                      <CardsTab
                        sourceId={id}
                        count={counts.cards}
                        onGenerate={() => regenerate.mutate({ target: 'cards' })}
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
                  title="Expand studio panel"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="[writing-mode:vertical-rl] text-xs font-semibold text-[var(--text-muted)] tracking-wider">
                  STUDIO TOOLS
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
 * Embedded Grounded AI Tutor Chat component inside the NotebookLM Studio
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
    const trimmed = text.trim()
    if (!trimmed || busy) return
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      toast.error('Connecting to AI Tutor... Try again in a moment.')
      return
    }
    setBusy(true)
    setStreaming('')
    setExcerpts([])
    setInput('')

    // Optimistic user bubble
    queryClient.setQueryData(['chat', chatId], (old: typeof data) =>
      old
        ? {
            ...old,
            messages: [
              ...old.messages,
              {
                id: -Date.now(),
                chat_id: chatId,
                role: 'user',
                content: trimmed,
                citations: [],
                followups: [],
                created_at: new Date().toISOString(),
              } as ChatMessage,
            ],
          }
        : old,
    )
    socket.send(JSON.stringify({ content: trimmed }))
  }

  const SUGGESTED_PROMPTS = [
    'Summarize key ideas in this document',
    'What formulas or definitions are introduced?',
    'Create 3 practice questions from this material',
  ]

  return (
    <div className="flex-1 flex flex-col h-full min-h-0">
      {/* Scrollable messages container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !streaming && (
          <div className="max-w-md mx-auto text-center py-8 space-y-4">
            <div className="grid h-10 w-10 mx-auto place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--text)]">NotebookLM Grounded Tutor</h3>
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

function ConceptsTab({
  sourceId,
  onJump,
  onExtract,
  isExtracting,
}: {
  sourceId: number
  onJump: (ids: number[]) => void
  onExtract?: () => void
  isExtracting?: boolean
}) {
  const { data } = useQuery({
    queryKey: ['concepts', sourceId],
    queryFn: () => api.getConcepts(sourceId),
  })
  const concepts = data?.concepts ?? []

  if (concepts.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={Sparkles}
          title="No concepts extracted yet"
          description="Concepts are key curriculum units flashcards and quiz questions are built from."
          action={
            onExtract && (
              <Button variant="primary" size="sm" disabled={isExtracting} onClick={onExtract}>
                <Sparkles className="h-4 w-4 mr-1" /> Extract concepts
              </Button>
            )
          }
        />
      </Card>
    )
  }

  return (
    <div className="space-y-2.5">
      {concepts.map((concept) => (
        <Card key={concept.id}>
          <CardBody className="p-3">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-xs font-bold text-[var(--text)]">{concept.name}</h3>
              <Badge tone={concept.importance >= 4 ? 'accent' : 'neutral'} className="text-[10px]">
                {'★'.repeat(concept.importance)}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-[var(--text-muted)] line-clamp-2">{concept.definition}</p>
            <div className="mt-2.5 flex items-center gap-2">
              <Progress
                value={concept.mastery * 100}
                tone={concept.mastery >= 0.8 ? 'success' : concept.mastery < 0.35 ? 'danger' : 'accent'}
                className="flex-1 h-1.5"
              />
              <span className="tabular-nums text-[10px] text-[var(--text-muted)]">
                {Math.round(concept.mastery * 100)}%
              </span>
              {concept.segment_ids.length > 0 && (
                <Button variant="ghost" size="icon-sm" onClick={() => onJump(concept.segment_ids)} title="View in source">
                  <Layers className="h-3 w-3 text-[var(--accent)]" />
                </Button>
              )}
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  )
}

function CardsTab({
  sourceId, count, onGenerate,
}: {
  sourceId: number
  count: number
  onGenerate: () => void
}) {
  const { data } = useQuery({
    queryKey: ['cards', sourceId],
    queryFn: () => api.listCards(sourceId),
    enabled: count > 0,
  })
  const navigate = useNavigate()

  if (count === 0) {
    return (
      <Card>
        <EmptyState
          icon={Brain}
          title="No flashcards yet"
          description="Cards are generated from syllabus concepts and scheduled with FSRS."
          action={<Button size="sm" variant="primary" onClick={onGenerate}>Generate flashcards</Button>}
        />
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="primary" onClick={() => navigate({ to: '/review', search: { source: sourceId } })}>
          <Brain className="h-3.5 w-3.5 mr-1" /> Practice Now
        </Button>
        <Button
          size="sm"
          onClick={async () => {
            try {
              const { blob } = await api.exportAnki({ source_ids: [sourceId] })
              const { downloadBlob } = await import('../lib/utils')
              downloadBlob(blob, 'eduverse_cards.apkg')
              toast.success('Exported to Anki.')
            } catch (error) {
              toast.error(error instanceof ApiError ? error.message : 'Export failed.')
            }
          }}
        >
          <Download className="h-3.5 w-3.5 mr-1" /> Anki
        </Button>
      </div>

      <div className="space-y-2">
        {(data?.cards ?? []).map((card) => (
          <Card key={card.id}>
            <CardBody className="p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold text-[var(--text)]">{card.front}</p>
                <Badge className="text-[9px] px-1">{card.type}</Badge>
              </div>
              <p className="mt-1 border-t border-[var(--border)] pt-1 text-xs text-[var(--text-muted)]">
                {card.back}
              </p>
              <div className="mt-1.5 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                <span>{card.state}</span>
                <span>{card.reps} reviews {card.lapses > 0 && `· ${card.lapses} lapses`}</span>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  )
}
