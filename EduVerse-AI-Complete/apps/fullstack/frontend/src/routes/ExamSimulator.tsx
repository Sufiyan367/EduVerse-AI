import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { Award, Sparkles, Send, ChevronRight, ChevronLeft } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Button, Input, Modal, Badge } from '../components/ui'

export function ExamSimulatorPage() {
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

  // Active Session State
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [currentQIndex, setCurrentQIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [startOpen, setStartOpen] = useState(false)
  const [examTitle, setExamTitle] = useState('In-Sem Exam Simulation (50M)')
  const [maxScore, setMaxScore] = useState(50)
  const [qCount, setQCount] = useState(5)

  // Simulation Session Query
  const { data: sessionData } = useQuery({
    queryKey: ['simulator-session', activeSessionId],
    queryFn: () => (activeSessionId ? api.getSimulationSession(activeSessionId) : null),
    enabled: !!activeSessionId,
  })

  // Past Attempts Query
  const { data: history = [] } = useQuery({
    queryKey: ['simulator-history'],
    queryFn: () => api.getExamHistory(),
  })

  // Populate answers when session loads
  useEffect(() => {
    if (sessionData && sessionData.questions) {
      const map: Record<number, string> = {}
      for (const q of sessionData.questions) {
        if (q.student_answer) map[q.id] = q.student_answer
      }
      setAnswers((prev) => ({ ...map, ...prev }))
    }
  }, [sessionData])

  // Start Simulation Mutation
  const startMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId) throw new Error('Select a course first')
      return api.generateSimulation(selectedCourseId, {
        title: examTitle,
        max_score: Number(maxScore),
        question_count: Number(qCount),
      })
    },
    onSuccess: (data: any) => {
      setStartOpen(false)
      setActiveSessionId(data.session_id)
      setCurrentQIndex(0)
      setAnswers({})
      queryClient.invalidateQueries({ queryKey: ['simulator-history'] })
      toast.success('Exam simulation generated! Good luck.')
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to generate simulation')
    },
  })

  // Submit Exam Mutation
  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!activeSessionId || !sessionData) return
      const payload = sessionData.questions.map((q: any) => ({
        question_id: q.id,
        student_answer: answers[q.id] || '',
      }))
      await api.submitExam(activeSessionId, payload)
      // Automatically trigger AI grading
      return api.gradeExam(activeSessionId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['simulator-session', activeSessionId] })
      queryClient.invalidateQueries({ queryKey: ['simulator-history'] })
      toast.success('Exam submitted and graded by AI Professor!')
    },
    onError: (err: any) => {
      toast.error(err.message || 'Submission or grading failed')
    },
  })

  const currentQ = sessionData?.questions?.[currentQIndex]
  const isGraded = sessionData?.status === 'graded'

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <Award className="h-7 w-7 text-emerald-500" />
            University Exam Simulator & AI Rubric Assessment
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Timed realistic exam simulations with automated university rubric evaluations powered by Qwen3.5:4b.
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

          <Button onClick={() => setStartOpen(true)} className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Start Simulation
          </Button>
        </div>
      </div>

      {/* Main View: Either Active Exam or Exam Portal / History */}
      {activeSessionId && sessionData ? (
        <div className="space-y-6">
          {/* Active Session Status Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 rounded-xl border border-border bg-card shadow-sm gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-primary/10 text-primary">
                  SESSION #{sessionData.id}
                </span>
                <h2 className="text-base font-bold text-foreground">{sessionData.title}</h2>
                <Badge tone={isGraded ? 'success' : 'neutral'} className="text-xs">
                  {sessionData.status.toUpperCase()}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Started {new Date(sessionData.started_at).toLocaleTimeString()} • Max Marks: {sessionData.max_score}M
              </p>
            </div>

            <div className="flex items-center gap-3">
              {isGraded ? (
                <div className="flex items-center gap-4 bg-muted/30 px-4 py-2 rounded-lg border border-border">
                  <div className="text-right">
                    <div className="text-xs text-muted-foreground">Overall Score</div>
                    <div className="text-lg font-bold text-emerald-500">
                      {sessionData.total_score} / {sessionData.max_score} (
                      {Math.round(((sessionData.total_score || 0) / sessionData.max_score) * 100)}%)
                    </div>
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => setActiveSessionId(null)}>
                    Exit to History
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <Button
                    onClick={() => {
                      if (confirm('Submit all your answers for AI professor grading?')) {
                        submitMutation.mutate()
                      }
                    }}
                    disabled={submitMutation.isPending}
                    className="flex items-center gap-2"
                  >
                    <Send className="h-4 w-4" />
                    {submitMutation.isPending ? 'Grading with AI...' : 'Submit Exam for Grading'}
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => setActiveSessionId(null)}>
                    Exit
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Question Navigation Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {sessionData.questions.map((q: any, idx: number) => {
              const hasAnswer = Boolean(answers[q.id]?.trim())
              const isCurrent = idx === currentQIndex
              return (
                <button
                  key={q.id}
                  onClick={() => setCurrentQIndex(idx)}
                  className={`px-4 py-2 rounded-lg text-xs font-medium border transition-all flex items-center gap-2 whitespace-nowrap ${
                    isCurrent
                      ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                      : hasAnswer
                      ? 'bg-card text-foreground border-border hover:bg-muted/40'
                      : 'bg-muted/30 text-muted-foreground border-border/60 hover:bg-muted/60'
                  }`}
                >
                  <span>Q{q.order}</span>
                  {hasAnswer && !isGraded && <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
                  {isGraded && q.feedback && (
                    <span className="font-mono font-bold text-[10px]">
                      {q.feedback.score_awarded}/{q.marks}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Active Question Box */}
          {currentQ && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Question Statement & Input */}
              <div className="lg:col-span-8 rounded-xl border border-border bg-card p-6 shadow-sm space-y-5">
                <div className="flex items-start justify-between gap-4 border-b border-border/80 pb-4">
                  <div>
                    <span className="text-xs font-semibold text-primary uppercase tracking-wide">
                      Question {currentQ.order} of {sessionData.questions.length}
                    </span>
                    <h3 className="text-lg font-semibold text-foreground mt-1">{currentQ.question_text}</h3>
                  </div>
                  <div className="text-right whitespace-nowrap">
                    <span className="px-2.5 py-1 rounded-md bg-muted text-foreground font-mono text-xs font-bold border border-border">
                      {currentQ.marks} Marks
                    </span>
                    <div className="text-[11px] text-muted-foreground mt-1">{currentQ.topic_name}</div>
                  </div>
                </div>

                {/* Answer Area */}
                <div>
                  <label className="text-xs font-medium text-foreground flex items-center justify-between mb-1.5">
                    <span>Your Detailed Answer / Solution:</span>
                    <span className="text-muted-foreground font-mono text-[11px]">
                      {answers[currentQ.id]?.trim() ? `${answers[currentQ.id].trim().split(/\s+/).length} words` : '0 words'}
                    </span>
                  </label>
                  <textarea
                    value={answers[currentQ.id] || ''}
                    onChange={(e) => setAnswers({ ...answers, [currentQ.id]: e.target.value })}
                    disabled={isGraded}
                    rows={12}
                    placeholder="Write your structured solution here. State definitions, architectural assumptions, working steps, algorithm formulas, and design tradeoffs..."
                    className="w-full p-3.5 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-sans leading-relaxed disabled:opacity-80"
                  />
                </div>

                {/* Nav buttons */}
                <div className="flex items-center justify-between pt-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={currentQIndex === 0}
                    onClick={() => setCurrentQIndex(currentQIndex - 1)}
                    className="gap-1 text-xs"
                  >
                    <ChevronLeft className="h-4 w-4" /> Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={currentQIndex === sessionData.questions.length - 1}
                    onClick={() => setCurrentQIndex(currentQIndex + 1)}
                    className="gap-1 text-xs"
                  >
                    Next <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* Rubric Feedback / AI Professor Grading Panel */}
              <div className="lg:col-span-4 rounded-xl border border-border bg-card p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <h4 className="text-sm font-bold text-foreground flex items-center gap-2 mb-3">
                    <Sparkles className="h-4 w-4 text-primary" />
                    AI Rubric Evaluation
                  </h4>

                  {isGraded && currentQ.feedback ? (
                    <div className="space-y-4 text-xs">
                      <div className="bg-muted/40 p-3 rounded-lg border border-border">
                        <div className="text-muted-foreground font-medium">Marks Awarded</div>
                        <div className="text-xl font-bold text-emerald-500 mt-0.5">
                          {currentQ.feedback.score_awarded} / {currentQ.marks} M
                        </div>
                      </div>

                      {/* Criteria Scores */}
                      <div className="space-y-2">
                        <div className="font-semibold text-foreground">Rubric Criteria Breakdown:</div>
                        <div className="space-y-1.5 font-mono text-[11px] bg-background p-2.5 rounded border border-border">
                          {Object.entries(currentQ.feedback.criterion_scores || {}).map(([crit, pts]: any) => (
                            <div key={crit} className="flex justify-between">
                              <span className="capitalize">{crit.replace(/_/g, ' ')}:</span>
                              <strong className="text-primary">{pts} pts</strong>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Strengths */}
                      <div>
                        <div className="font-semibold text-emerald-500 mb-1">Key Strengths:</div>
                        <p className="text-muted-foreground bg-emerald-500/5 border border-emerald-500/20 p-2 rounded">
                          {currentQ.feedback.strengths || 'Accurate general concept coverage.'}
                        </p>
                      </div>

                      {/* Weaknesses */}
                      <div>
                        <div className="font-semibold text-amber-500 mb-1">Missing Elements & Weaknesses:</div>
                        <p className="text-muted-foreground bg-amber-500/5 border border-amber-500/20 p-2 rounded">
                          {currentQ.feedback.weaknesses || 'Missing complete step-by-step formulas.'}
                        </p>
                      </div>

                      {/* Recommendations */}
                      <div>
                        <div className="font-semibold text-foreground mb-1">Professor's Advice:</div>
                        <p className="text-muted-foreground bg-muted/40 p-2 rounded italic">
                          "{currentQ.feedback.suggestions || 'Practice deriving the architecture diagram under exam conditions.'}"
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground space-y-3">
                      <p>
                        Your answers are evaluated according to official university examination rubrics:
                      </p>
                      <ul className="list-disc pl-4 space-y-1 text-[11px]">
                        <li>50% Conceptual Accuracy & Soundness</li>
                        <li>30% Formulas, Equations & Steps</li>
                        <li>20% Diagram Clarity & Terminology</li>
                      </ul>
                      <p className="text-[11px] italic bg-muted/30 p-2 rounded">
                        Submit the exam when finished to receive instant criterion-by-criterion marks and feedback.
                      </p>
                    </div>
                  )}
                </div>

                <div className="mt-6 pt-4 border-t border-border text-[11px] text-muted-foreground font-mono">
                  Evaluator: Qwen3.5:4b (Local GPU Inference)
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* History & Standby Portal */
        <div className="space-y-6">
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-foreground">Exam Simulation Engine</h2>
              <p className="text-xs text-muted-foreground mt-1 max-w-xl">
                Practice full-length or modular university exams under real test conditions. Tests are composed from
                syllabus units and verified against past exam blueprints.
              </p>
            </div>
            <Button onClick={() => setStartOpen(true)} className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              Generate New Exam Simulation
            </Button>
          </div>

          {/* Past Attempts Table */}
          <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border bg-muted/20">
              <h3 className="text-sm font-bold text-foreground">Previous Exam Attempts & Score Reports</h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/40 text-xs font-semibold text-muted-foreground uppercase border-b border-border">
                  <tr>
                    <th className="px-6 py-3">Course</th>
                    <th className="px-6 py-3">Simulation Title</th>
                    <th className="px-4 py-3 text-center">Status</th>
                    <th className="px-4 py-3 text-center">Marks</th>
                    <th className="px-6 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {history.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-muted-foreground italic text-xs">
                        No previous exam simulations found. Click "Generate New Exam Simulation" to start.
                      </td>
                    </tr>
                  ) : (
                    history.map((h: any) => (
                      <tr key={h.id} className="hover:bg-muted/20 transition-colors">
                        <td className="px-6 py-3 font-semibold text-foreground">{h.course_name}</td>
                        <td className="px-6 py-3 text-muted-foreground">{h.title}</td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                              h.status === 'graded'
                                ? 'bg-emerald-500/15 text-emerald-500'
                                : 'bg-amber-500/15 text-amber-500'
                            }`}
                          >
                            {h.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center font-bold text-foreground">
                          {h.total_score !== null ? `${h.total_score} / ${h.max_score} (${h.percentage}%)` : '—'}
                        </td>
                        <td className="px-6 py-3 text-right">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setActiveSessionId(h.id)}
                            className="h-8 text-xs"
                          >
                            {h.status === 'graded' ? 'View Evaluation' : 'Resume Exam'}
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Generate Simulation */}
      <Modal open={startOpen} onClose={() => setStartOpen(false)} title="Generate Simulated Exam">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (selectedCourseId) startMutation.mutate()
          }}
          className="space-y-4 pt-2"
        >
          <div>
            <label className="text-xs font-medium text-foreground">Select Course</label>
            <select
              value={selectedCourseId || ''}
              onChange={(e) => setSelectedCourseId(Number(e.target.value))}
              className="mt-1 w-full h-9 px-3 py-1 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {courses.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.code}: {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-foreground">Exam Title</label>
            <Input
              value={examTitle}
              onChange={(e) => setExamTitle(e.target.value)}
              placeholder="e.g. Mid-Term Simulation 50M"
              required
              className="mt-1"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-foreground">Total Marks</label>
              <Input
                type="number"
                value={maxScore}
                onChange={(e) => setMaxScore(Number(e.target.value))}
                min={10}
                max={100}
                required
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground">Number of Questions</label>
              <Input
                type="number"
                value={qCount}
                onChange={(e) => setQCount(Number(e.target.value))}
                min={2}
                max={15}
                required
                className="mt-1"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => setStartOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!selectedCourseId || startMutation.isPending}>
              {startMutation.isPending ? 'Generating...' : 'Start Exam'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
