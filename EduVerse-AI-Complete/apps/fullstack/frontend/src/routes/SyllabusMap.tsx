import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { Layers, Sparkles, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Button, Input, Modal } from '../components/ui'

export function SyllabusMapPage() {
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

  // Active course syllabus query
  const { data: syllabus, isLoading } = useQuery({
    queryKey: ['syllabus', selectedCourseId],
    queryFn: () => (selectedCourseId ? api.getSyllabus(selectedCourseId) : null),
    enabled: !!selectedCourseId,
  })

  // Modals state
  const [extractOpen, setExtractOpen] = useState(false)
  const [rawText, setRawText] = useState('')
  const [selectedSourceId, setSelectedSourceId] = useState<number | undefined>(undefined)

  const [addUnitOpen, setAddUnitOpen] = useState(false)
  const [unitNumber, setUnitNumber] = useState(1)
  const [unitTitle, setUnitTitle] = useState('')
  const [weightage, setWeightage] = useState(16.6)

  const [addTopicOpen, setAddTopicOpen] = useState(false)
  const [targetUnitId, setTargetUnitId] = useState<number | null>(null)
  const [topicName, setTopicName] = useState('')
  const [bloomLevel, setBloomLevel] = useState('Understand')

  const { data: sources = [] } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.listSources().then(r => r.sources),
  })

  // Extract Syllabus Mutation
  const extractMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId) throw new Error('No course selected')
      return api.extractSyllabus(selectedCourseId, {
        source_id: selectedSourceId,
        raw_text: rawText,
      })
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['syllabus', selectedCourseId] })
      setExtractOpen(false)
      setRawText('')
      toast.success(data.message || `Successfully extracted ${data.units_extracted || 0} units and ${data.topics_extracted || 0} topics!`)
    },
    onError: (err: any) => {
      toast.error(err.message || 'Syllabus extraction failed')
    },
  })

  // Add Unit Mutation
  const addUnitMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId) throw new Error('No course selected')
      return api.addUnit(selectedCourseId, {
        unit_number: Number(unitNumber),
        title: unitTitle,
        weightage_percent: Number(weightage),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syllabus', selectedCourseId] })
      setAddUnitOpen(false)
      setUnitTitle('')
      toast.success('Unit added successfully')
    },
  })

  // Add Topic Mutation
  const addTopicMutation = useMutation({
    mutationFn: () => {
      if (!selectedCourseId || !targetUnitId) throw new Error('Selection missing')
      return api.addTopic(selectedCourseId, {
        unit_id: targetUnitId,
        name: topicName,
        bloom_level: bloomLevel,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syllabus', selectedCourseId] })
      setAddTopicOpen(false)
      setTopicName('')
      toast.success('Topic added')
    },
  })

  // Delete Topic Mutation
  const deleteTopicMutation = useMutation({
    mutationFn: (topicId: number) => {
      if (!selectedCourseId) throw new Error('No course selected')
      return api.deleteTopic(selectedCourseId, topicId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syllabus', selectedCourseId] })
      toast.success('Topic removed')
    },
  })

  const getBloomBadgeClass = (level: string) => {
    switch (level.toLowerCase()) {
      case 'remember':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
      case 'understand':
        return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
      case 'apply':
        return 'bg-purple-500/10 text-purple-500 border-purple-500/20'
      case 'analyze':
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20'
      case 'evaluate':
      case 'create':
        return 'bg-rose-500/10 text-rose-500 border-rose-500/20'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Header & Course Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <Layers className="h-7 w-7 text-primary" />
            Syllabus & Cognitive Topic Map
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Modular unit breakdowns, Bloom's cognitive taxonomy levels, and course outcome alignment.
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

          <Button onClick={() => setExtractOpen(true)} variant="secondary" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            AI Syllabus Parser
          </Button>

          <Button onClick={() => setAddUnitOpen(true)} className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Add Unit
          </Button>
        </div>
      </div>

      {/* Main Content */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 rounded-xl border border-border bg-card animate-pulse" />
          ))}
        </div>
      ) : !syllabus || syllabus.units.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border rounded-xl bg-card/50">
          <Layers className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4" />
          <h3 className="text-lg font-medium text-foreground">Syllabus not configured for this course</h3>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mt-1 mb-6">
            Use the AI Syllabus Parser to automatically import units and topics from your syllabus PDF, or add units manually.
          </p>
          <div className="flex justify-center gap-3">
            <Button onClick={() => setExtractOpen(true)}>
              <Sparkles className="h-4 w-4 mr-2" />
              Auto-Extract with AI
            </Button>
            <Button variant="secondary" onClick={() => setAddUnitOpen(true)}>
              Add Unit Manually
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Curriculum Units</div>
              <div className="text-2xl font-bold text-foreground mt-1">{syllabus.total_units}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Total Cataloged Topics</div>
              <div className="text-2xl font-bold text-foreground mt-1">{syllabus.total_topics}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Course Outcomes (COs)</div>
              <div className="text-2xl font-bold text-foreground mt-1">{syllabus.outcomes.length || 6}</div>
            </div>
            <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs text-muted-foreground font-medium">Target Exam Coverage</div>
              <div className="text-2xl font-bold text-emerald-500 mt-1">100%</div>
            </div>
          </div>

          {/* Units and Topics List */}
          <div className="space-y-6">
            {syllabus.units.map((u: any) => (
              <div key={u.id} className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between px-6 py-4 bg-muted/30 border-b border-border/80 gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                        Unit {u.unit_number}
                      </span>
                      <h3 className="text-base font-semibold text-foreground">{u.title}</h3>
                    </div>
                    {u.description && <p className="text-xs text-muted-foreground mt-1">{u.description}</p>}
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium text-muted-foreground">
                      Weightage: <strong className="text-foreground">{u.weightage_percent}%</strong>
                    </span>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setTargetUnitId(u.id)
                        setAddTopicOpen(true)
                      }}
                      className="h-8 text-xs gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Add Topic
                    </Button>
                  </div>
                </div>

                {/* Topics Grid */}
                <div className="p-6">
                  {u.topics.length === 0 ? (
                    <div className="text-xs text-muted-foreground py-2 italic">
                      No topics added to this unit yet. Click "Add Topic" to populate.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {u.topics.map((t: any) => (
                        <div
                          key={t.id}
                          className="flex items-start justify-between p-3.5 rounded-lg border border-border/70 bg-card hover:bg-muted/20 transition-colors group"
                        >
                          <div className="space-y-1.5 pr-2">
                            <div className="text-sm font-medium text-foreground line-clamp-2">{t.name}</div>
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span
                                className={`text-[10px] font-medium border px-1.5 py-0.5 rounded-md ${getBloomBadgeClass(
                                  t.bloom_level
                                )}`}
                              >
                                {t.bloom_level}
                              </span>
                              <span className="text-[10px] text-muted-foreground font-mono bg-muted/60 px-1.5 py-0.5 rounded">
                                Yield: {t.importance_score}x
                              </span>
                            </div>
                          </div>
                          <button
                            onClick={() => deleteTopicMutation.mutate(t.id)}
                            className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive p-1 transition-opacity"
                            title="Remove topic"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modal: AI Syllabus Parser */}
      <Modal open={extractOpen} onClose={() => setExtractOpen(false)} title="AI Syllabus Parser">
        <div className="space-y-4 pt-2">
          <p className="text-xs text-muted-foreground">
            Automatically extract curriculum units and topics using local Ollama Qwen3.5:4b.
          </p>

          <div>
            <label className="text-xs font-medium text-foreground">Select Uploaded Syllabus Document</label>
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

          <div className="relative">
            <div className="text-xs text-muted-foreground text-center my-1 uppercase font-semibold">— OR Paste Syllabus Text —</div>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste units, modules, and topic listings directly from your university PDF..."
              rows={6}
              className="mt-1 w-full p-2.5 bg-card border border-border rounded-md text-sm text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button variant="secondary" onClick={() => setExtractOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => extractMutation.mutate()}
              disabled={(!selectedSourceId && !rawText.trim()) || extractMutation.isPending}
            >
              {extractMutation.isPending ? 'Extracting with Ollama...' : 'Extract Syllabus'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Add Unit */}
      <Modal open={addUnitOpen} onClose={() => setAddUnitOpen(false)} title="Add Syllabus Unit">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (unitTitle) addUnitMutation.mutate()
          }}
          className="space-y-4 pt-2"
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-foreground">Unit Number</label>
              <Input
                type="number"
                value={unitNumber}
                onChange={(e) => setUnitNumber(Number(e.target.value))}
                min={1}
                max={20}
                required
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground">Weightage (%)</label>
              <Input
                type="number"
                value={weightage}
                onChange={(e) => setWeightage(Number(e.target.value))}
                step="0.1"
                min={0}
                max={100}
                className="mt-1"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-foreground">Unit Title</label>
            <Input
              value={unitTitle}
              onChange={(e) => setUnitTitle(e.target.value)}
              placeholder="e.g. Unit 1: Foundations of Artificial Intelligence"
              required
              className="mt-1"
            />
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => setAddUnitOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!unitTitle || addUnitMutation.isPending}>
              Add Unit
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Add Topic */}
      <Modal open={addTopicOpen} onClose={() => setAddTopicOpen(false)} title="Add Topic to Unit">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (topicName) addTopicMutation.mutate()
          }}
          className="space-y-4 pt-2"
        >
          <div>
            <label className="text-xs font-medium text-foreground">Topic Name</label>
            <Input
              value={topicName}
              onChange={(e) => setTopicName(e.target.value)}
              placeholder="e.g. Heuristic Search Algorithms (A* and Greedy Best-First)"
              required
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-foreground">Bloom's Taxonomy Cognitive Level</label>
            <select
              value={bloomLevel}
              onChange={(e) => setBloomLevel(e.target.value)}
              className="mt-1 w-full h-9 px-3 py-1 bg-card border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="Remember">Remember (Recall definitions, facts)</option>
              <option value="Understand">Understand (Explain concepts, block diagrams)</option>
              <option value="Apply">Apply (Execute algorithms, solve problems)</option>
              <option value="Analyze">Analyze (Derive tradeoffs, compare architectures)</option>
              <option value="Evaluate">Evaluate (Assess performance, critique designs)</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => setAddTopicOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!topicName || addTopicMutation.isPending}>
              Add Topic
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
