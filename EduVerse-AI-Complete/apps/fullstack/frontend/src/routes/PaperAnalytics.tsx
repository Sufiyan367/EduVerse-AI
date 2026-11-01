import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { FileText, TrendingUp, Sparkles, Plus, BarChart3 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Button, Input, Modal } from '../components/ui'

export function PaperAnalyticsPage() {
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

  // Analytics query
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['paper-analytics', selectedCourseId],
    queryFn: () => (selectedCourseId ? api.getPaperAnalytics(selectedCourseId) : null),
    enabled: !!selectedCourseId,
  })

  // Past papers list query
  const { data: papers = [] } = useQuery({
    queryKey: ['papers', selectedCourseId],
    queryFn: () => (selectedCourseId ? api.listPapers(selectedCourseId) : []),
    enabled: !!selectedCourseId,
  })

  const { data: sources = [] } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.listSources().then(r => r.sources),
  })

  // Modals state
  const [createPaperOpen, setCreatePaperOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [examTerm, setExamTerm] = useState('End-Sem')
  const [examYear, setExamYear] = useState(2024)
  const [totalMarks, setTotalMarks] = useState(70)
  const [selectedSourceId, setSelectedSourceId] = useState<number | undefined>(undefined)

  const [extractOpen, setExtractOpen] = useState(false)
  const [targetPaperId, setTargetPaperId] = useState<number | null>(null)
  const [paperRawText, setPaperRawText] = useState('')

  // Create Paper Mutation
  const createPaperMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId) throw new Error('No course selected')
      return api.createPaper(selectedCourseId, {
        title,
        exam_term: examTerm,
        exam_year: Number(examYear),
        total_marks: Number(totalMarks),
        source_id: selectedSourceId,
      })
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['papers', selectedCourseId] })
      queryClient.invalidateQueries({ queryKey: ['paper-analytics', selectedCourseId] })
      setCreatePaperOpen(false)
      setTitle('')
      toast.success('Past paper registered! You can now extract its questions.')
      setTargetPaperId(data.id)
      setExtractOpen(true)
    },
  })

  // Extract Questions Mutation
  const extractQuestionsMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId || !targetPaperId) throw new Error('Selection missing')
      return api.extractPaperQuestions(selectedCourseId, {
        paper_id: targetPaperId,
        raw_text: paperRawText,
      })
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['papers', selectedCourseId] })
      queryClient.invalidateQueries({ queryKey: ['paper-analytics', selectedCourseId] })
      setExtractOpen(false)
      setPaperRawText('')
      toast.success(`Extracted ${data.questions_extracted || 0} questions and mapped to syllabus topics!`)
    },
    onError: (err: any) => {
      toast.error(err.message || 'Question extraction failed')
    },
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Header & Course Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <TrendingUp className="h-7 w-7 text-amber-500" />
            Previous Paper Intelligence
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Topic frequency analysis, recurring questions, unit mark weightage, and high-yield exam predictions.
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

          <Button onClick={() => setCreatePaperOpen(true)} className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Add Past Exam Paper
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 rounded-xl border border-border bg-card animate-pulse" />
          ))}
        </div>
      ) : !analytics ? (
        <div className="text-center py-16 border border-dashed border-border rounded-xl bg-card/50">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4" />
          <h3 className="text-lg font-medium text-foreground">Select a course to view paper analytics</h3>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Key Intelligence Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Exam Papers Analyzed</div>
              <div className="text-2xl font-bold text-foreground mt-1">{analytics.total_papers_analyzed}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Questions Indexed</div>
              <div className="text-2xl font-bold text-foreground mt-1">{analytics.total_questions_cataloged}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">High-Yield Topics</div>
              <div className="text-2xl font-bold text-amber-500 mt-1">{analytics.high_yield_topics.length}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Analytics Confidence</div>
              <div className="text-2xl font-bold text-emerald-500 mt-1">
                {analytics.total_papers_analyzed >= 2 ? 'High' : 'Moderate'}
              </div>
            </div>
          </div>

          {/* High-Yield Topics Frequency Ranking */}
          <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border bg-muted/20 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-primary" />
                  Exam Topic Frequency & Marks Ranking
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Topics appearing repeatedly across past university exams, sorted by frequency and marks density.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/40 text-xs font-semibold text-muted-foreground uppercase border-b border-border">
                  <tr>
                    <th className="px-6 py-3">Topic</th>
                    <th className="px-4 py-3">Bloom's Level</th>
                    <th className="px-4 py-3 text-center">Past Frequency</th>
                    <th className="px-4 py-3 text-center">Total Marks Tested</th>
                    <th className="px-6 py-3 text-right">Yield Prediction</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {analytics.all_topic_frequencies.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-muted-foreground italic text-xs">
                        No past paper questions mapped yet. Upload and extract a previous exam paper above.
                      </td>
                    </tr>
                  ) : (
                    analytics.all_topic_frequencies.map((t: any, idx: number) => (
                      <tr key={t.topic_id} className="hover:bg-muted/20 transition-colors">
                        <td className="px-6 py-3 font-medium text-foreground">
                          <span className="font-mono text-xs text-muted-foreground mr-2">#{idx + 1}</span>
                          {t.topic_name}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-muted border border-border">
                            {t.bloom_level}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center font-bold text-foreground">
                          {t.frequency} {t.frequency === 1 ? 'time' : 'times'}
                        </td>
                        <td className="px-4 py-3 text-center font-mono text-primary font-semibold">
                          {t.total_marks_tested} M
                        </td>
                        <td className="px-6 py-3 text-right">
                          <span
                            className={`text-xs font-semibold px-2 py-0.5 rounded-md ${
                              t.exam_yield === 'High'
                                ? 'bg-amber-500/15 text-amber-500 border border-amber-500/30'
                                : t.exam_yield === 'Medium'
                                ? 'bg-blue-500/15 text-blue-500 border border-blue-500/30'
                                : 'bg-muted text-muted-foreground'
                            }`}
                          >
                            {t.exam_yield}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Unit Marks Breakdown vs Syllabus Weightage */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
              <h3 className="text-base font-semibold text-foreground mb-4">Unit Marks Distribution</h3>
              <div className="space-y-4">
                {analytics.unit_distribution.map((u: any) => (
                  <div key={u.unit_number} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-foreground">
                        Unit {u.unit_number}: {u.unit_title}
                      </span>
                      <span className="text-primary font-mono">{u.past_paper_marks} Marks Tested</span>
                    </div>
                    <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, (u.past_paper_marks / 50) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Cataloged Past Papers */}
            <div className="rounded-xl border border-border bg-card p-6 shadow-sm flex flex-col justify-between">
              <div>
                <h3 className="text-base font-semibold text-foreground mb-4">Cataloged Past Papers</h3>
                {papers.length === 0 ? (
                  <p className="text-xs text-muted-foreground italic">No past papers uploaded for this course yet.</p>
                ) : (
                  <div className="space-y-3">
                    {papers.map((p: any) => (
                      <div
                        key={p.id}
                        className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/20"
                      >
                        <div>
                          <div className="text-sm font-medium text-foreground">{p.title}</div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {p.exam_term} {p.exam_year} • {p.total_marks} Marks • {p.question_count} questions
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setTargetPaperId(p.id)
                            setExtractOpen(true)
                          }}
                          className="h-7 text-xs gap-1"
                        >
                          <Sparkles className="h-3 w-3 text-primary" />
                          AI Extract
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-border">
                <Button onClick={() => setCreatePaperOpen(true)} variant="secondary" className="w-full text-xs">
                  Register Another Past Paper
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create Paper */}
      <Modal open={createPaperOpen} onClose={() => setCreatePaperOpen(false)} title="Register Past Exam Paper">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (title) createPaperMutation.mutate()
          }}
          className="space-y-4 pt-2"
        >
          <div>
            <label className="text-xs font-medium text-foreground">Paper Title</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. End-Sem Exam Nov/Dec 2024"
              required
              className="mt-1"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-foreground">Exam Term</label>
              <select
                value={examTerm}
                onChange={(e) => setExamTerm(e.target.value)}
                className="mt-1 w-full h-9 px-3 py-1 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="In-Sem">In-Sem (Mid-Term)</option>
                <option value="End-Sem">End-Sem (Final)</option>
                <option value="Remedial">Remedial / Supplementary</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-foreground">Exam Year</label>
              <Input
                type="number"
                value={examYear}
                onChange={(e) => setExamYear(Number(e.target.value))}
                min={2018}
                max={2030}
                required
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground">Total Marks</label>
              <Input
                type="number"
                value={totalMarks}
                onChange={(e) => setTotalMarks(Number(e.target.value))}
                min={10}
                max={150}
                required
                className="mt-1"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-foreground">Link Scanned Paper (Optional)</label>
            <select
              value={selectedSourceId || ''}
              onChange={(e) => setSelectedSourceId(e.target.value ? Number(e.target.value) : undefined)}
              className="mt-1 w-full h-9 px-3 py-1 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">-- Choose from Study Library --</option>
              {sources.map((s: any) => (
                <option key={s.id} value={s.id}>
                  {s.title} ({s.page_count} pages)
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => setCreatePaperOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!title || createPaperMutation.isPending}>
              Register Paper
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: AI Extract Paper Questions */}
      <Modal open={extractOpen} onClose={() => setExtractOpen(false)} title="AI Question Paper Parser">
        <div className="space-y-4 pt-2">
          <p className="text-xs text-muted-foreground">
            Ollama Qwen3.5:4b will extract questions, marks, and cognitive demand, and automatically link them to syllabus topics.
          </p>

          <textarea
            value={paperRawText}
            onChange={(e) => setPaperRawText(e.target.value)}
            placeholder="Paste raw text or questions from the past exam paper..."
            rows={8}
            className="w-full p-2.5 bg-card border border-border rounded-md text-sm text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button variant="secondary" onClick={() => setExtractOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => extractQuestionsMutation.mutate()}
              disabled={extractQuestionsMutation.isPending}
            >
              {extractQuestionsMutation.isPending ? 'Extracting with Ollama...' : 'Parse & Index Questions'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
