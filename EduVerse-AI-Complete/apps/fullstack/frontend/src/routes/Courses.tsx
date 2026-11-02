import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { useSearch, useNavigate } from '@tanstack/react-router'
import {
  BookOpen, Plus, Layers, FileText, Award, Trash2, ArrowRight,
  CheckCircle2, Sparkles, RotateCcw, ChevronRight, LayoutGrid
} from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Button, Input, Modal, Badge } from '../components/ui'
import { useActiveCourse } from '../lib/store'
import { SyllabusMapPage } from './SyllabusMap'
import { PaperAnalyticsPage } from './PaperAnalytics'
import { ExamSimulatorPage } from './ExamSimulator'
import { AdaptiveRevisionPage } from './AdaptiveRevision'

type TabType = 'overview' | 'syllabus' | 'papers' | 'simulator' | 'revision'

export function CoursesPage() {
  const queryClient = useQueryClient()
  const search: any = useSearch({ strict: false })
  const navigate = useNavigate()
  const { activeCourseId, setActiveCourseId } = useActiveCourse()

  const [createOpen, setCreateOpen] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [semester, setSemester] = useState('Semester 3')
  const [academicYear, setAcademicYear] = useState('2025-2026')
  const [description, setDescription] = useState('')

  // Selected course from query or local state
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(() => {
    if (search?.courseId) return Number(search.courseId)
    return activeCourseId || null
  })

  const [activeTab, setActiveTab] = useState<TabType>(() => {
    if (search?.tab && ['overview', 'syllabus', 'papers', 'simulator', 'revision'].includes(search.tab)) {
      return search.tab as TabType
    }
    return 'overview'
  })

  // Synchronize when search params change
  useEffect(() => {
    if (search?.courseId) {
      setSelectedCourseId(Number(search.courseId))
    }
    if (search?.tab && ['overview', 'syllabus', 'papers', 'simulator', 'revision'].includes(search.tab)) {
      setActiveTab(search.tab as TabType)
    }
  }, [search?.courseId, search?.tab])

  const { data: courses = [], isLoading } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  // Fallback to active course or first course if courses load and none selected yet
  useEffect(() => {
    if (!selectedCourseId && courses.length > 0) {
      if (activeCourseId && courses.some((c: any) => c.id === activeCourseId)) {
        setSelectedCourseId(activeCourseId)
      }
    }
  }, [courses, activeCourseId, selectedCourseId])

  const selectedCourse = courses.find((c: any) => c.id === selectedCourseId) || null

  const createMutation = useMutation({
    mutationFn: () =>
      api.createCourse({
        code,
        name,
        semester,
        academic_year: academicYear,
        description,
      }),
    onSuccess: (newCourse: any) => {
      queryClient.invalidateQueries({ queryKey: ['courses'] })
      setCreateOpen(false)
      setCode('')
      setName('')
      setDescription('')
      toast.success('Course workspace created successfully!')
      if (newCourse?.id) {
        setSelectedCourseId(newCourse.id)
        setActiveCourseId(newCourse.id)
      }
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to create course')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteCourse(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['courses'] })
      if (selectedCourseId === deletedId) {
        setSelectedCourseId(null)
      }
      if (activeCourseId === deletedId) {
        setActiveCourseId(null)
      }
      toast.success('Course deleted')
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to delete course')
    },
  })

  const handleSelectCourse = (courseId: number | null) => {
    setSelectedCourseId(courseId)
    setActiveTab('overview')
    if (courseId) {
      navigate({
        to: '/courses',
        search: { courseId, tab: 'overview' } as any,
      })
    } else {
      navigate({
        to: '/courses',
        search: {} as any,
      })
    }
  }

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab)
    if (selectedCourseId) {
      navigate({
        to: '/courses',
        search: { courseId: selectedCourseId, tab } as any,
      })
    }
  }

  const isCurrentCourseActive = selectedCourse && activeCourseId === selectedCourse.id

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Workspace Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-medium">
            <button
              onClick={() => handleSelectCourse(null)}
              className="hover:text-foreground transition-colors flex items-center gap-1"
            >
              <BookOpen className="h-3.5 w-3.5 text-primary" />
              Courses
            </button>
            {selectedCourse && (
              <>
                <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
                <span className="text-foreground font-semibold">{selectedCourse.code}</span>
              </>
            )}
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            {selectedCourse ? (
              <>
                <span>{selectedCourse.name}</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                  {selectedCourse.code}
                </span>
              </>
            ) : (
              <>
                <BookOpen className="h-7 w-7 text-primary" />
                Course Workspaces & Syllabus
              </>
            )}
          </h1>
          <p className="text-sm text-muted-foreground">
            {selectedCourse
              ? `${selectedCourse.semester} • ${selectedCourse.academic_year} — Integrated Syllabus, Past Papers & Exam Simulator`
              : 'Deep course workspaces with syllabus mastery, past paper analytics, and adaptive exam simulation.'}
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {selectedCourse && (
            <>
              {isCurrentCourseActive ? (
                <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20 text-xs font-semibold">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Active Course
                </div>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setActiveCourseId(selectedCourse.id)
                    toast.success(`${selectedCourse.code} set as your active course`)
                  }}
                  className="text-xs"
                >
                  <Sparkles className="h-3.5 w-3.5 mr-1.5 text-teal-400" />
                  Set as Active
                </Button>
              )}

              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleSelectCourse(null)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                <LayoutGrid className="h-3.5 w-3.5 mr-1.5" />
                All Courses ({courses.length})
              </Button>
            </>
          )}

          <Button onClick={() => setCreateOpen(true)} size="sm" className="flex items-center gap-1.5 shadow-sm text-xs">
            <Plus className="h-3.5 w-3.5" />
            New Course
          </Button>
        </div>
      </div>

      {/* View 1: When a specific course is selected -> Show Workspace with Tabs */}
      {selectedCourse ? (
        <div className="space-y-6">
          {/* Workspace Tab Bar */}
          <div className="flex items-center gap-2 border-b border-border overflow-x-auto pb-px">
            <button
              onClick={() => handleTabChange('overview')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 whitespace-nowrap ${
                activeTab === 'overview'
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30'
              }`}
            >
              <BookOpen className="h-4 w-4" />
              Workspace Overview
            </button>
            <button
              onClick={() => handleTabChange('syllabus')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 whitespace-nowrap ${
                activeTab === 'syllabus'
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30'
              }`}
            >
              <Layers className="h-4 w-4 text-primary" />
              Syllabus Map
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-muted text-[10px] text-muted-foreground">
                {selectedCourse.unit_count || 0}u
              </span>
            </button>
            <button
              onClick={() => handleTabChange('papers')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 whitespace-nowrap ${
                activeTab === 'papers'
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30'
              }`}
            >
              <FileText className="h-4 w-4 text-amber-500" />
              Past Paper Analytics
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-muted text-[10px] text-muted-foreground">
                {selectedCourse.paper_count || 0}p
              </span>
            </button>
            <button
              onClick={() => handleTabChange('simulator')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 whitespace-nowrap ${
                activeTab === 'simulator'
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30'
              }`}
            >
              <Award className="h-4 w-4 text-emerald-500" />
              Exam Simulator
            </button>
            <button
              onClick={() => handleTabChange('revision')}
              className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 whitespace-nowrap ${
                activeTab === 'revision'
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30'
              }`}
            >
              <RotateCcw className="h-4 w-4 text-purple-400" />
              Adaptive Revision
            </button>
          </div>

          {/* Tab 1: Overview */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Quick Summary Card */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-card border border-border rounded-xl p-4">
                  <div className="text-xs text-muted-foreground font-medium">Curriculum Units</div>
                  <div className="text-2xl font-bold text-foreground mt-1">{selectedCourse.unit_count || 0}</div>
                  <div className="text-[11px] text-muted-foreground mt-1">Configured in syllabus</div>
                </div>
                <div className="bg-card border border-border rounded-xl p-4">
                  <div className="text-xs text-muted-foreground font-medium">Learning Topics</div>
                  <div className="text-2xl font-bold text-foreground mt-1">{selectedCourse.topic_count || 0}</div>
                  <div className="text-[11px] text-muted-foreground mt-1">Across all units</div>
                </div>
                <div className="bg-card border border-border rounded-xl p-4">
                  <div className="text-xs text-muted-foreground font-medium">Past Exam Papers</div>
                  <div className="text-2xl font-bold text-foreground mt-1">{selectedCourse.paper_count || 0}</div>
                  <div className="text-[11px] text-muted-foreground mt-1">Ingested for analytics</div>
                </div>
                <div className="bg-card border border-border rounded-xl p-4 flex flex-col justify-between">
                  <div>
                    <div className="text-xs text-muted-foreground font-medium">Academic Term</div>
                    <div className="text-sm font-semibold text-foreground mt-1">{selectedCourse.semester}</div>
                  </div>
                  <div className="text-[11px] text-muted-foreground font-mono">{selectedCourse.academic_year}</div>
                </div>
              </div>

              {/* Course Actions / Launchers */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div
                  onClick={() => handleTabChange('syllabus')}
                  className="group cursor-pointer rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                        <Layers className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                          Syllabus & Topic Breakdown
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Define units, organize topics, and link lecture notes and PDFs.
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>

                <div
                  onClick={() => handleTabChange('papers')}
                  className="group cursor-pointer rounded-xl border border-border bg-card p-5 hover:border-amber-500/50 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-500">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-foreground group-hover:text-amber-400 transition-colors">
                          Past Question Paper Intelligence
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Analyze recurring patterns, marks distribution, and frequent questions.
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-amber-400 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>

                <div
                  onClick={() => handleTabChange('simulator')}
                  className="group cursor-pointer rounded-xl border border-border bg-card p-5 hover:border-emerald-500/50 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-500">
                        <Award className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-foreground group-hover:text-emerald-400 transition-colors">
                          Autonomous Exam Simulator
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Generate realistic university papers with strict time limits and rubric grading.
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-emerald-400 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>

                <div
                  onClick={() => handleTabChange('revision')}
                  className="group cursor-pointer rounded-xl border border-border bg-card p-5 hover:border-purple-500/50 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400">
                        <RotateCcw className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-foreground group-hover:text-purple-400 transition-colors">
                          Adaptive Revision & Knowledge Gaps
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Target weak units with priority intervals and targeted recall questions.
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-purple-400 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Syllabus Map Embedded */}
          {activeTab === 'syllabus' && (
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <SyllabusMapPage courseId={selectedCourse.id} />
            </div>
          )}

          {/* Tab 3: Past Papers Embedded */}
          {activeTab === 'papers' && (
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <PaperAnalyticsPage courseId={selectedCourse.id} />
            </div>
          )}

          {/* Tab 4: Exam Simulator Embedded */}
          {activeTab === 'simulator' && (
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <ExamSimulatorPage courseId={selectedCourse.id} />
            </div>
          )}

          {/* Tab 5: Adaptive Revision Embedded */}
          {activeTab === 'revision' && (
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <AdaptiveRevisionPage courseId={selectedCourse.id} />
            </div>
          )}
        </div>
      ) : (
        /* View 2: When no specific course is selected -> Show All Courses Grid */
        <div className="space-y-6">
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-56 rounded-xl border border-border bg-card animate-pulse" />
              ))}
            </div>
          ) : courses.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-border rounded-xl bg-card/50">
              <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4" />
              <h3 className="text-lg font-medium text-foreground">No course workspaces yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto mt-1 mb-6">
                Create your first university course workspace to start mapping the syllabus and analyzing previous exam papers.
              </p>
              <Button onClick={() => setCreateOpen(true)}>Create Course Workspace</Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {courses.map((c: any) => {
                const isActive = activeCourseId === c.id
                return (
                  <div
                    key={c.id}
                    onClick={() => handleSelectCourse(c.id)}
                    className={`group relative flex flex-col justify-between rounded-xl border bg-card p-6 shadow-sm cursor-pointer transition-all duration-200 ${
                      isActive
                        ? 'border-primary ring-1 ring-primary/30 bg-primary/[0.02]'
                        : 'border-border hover:border-primary/50 hover:shadow-md'
                    }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Badge tone="accent" className="font-mono text-xs uppercase font-semibold">
                            {c.code}
                          </Badge>
                          {isActive && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
                              <CheckCircle2 className="h-3 w-3" /> Active
                            </span>
                          )}
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (confirm(`Delete course ${c.name}?`)) deleteMutation.mutate(c.id)
                          }}
                          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity p-1"
                          title="Delete course"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>

                      <h3 className="text-lg font-semibold text-foreground mt-3 line-clamp-1 group-hover:text-primary transition-colors">
                        {c.name}
                      </h3>
                      <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                        <span>{c.semester}</span>
                        <span>•</span>
                        <span>{c.academic_year}</span>
                      </p>
                      {c.description && (
                        <p className="text-sm text-muted-foreground mt-2.5 line-clamp-2">{c.description}</p>
                      )}

                      {/* Metrics */}
                      <div className="grid grid-cols-3 gap-2 mt-5 pt-4 border-t border-border/60 text-center">
                        <div className="bg-muted/40 rounded-lg p-2">
                          <div className="text-base font-bold text-foreground">{c.unit_count || 0}</div>
                          <div className="text-[11px] text-muted-foreground">Units</div>
                        </div>
                        <div className="bg-muted/40 rounded-lg p-2">
                          <div className="text-base font-bold text-foreground">{c.topic_count || 0}</div>
                          <div className="text-[11px] text-muted-foreground">Topics</div>
                        </div>
                        <div className="bg-muted/40 rounded-lg p-2">
                          <div className="text-base font-bold text-foreground">{c.paper_count || 0}</div>
                          <div className="text-[11px] text-muted-foreground">Past Papers</div>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 pt-4 border-t border-border/60 flex items-center justify-between text-xs font-semibold text-primary">
                      <span>Open Course Workspace</span>
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Modal: Create Course Workspace */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Course Workspace">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (code && name) createMutation.mutate()
          }}
          className="space-y-4 pt-2"
        >
          <div>
            <label className="text-xs font-medium text-foreground">Course Code</label>
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. CS301, AI-402, IT-305"
              required
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-foreground">Course Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Artificial Intelligence and Data Science"
              required
              className="mt-1"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-foreground">Semester</label>
              <Input
                value={semester}
                onChange={(e) => setSemester(e.target.value)}
                placeholder="Semester 3"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground">Academic Year</label>
              <Input
                value={academicYear}
                onChange={(e) => setAcademicYear(e.target.value)}
                placeholder="2025-2026"
                className="mt-1"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-foreground">Description (Optional)</label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Overview of syllabus, university syllabus reference, etc."
              className="mt-1"
            />
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!code || !name || createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Course'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
