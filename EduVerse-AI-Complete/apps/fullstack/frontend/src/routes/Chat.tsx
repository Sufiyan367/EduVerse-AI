import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearch, Link } from '@tanstack/react-router'
import {
  BookOpen, Check, Copy, ListChecks, MessageSquare,
  Plus, Send, Sparkles, Brain, Layers
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { api, ApiError } from '../lib/api'
import type { ChatMessage, Excerpt, Segment } from '../lib/types'
import { openChatSocket } from '../lib/ws'
import { useServerHealth, useActiveCourse } from '../lib/store'
import { cn, formatRelative } from '../lib/utils'
import {
  Badge, Button, Dialog, DialogContent, DialogTitle, EmptyState, Field, Select,
  SelectContent, SelectItem, SelectTrigger, SelectValue, Spinner, Textarea,
} from '../components/ui'

export function ChatPage() {
  const search: any = useSearch({ strict: false })
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [newOpen, setNewOpen] = useState(false)
  const { activeCourseId } = useActiveCourse()

  const { data: courses = [] } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })
  const activeCourse = courses.find((c: any) => c.id === activeCourseId) || null

  const { data } = useQuery({ queryKey: ['chats'], queryFn: () => api.listChats() })
  const chats = data?.chats ?? []
  const activeId = search?.id ? Number(search.id) : chats[0]?.id

  // Deep-linked from a source page: open (or create) a conversation scoped to it.
  const scopedCreate = useMutation({
    mutationFn: (sourceId: number) => api.createChat('source', sourceId),
    onSuccess: (chat) => {
      queryClient.invalidateQueries({ queryKey: ['chats'] })
      navigate({ to: '/chat', search: { id: chat.id } as any })
    },
  })

  useEffect(() => {
    if (search?.source && !search?.id) {
      const existing = chats.find(
        (chat) => chat.scope_type === 'source' && chat.scope_id === Number(search.source),
      )
      if (existing) navigate({ to: '/chat', search: { id: existing.id } as any })
      else if (!scopedCreate.isPending) scopedCreate.mutate(Number(search.source))
    } else if (search?.courseId && !search?.id) {
      const cId = Number(search.courseId)
      const existing = chats.find(
        (chat) => chat.scope_type === 'course' && chat.scope_id === cId,
      )
      if (existing) navigate({ to: '/chat', search: { id: existing.id } as any })
      else {
        api.createChat('course', cId, `Course: ${activeCourse?.code || cId}`).then((newChat) => {
          queryClient.invalidateQueries({ queryKey: ['chats'] })
          navigate({ to: '/chat', search: { id: newChat.id } as any })
        }).catch(() => {})
      }
    } else if (search?.topicId && !search?.id) {
      const tId = Number(search.topicId)
      const existing = chats.find(
        (chat) => chat.scope_type === 'topic' && chat.scope_id === tId,
      )
      if (existing) navigate({ to: '/chat', search: { id: existing.id } as any })
      else {
        api.createChat('topic', tId, `Topic: ${search.topicTitle || tId}`).then((newChat) => {
          queryClient.invalidateQueries({ queryKey: ['chats'] })
          navigate({ to: '/chat', search: { id: newChat.id } as any })
        }).catch(() => {})
      }
    }
  }, [search?.source, search?.courseId, search?.topicId, search?.id, chats.length])

  return (
    <div className="mx-auto flex h-full max-w-7xl">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card/30 md:flex">
        {/* Active Course Selector Header */}
        <div className="p-3 border-b border-border bg-muted/20">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <BookOpen className="h-3 w-3 text-primary" />
              Active Course Scope
            </span>
            <Link to="/courses" className="text-[10px] text-primary hover:underline">
              Change
            </Link>
          </div>
          {activeCourse ? (
            <div className="mt-1.5 flex items-center justify-between">
              <div className="min-w-0">
                <span className="text-xs font-bold text-foreground truncate block">
                  {activeCourse.code}: {activeCourse.name}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {activeCourse.unit_count || 0} units · {activeCourse.paper_count || 0} exam papers
                </span>
              </div>
            </div>
          ) : (
            <p className="mt-1 text-[11px] text-muted-foreground italic">
              All Indexed Sources (Global Library)
            </p>
          )}
        </div>

        <div className="flex items-center justify-between p-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Conversations
          </span>
          <Button variant="ghost" size="icon-sm" onClick={() => setNewOpen(true)} title="New chat">
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {chats.map((chat) => (
            <button
              key={chat.id}
              onClick={() => navigate({ to: '/chat', search: { id: chat.id } as any })}
              className={cn(
                'w-full rounded-lg px-2.5 py-2 text-left transition-colors',
                chat.id === activeId
                  ? 'bg-primary/10 text-primary border border-primary/20 font-medium'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground',
              )}
            >
              <p className="truncate text-xs font-semibold">{chat.title}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {chat.scope_type === 'global' ? 'Entire Library' : chat.scope_type} ·{' '}
                {formatRelative(chat.created_at)}
              </p>
            </button>
          ))}
          {chats.length === 0 && (
            <p className="px-2.5 py-4 text-xs text-muted-foreground text-center">No conversations yet.</p>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {activeId ? (
          <Conversation chatId={activeId} activeCourse={activeCourse} />
        ) : (
          <div className="grid flex-1 place-items-center p-6">
            <EmptyState
              icon={MessageSquare}
              title="Context-Aware Academic Tutor"
              description="Ask questions across lecture slides, syllabus units, and previous university exam papers. Every assertion is verified with verbatim quotes and page references."
              action={
                <Button variant="primary" onClick={() => setNewOpen(true)}>
                  <Plus className="h-4 w-4" /> Start New Conversation
                </Button>
              }
            />
          </div>
        )}
      </div>

      <NewChatDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  )
}

function NewChatDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { data: courses = [] } = useQuery({ queryKey: ['courses'], queryFn: () => api.listCourses() })
  const [scope, setScope] = useState<'global' | 'course' | 'source' | 'folder'>('global')
  const [scopeId, setScopeId] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.listSources({ status: 'ready' }),
  })
  const { data: folders } = useQuery({ queryKey: ['folders'], queryFn: () => api.listFolders() })

  const create = useMutation({
    mutationFn: () => api.createChat(scope, scope === 'global' ? null : Number(scopeId)),
    onSuccess: (chat) => {
      queryClient.invalidateQueries({ queryKey: ['chats'] })
      onOpenChange(false)
      navigate({ to: '/chat', search: { id: chat.id } as any })
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : 'Failed.'),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogTitle>New conversation</DialogTitle>
        <div className="space-y-4">
          <Field label="Scope" hint="Narrower scopes give more focused retrieval.">
            <Select value={scope} onValueChange={(value) => setScope(value as typeof scope)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="global">Entire library</SelectItem>
                <SelectItem value="course">Course workspace</SelectItem>
                <SelectItem value="source">One source</SelectItem>
                <SelectItem value="folder">One folder</SelectItem>
              </SelectContent>
            </Select>
          </Field>

          {scope === 'course' && (
            <Field label="Course Workspace">
              <Select value={scopeId} onValueChange={setScopeId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose course…" />
                </SelectTrigger>
                <SelectContent>
                  {(courses ?? []).map((c: any) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.code}: {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}

          {scope === 'source' && (
            <Field label="Source">
              <Select value={scopeId} onValueChange={setScopeId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose…" />
                </SelectTrigger>
                <SelectContent>
                  {(sources?.sources ?? []).map((source) => (
                    <SelectItem key={source.id} value={String(source.id)}>
                      {source.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}

          {scope === 'folder' && (
            <Field label="Folder">
              <Select value={scopeId} onValueChange={setScopeId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose…" />
                </SelectTrigger>
                <SelectContent>
                  {(folders?.folders ?? []).map((folder) => (
                    <SelectItem key={folder.id} value={String(folder.id)}>
                      {folder.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}

          <Button
            variant="primary"
            className="w-full justify-center"
            disabled={scope !== 'global' && !scopeId}
            loading={create.isPending}
            onClick={() => create.mutate()}
          >
            Start
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function Conversation({ chatId, activeCourse }: { chatId: number; activeCourse: any }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const llmStatus = useServerHealth((state) => state.llmStatus)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const [busy, setBusy] = useState(false)
  const [excerpts, setExcerpts] = useState<Excerpt[]>([])
  const [citation, setCitation] = useState<Segment | null>(null)
  const [copiedId, setCopiedId] = useState<number | null>(null)
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
        // Refresh messages in case server completed via background or recovery
        void queryClient.invalidateQueries({ queryKey: ['chat', chatId] })
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

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setStreaming('')
    setExcerpts([])
    setInput('')

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

    const socket = socketRef.current
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ content: trimmed }))
        return
      } catch (err) {
        console.warn('Socket send failed, falling back to HTTP:', err)
      }
    }

    // Seamless HTTP fallback if socket is reconnecting or unavailable
    try {
      await api.sendChatMessage(chatId, trimmed)
      setBusy(false)
      void queryClient.invalidateQueries({ queryKey: ['chat', chatId] })
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
    } catch (err: any) {
      setBusy(false)
      toast.error(err?.message || 'Failed to send message.')
    }
  }

  const handleCopy = (msgId: number, content: string) => {
    navigator.clipboard.writeText(content)
    setCopiedId(msgId)
    toast.success('Copied to clipboard')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant')

  return (
    <>
      {/* Tutor Header with Model Status and Active Course Scope */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-card/60 px-4 text-xs">
        <div className="flex items-center gap-2.5">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          <span className="font-semibold text-foreground">
            {llmStatus?.status === 'connected' ? `Model: ${llmStatus.model || 'qwen3.5:4b'}` : 'Local AI / Offline'}
          </span>
          {activeCourse && (
            <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded bg-primary/10 text-primary font-mono text-[11px] border border-primary/20">
              <BookOpen className="h-3 w-3" />
              {activeCourse.code}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground hidden sm:inline">
            Grounding: Hybrid Vector + BM25
          </span>
          <Badge tone={llmStatus?.status === 'connected' ? 'accent' : 'neutral'} className="text-[10px]">
            {llmStatus?.status === 'connected' ? 'GPU Ready' : 'Local Offline'}
          </Badge>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {llmStatus?.status === 'unavailable' && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
              💡 <strong>Local Ollama Offline:</strong> Start Ollama (`ollama serve`) to enable private GPU reasoning.
            </div>
          )}
          {messages.length === 0 && !streaming && (
            <div className="py-12 text-center space-y-3">
              <Sparkles className="mx-auto h-8 w-8 text-primary/70" />
              <h3 className="text-base font-semibold text-foreground">Academic Study Assistant</h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                Ask targeted conceptual questions, request syllabus breakdowns, or compare topics across previous university papers.
              </p>
              <div className="pt-2 flex flex-wrap justify-center gap-2">
                <button
                  onClick={() => send('Explain the core concepts and theorems covered in my course.')}
                  className="text-xs px-3 py-1.5 rounded-full border border-border bg-card hover:border-primary/50 text-muted-foreground hover:text-foreground transition-colors"
                >
                  &ldquo;Explain core concepts and theorems&rdquo;
                </button>
                <button
                  onClick={() => send('What are the most frequent exam questions on this subject?')}
                  className="text-xs px-3 py-1.5 rounded-full border border-border bg-card hover:border-primary/50 text-muted-foreground hover:text-foreground transition-colors"
                >
                  &ldquo;Most frequent exam questions&rdquo;
                </button>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className="space-y-2">
              <Bubble message={message} onCitation={setCitation} />

              {/* Action Toolbar on Assistant Messages */}
              {message.role === 'assistant' && (
                <div className="flex flex-wrap items-center gap-1.5 text-xs pt-1">
                  <button
                    onClick={() => handleCopy(message.id, message.content)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors text-[11px]"
                    title="Copy response"
                  >
                    {copiedId === message.id ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedId === message.id ? 'Copied' : 'Copy'}</span>
                  </button>
                  <button
                    onClick={() => send('Explain this in simpler terms with an intuitive analogy or everyday intuition.')}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border/70 hover:border-primary/40 text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors text-[11px]"
                    title="Explain simply"
                  >
                    <Sparkles className="h-3 w-3 text-teal-400" />
                    <span>Explain simply</span>
                  </button>
                  <button
                    onClick={() => send('Provide a step-by-step worked example demonstrating how this concept or formula is applied.')}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border/70 hover:border-primary/40 text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors text-[11px]"
                    title="Show worked example"
                  >
                    <BookOpen className="h-3 w-3 text-blue-400" />
                    <span>Show worked example</span>
                  </button>
                  <button
                    onClick={() => send('Compare and contrast the key concepts mentioned here with related principles in this course, highlighting common exam confusions.')}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border/70 hover:border-primary/40 text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors text-[11px]"
                    title="Compare concepts"
                  >
                    <Layers className="h-3 w-3 text-purple-400" />
                    <span>Compare concepts</span>
                  </button>
                  <button
                    onClick={() => navigate({ to: '/practice', search: { tab: 'quiz' } as any })}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-primary hover:bg-primary/10 transition-colors text-[11px]"
                  >
                    <ListChecks className="h-3 w-3" />
                    <span>Take Quiz</span>
                  </button>
                  <button
                    onClick={() => navigate({ to: '/practice', search: { tab: 'revision' } as any })}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-amber-400 hover:bg-amber-500/10 transition-colors text-[11px]"
                  >
                    <Brain className="h-3 w-3" />
                    <span>Schedule Revision</span>
                  </button>
                </div>
              )}
            </div>
          ))}

          {streaming && (
            <div className="space-y-2">
              <MessageBody content={streaming} onCitation={setCitation} />
              <span className="inline-block h-3.5 w-1.5 animate-pulse bg-primary" />
            </div>
          )}

          {busy && !streaming && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner className="h-3.5 w-3.5" />
              {excerpts.length > 0
                ? `Reading ${excerpts.length} passage${excerpts.length === 1 ? '' : 's'}…`
                : 'Searching indexed course notes & syllabus…'}
            </div>
          )}

          {!busy && lastAssistant?.followups && lastAssistant.followups.length > 0 && (
            <div className="space-y-1.5 pt-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Follow-up Suggestions
              </span>
              <div className="flex flex-wrap gap-1.5">
                {lastAssistant.followups.map((question) => (
                  <button
                    key={question}
                    onClick={() => send(question)}
                    className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-border p-3 sm:p-4 bg-card/40">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                send(input)
              }
            }}
            rows={1}
            placeholder="Ask a question about your syllabus, lecture notes, or past papers…"
            className="max-h-40 min-h-[2.5rem] resize-none py-2"
          />
          <Button
            variant="primary"
            size="icon"
            disabled={!input.trim() || busy}
            onClick={() => send(input)}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Dialog open={!!citation} onOpenChange={(open) => !open && setCitation(null)}>
        <DialogContent>
          <DialogTitle>Source Passage & Evidence</DialogTitle>
          {citation && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {citation.timestamp && <Badge tone="accent">{citation.timestamp}</Badge>}
                {citation.page_no && <Badge>Page {citation.page_no}</Badge>}
                {citation.speaker && <span>{citation.speaker}</span>}
              </div>
              <p className="rounded-lg bg-muted/40 p-3 text-sm leading-relaxed text-foreground border border-border">
                {citation.text}
              </p>
              <Button
                variant="primary"
                className="w-full justify-center text-xs"
                onClick={() => {
                  window.location.href = `/library/${citation.source_id}?tab=transcript&seg=${citation.id}`
                }}
              >
                Open in Source Material
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

function Bubble({
  message, onCitation,
}: {
  message: ChatMessage
  onCitation: (segment: Segment) => void
}) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm text-primary-foreground font-medium">
          {message.content}
        </div>
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <MessageBody content={message.content} onCitation={onCitation} />
      {message.citations.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          {message.citations.length} source
          {message.citations.length === 1 ? '' : 's'} cited — click a badge to verify evidence
        </p>
      )}
    </div>
  )
}

function MessageBody({
  content, onCitation,
}: {
  content: string
  onCitation: (segment: Segment) => void
}) {
  const parts = useMemo(() => content.split(/(\[\d+\])/g), [content])

  const open = async (segmentId: number) => {
    try {
      const result = await api.resolveCitations([segmentId])
      const segment = result.segments[0]
      if (segment) onCitation(segment)
      else toast.error('That passage no longer exists.')
    } catch {
      toast.error('Could not load that passage.')
    }
  }

  return (
    <div className="text-[15px] leading-relaxed text-foreground">
      {parts.map((part, index) => {
        const match = /^\[(\d+)\]$/.exec(part)
        if (match) {
          const id = Number(match[1])
          return (
            <button
              key={index}
              onClick={() => open(id)}
              className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-primary/20 px-1 align-super text-[10px] font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
              title="Show source evidence"
            >
              {id}
            </button>
          )
        }
        return (
          <span key={index} className="whitespace-pre-wrap">
            {part}
          </span>
        )
      })}
    </div>
  )
}
