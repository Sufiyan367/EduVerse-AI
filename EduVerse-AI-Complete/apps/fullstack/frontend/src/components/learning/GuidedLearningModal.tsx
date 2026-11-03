import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  BookOpen, CheckCircle2, ChevronRight,
  RotateCcw, Sparkles, FileText, ArrowRight,
  AlertTriangle, Calendar
} from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../../lib/api'
import { Badge, Button, Modal, Spinner } from '../ui'

interface GuidedLearningModalProps {
  courseId: number
  topicId: number | null
  open: boolean
  onClose: () => void
  onStatusChange?: (newStatus: string) => void
}

export function GuidedLearningModal({
  courseId,
  topicId,
  open,
  onClose,
  onStatusChange,
}: GuidedLearningModalProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [activeStep, setActiveStep] = useState<'overview' | 'explanation' | 'quiz' | 'result'>('overview')
  const [explainMode, setExplainMode] = useState<'standard' | 'simple' | 'example' | 'compare'>('standard')
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({})
  const [quizResult, setQuizResult] = useState<any>(null)

  // Reset step when topic changes
  useEffect(() => {
    setActiveStep('overview')
    setQuizAnswers({})
    setQuizResult(null)
  }, [topicId])

  const { data: context, isLoading } = useQuery({
    queryKey: ['guided-learning', courseId, topicId],
    queryFn: () => (topicId ? api.getGuidedLearning(courseId, topicId) : null),
    enabled: !!topicId && open,
  })

  const { data: explanation, isFetching: isExplaining } = useQuery({
    queryKey: ['guided-learning-explain', courseId, topicId, explainMode],
    queryFn: () => (topicId ? api.explainTopic(courseId, topicId, explainMode) : null),
    enabled: !!topicId && open && activeStep === 'explanation',
  })

  const { data: quizData, isFetching: isGeneratingQuiz } = useQuery({
    queryKey: ['guided-learning-quiz', courseId, topicId],
    queryFn: () => (topicId ? api.getTopicKnowledgeCheck(courseId, topicId) : null),
    enabled: !!topicId && open && activeStep === 'quiz',
  })

  const startMutation = useMutation({
    mutationFn: () => api.startTopicLearning(courseId, topicId!),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['guided-learning', courseId, topicId] })
      queryClient.invalidateQueries({ queryKey: ['syllabus', courseId] })
      queryClient.invalidateQueries({ queryKey: ['course-progress', courseId] })
      setActiveStep('explanation')
      onStatusChange?.(res.status)
      toast.success('Guided learning session started!')
    },
  })

  const submitQuizMutation = useMutation({
    mutationFn: (payload: { answers: Array<{ question_id: number; selected_option: string }>; quiz_token: string }) =>
      api.submitTopicKnowledgeCheck(courseId, topicId!, payload.answers, payload.quiz_token),
    onSuccess: (res: any) => {
      setQuizResult(res)
      setActiveStep('result')
      queryClient.invalidateQueries({ queryKey: ['guided-learning', courseId, topicId] })
      queryClient.invalidateQueries({ queryKey: ['syllabus', courseId] })
      queryClient.invalidateQueries({ queryKey: ['course-progress', courseId] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      onStatusChange?.(res.new_status)
      const formattedStatus = String(res.new_status || '').replace('_', ' ')
      if (res.passed) {
        toast.success(`Knowledge check passed! Topic status: ${formattedStatus}.`)
      } else {
        toast.warning(`Knowledge check score: ${res.score_percent}%. Topic flagged as ${formattedStatus}.`)
      }
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to submit quiz session'
      toast.error(msg)
    },
  })

  const revisionMutation = useMutation({
    mutationFn: () => api.scheduleTopicRevision(courseId, topicId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      toast.success('Scheduled adaptive revision task!')
    },
  })

  if (!open || !topicId) return null

  const topic = context?.topic
  const lifecycle = context?.lifecycle
  const status = lifecycle?.status || 'not_started'

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'mastered':
        return <Badge tone="success" className="text-xs">Mastered</Badge>
      case 'needs_review':
        return <Badge tone="danger" className="text-xs">Needs Review</Badge>
      case 'learning':
        return <Badge tone="accent" className="text-xs">Learning</Badge>
      case 'practicing':
        return <Badge tone="warning" className="text-xs">Practicing</Badge>
      default:
        return <Badge className="text-xs">Not Started</Badge>
    }
  }

  const handleOptionSelect = (qId: number, opt: string) => {
    setQuizAnswers((prev) => ({ ...prev, [qId]: opt }))
  }

  const handleSubmitQuiz = () => {
    const questions = quizData?.questions || []
    if (questions.length === 0) {
      toast.error('No questions available to submit.')
      return
    }
    const unanswered = questions.filter((q: any) => !quizAnswers[q.id])
    if (unanswered.length > 0) {
      toast.error(`Please answer all ${questions.length} questions before submitting.`)
      return
    }
    if (!quizData?.quiz_token) {
      toast.error('Quiz security token missing. Please refresh questions.')
      return
    }
    const answers = questions.map((q: any) => ({
      question_id: q.id,
      selected_option: quizAnswers[q.id],
    }))
    submitQuizMutation.mutate({ answers, quiz_token: quizData.quiz_token })
  }

  return (
    <Modal open={open} onClose={onClose} title="">
      <div className="space-y-5 -mt-2">
        {/* Header Breadcrumbs & Status */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>{topic?.course_code || 'Course'}</span>
              <ChevronRight className="h-3 w-3" />
              <span>Unit {topic?.unit_number}</span>
              <ChevronRight className="h-3 w-3" />
              <span className="font-semibold text-foreground truncate max-w-xs">{topic?.name}</span>
            </div>
            <h2 className="text-lg font-bold text-foreground mt-1 flex items-center gap-2">
              <span>{topic?.name}</span>
              {getStatusBadge(status)}
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground font-mono">
              Bloom: {topic?.bloom_level}
            </span>
          </div>
        </div>

        {/* Step Navigation Pill Bar */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-muted/30 border border-border text-xs">
          <button
            onClick={() => setActiveStep('overview')}
            className={`flex-1 py-1.5 px-2 rounded-md font-medium text-center transition-colors ${
              activeStep === 'overview'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            1. Overview & Material
          </button>
          <button
            onClick={() => setActiveStep('explanation')}
            className={`flex-1 py-1.5 px-2 rounded-md font-medium text-center transition-colors ${
              activeStep === 'explanation'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            2. Tutor Explanation
          </button>
          <button
            onClick={() => setActiveStep('quiz')}
            className={`flex-1 py-1.5 px-2 rounded-md font-medium text-center transition-colors ${
              activeStep === 'quiz' || activeStep === 'result'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            3. Knowledge Check
          </button>
        </div>

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center gap-3">
            <Spinner className="h-6 w-6 text-primary" />
            <p className="text-xs text-muted-foreground">Loading topic learning intelligence...</p>
          </div>
        ) : (
          <div>
            {/* STEP 1: OVERVIEW & SOURCE MATERIAL */}
            {activeStep === 'overview' && (
              <div className="space-y-4">
                {/* Objectives */}
                <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-2">
                  <h3 className="text-xs font-semibold text-foreground flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    Learning Objectives
                  </h3>
                  <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
                    {context?.learning_objectives.map((obj: string, i: number) => (
                      <li key={i}>{obj}</li>
                    ))}
                  </ul>
                </div>

                {/* Prerequisites */}
                {context?.prerequisites && context.prerequisites.length > 0 && (
                  <div className="p-3 rounded-lg border border-border bg-muted/20 text-xs">
                    <span className="font-semibold text-foreground">Recommended Prerequisites: </span>
                    <span className="text-muted-foreground">
                      {context.prerequisites.map((p: any) => p.name).join(', ')}
                    </span>
                  </div>
                )}

                {/* Linked Source Materials & Citations */}
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-foreground flex items-center gap-2">
                    <FileText className="h-4 w-4 text-amber-500" />
                    Verified Course Materials & Source Passages
                  </h3>

                  {context?.has_source_evidence ? (
                    <div className="space-y-2">
                      {context.evidence_snippets.map((snip: any) => (
                        <div key={snip.id} className="p-3 rounded-lg border border-border/70 bg-card text-xs space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                            <span className="font-medium text-foreground">{snip.source_title}</span>
                            <Badge tone="accent" className="text-[10px]">Page {snip.page_no || 'N/A'}</Badge>
                          </div>
                          <p className="text-muted-foreground italic line-clamp-2">
                            &ldquo;{snip.text}&rdquo;
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl border border-dashed border-amber-500/40 bg-amber-500/5 text-xs text-amber-300 space-y-1.5">
                      <div className="flex items-center gap-2 font-semibold text-amber-200">
                        <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                        No Uploaded Course Materials For This Topic
                      </div>
                      <p className="text-muted-foreground">
                        No uploaded PDF lecture notes cover this topic yet. Explanations and checks are generated from foundational academic curricula without verified citations.
                      </p>
                    </div>
                  )}
                </div>

                {/* Bottom Action */}
                <div className="pt-3 border-t border-border flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    Status: <strong className="text-foreground capitalize">{status.replace('_', ' ')}</strong>
                  </span>
                  <Button
                    onClick={() => {
                      if (status === 'not_started') {
                        startMutation.mutate()
                      } else {
                        setActiveStep('explanation')
                      }
                    }}
                    className="gap-2 text-xs"
                    disabled={startMutation.isPending}
                  >
                    <span>{status === 'not_started' ? 'Begin Learning' : 'View Tutor Explanation'}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}

            {/* STEP 2: TUTOR EXPLANATION */}
            {activeStep === 'explanation' && (
              <div className="space-y-4">
                {/* Mode Selector Chips */}
                <div className="flex items-center gap-2 flex-wrap">
                  {(['standard', 'simple', 'example', 'compare'] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setExplainMode(m)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                        explainMode === m
                          ? 'border-primary bg-primary/10 text-primary font-semibold'
                          : 'border-border text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {m === 'standard' && 'Core Principle'}
                      {m === 'simple' && 'Simple Analogy'}
                      {m === 'example' && 'Worked Example'}
                      {m === 'compare' && 'Compare Concepts'}
                    </button>
                  ))}
                </div>

                {isExplaining ? (
                  <div className="py-12 flex flex-col items-center justify-center gap-2">
                    <Spinner className="h-5 w-5 text-primary" />
                    <p className="text-xs text-muted-foreground">Formulating explanation...</p>
                  </div>
                ) : explanation ? (
                  <div className="space-y-3.5 text-xs">
                    {explanation.disclaimer && (
                      <div className="p-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-[11px] text-amber-300">
                        {explanation.disclaimer}
                      </div>
                    )}

                    {/* Summary */}
                    <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-1.5">
                      <h4 className="font-semibold text-foreground text-xs">Conceptual Overview</h4>
                      <p className="text-muted-foreground leading-relaxed text-xs">{explanation.summary}</p>
                    </div>

                    {/* Key Definitions */}
                    {explanation.definitions && explanation.definitions.length > 0 && (
                      <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-2">
                        <h4 className="font-semibold text-foreground text-xs">Essential Definitions</h4>
                        <div className="space-y-1.5">
                          {explanation.definitions.map((d: any, idx: number) => (
                            <div key={idx} className="bg-muted/30 p-2 rounded-md">
                              <span className="font-semibold text-foreground">{d.term}: </span>
                              <span className="text-muted-foreground">{d.definition}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Worked Example */}
                    {explanation.worked_example && (
                      <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-1.5">
                        <h4 className="font-semibold text-foreground text-xs">Worked Example / Application</h4>
                        <pre className="p-2.5 rounded-lg bg-muted/40 text-foreground font-mono text-[11px] whitespace-pre-wrap leading-relaxed">
                          {explanation.worked_example}
                        </pre>
                      </div>
                    )}
                  </div>
                ) : null}

                {/* Bottom Actions */}
                <div className="pt-3 border-t border-border flex items-center justify-between">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      onClose()
                      navigate({
                        to: '/chat',
                        search: { source: undefined } as any,
                      })
                    }}
                    className="text-xs gap-1.5"
                  >
                    <BookOpen className="h-3.5 w-3.5 text-primary" />
                    <span>Open in Tutor Chat</span>
                  </Button>

                  <Button
                    onClick={() => setActiveStep('quiz')}
                    size="sm"
                    className="gap-2 text-xs"
                  >
                    <span>Take Knowledge Check</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}

            {/* STEP 3: KNOWLEDGE CHECK */}
            {activeStep === 'quiz' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="text-xs text-muted-foreground">
                    Answer all {quizData?.questions?.length || 10} questions to verify comprehension and advance topic mastery.
                  </span>
                  <Badge tone="accent" className="text-[10px]">≥80% Mastered (8+ / 10) • 70-79% Practicing (7 / 10) • &lt;70% Needs Review (≤6 / 10)</Badge>
                </div>

                {isGeneratingQuiz ? (
                  <div className="py-12 flex flex-col items-center justify-center gap-2">
                    <Spinner className="h-5 w-5 text-primary" />
                    <p className="text-xs text-muted-foreground">Generating diagnostic questions...</p>
                  </div>
                ) : quizData?.available === false ? (
                  <div className="p-4 rounded-xl border border-dashed border-amber-500/40 bg-amber-500/5 text-xs text-amber-300 space-y-2">
                    <div className="flex items-center gap-2 font-semibold text-amber-200">
                      <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                      Diagnostic Questions Currently Unavailable
                    </div>
                    <p className="text-muted-foreground leading-relaxed">
                      {quizData.message || 'Diagnostic questions cannot be reliably formed without course materials or an active LLM provider. Please upload course materials or connect an LLM provider.'}
                    </p>
                  </div>
                ) : quizData ? (
                  <div className="max-h-[55vh] overflow-y-auto pr-1 space-y-4">
                    {quizData.questions.map((q: any, idx: number) => {
                      const selected = quizAnswers[q.id]
                      const optionLetters = ['A', 'B', 'C', 'D']
                      return (
                        <div key={q.id} className="p-3.5 rounded-xl border border-border bg-card/60 space-y-2 text-xs">
                          <p className="font-semibold text-foreground">
                            {idx + 1}. {q.question_text}
                          </p>
                          <div className="space-y-1.5 pt-1">
                            {q.options.map((opt: string, oIdx: number) => {
                              const letter = optionLetters[oIdx]
                              const isSelected = selected === letter
                              return (
                                <button
                                  key={oIdx}
                                  onClick={() => handleOptionSelect(q.id, letter)}
                                  className={`w-full text-left p-2 rounded-lg border transition-colors flex items-start gap-2.5 ${
                                    isSelected
                                      ? 'border-primary bg-primary/10 text-primary font-medium'
                                      : 'border-border/70 hover:bg-muted/40 text-muted-foreground hover:text-foreground'
                                  }`}
                                >
                                  <span className={`h-4 w-4 rounded-full border flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                                    isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
                                  }`}>
                                    {letter}
                                  </span>
                                  <span className="leading-snug">{opt}</span>
                                </button>
                              )
                            })}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : null}

                <div className="pt-3 border-t border-border flex justify-end">
                  <Button
                    onClick={handleSubmitQuiz}
                    disabled={submitQuizMutation.isPending || !quizData}
                    className="gap-2 text-xs"
                  >
                    {submitQuizMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                    <span>Submit & Evaluate Answers</span>
                  </Button>
                </div>
              </div>
            )}

            {/* STEP 4: KNOWLEDGE CHECK RESULTS & ACTION */}
            {activeStep === 'result' && quizResult && (
              <div className="space-y-4">
                {/* Result Hero Banner */}
                <div className={`p-4 rounded-xl border ${
                  quizResult.new_status === 'mastered'
                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                    : quizResult.new_status === 'practicing'
                    ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                    : 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                } space-y-2`}>
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm flex items-center gap-1.5">
                      {quizResult.new_status === 'mastered' && '✓ Topic Mastered'}
                      {quizResult.new_status === 'practicing' && '⚡ Topic Practicing'}
                      {quizResult.new_status === 'needs_review' && '⚠ Needs Further Review'}
                    </span>
                    <span className="text-base font-bold font-mono">
                      {quizResult.score_percent}%
                    </span>
                  </div>
                  {quizResult.status_reason && (
                    <p className="text-xs text-foreground/90 font-medium leading-relaxed">
                      {quizResult.status_reason}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {quizResult.next_action}
                  </p>
                </div>

                {/* Mistake Analysis */}
                {quizResult.mistakes && quizResult.mistakes.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-rose-400">Mistakes to Remediate:</h4>
                    {quizResult.mistakes.map((m: any, idx: number) => (
                      <div key={idx} className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/5 text-xs space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Your answer: <strong>{m.selected}</strong></span>
                          <span className="text-emerald-400">Correct: <strong>{m.expected}</strong></span>
                        </div>
                        <p className="text-muted-foreground text-[11px]">{m.explanation}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="pt-3 border-t border-border flex items-center justify-between flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => revisionMutation.mutate()}
                    disabled={revisionMutation.isPending}
                    className="text-xs gap-1.5"
                  >
                    <Calendar className="h-3.5 w-3.5 text-primary" />
                    <span>Schedule Revision Task</span>
                  </Button>

                  <div className="flex items-center gap-2">
                    {!quizResult.passed && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setQuizAnswers({})
                          setActiveStep('quiz')
                        }}
                        className="text-xs gap-1.5"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        <span>Retry Check</span>
                      </Button>
                    )}
                    <Button
                      size="sm"
                      onClick={onClose}
                      className="text-xs"
                    >
                      Done
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
