import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { BookOpen, Plus, Layers, FileText, Award, Trash2, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import { Button, Input, Modal, Badge } from '../components/ui'

export function CoursesPage() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [semester, setSemester] = useState('Semester 3')
  const [academicYear, setAcademicYear] = useState('2025-2026')
  const [description, setDescription] = useState('')

  const { data: courses = [], isLoading } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      api.createCourse({
        code,
        name,
        semester,
        academic_year: academicYear,
        description,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courses'] })
      setCreateOpen(false)
      setCode('')
      setName('')
      setDescription('')
      toast.success('Course workspace created successfully!')
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to create course')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteCourse(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courses'] })
      toast.success('Course deleted')
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to delete course')
    },
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <BookOpen className="h-7 w-7 text-primary" />
            My Courses & Exam Intelligence
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Structured course workspaces with syllabus mapping, previous exam papers, and adaptive revision.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="flex items-center gap-2 shadow-sm">
          <Plus className="h-4 w-4" />
          New Course Workspace
        </Button>
      </div>

      {/* Course Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-64 rounded-xl border border-border bg-card animate-pulse" />
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
          {courses.map((c: any) => (
            <div
              key={c.id}
              className="group relative flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-sm hover:border-primary/50 hover:shadow-md transition-all duration-200"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <Badge tone="accent" className="font-mono text-xs uppercase font-semibold">
                    {c.code}
                  </Badge>
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
                <h3 className="text-lg font-semibold text-foreground mt-3 line-clamp-1">{c.name}</h3>
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
                    <div className="text-base font-bold text-foreground">{c.unit_count}</div>
                    <div className="text-[11px] text-muted-foreground">Units</div>
                  </div>
                  <div className="bg-muted/40 rounded-lg p-2">
                    <div className="text-base font-bold text-foreground">{c.topic_count}</div>
                    <div className="text-[11px] text-muted-foreground">Topics</div>
                  </div>
                  <div className="bg-muted/40 rounded-lg p-2">
                    <div className="text-base font-bold text-foreground">{c.paper_count}</div>
                    <div className="text-[11px] text-muted-foreground">Past Papers</div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-6 pt-4 border-t border-border/60 flex flex-col gap-2">
                <Link
                  to="/syllabus"
                  search={{ courseId: c.id }}
                  className="flex items-center justify-between text-xs font-medium text-foreground hover:text-primary p-2 rounded-md hover:bg-muted/60 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-primary" />
                    Syllabus & Topic Map
                  </span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
                <Link
                  to="/papers"
                  search={{ courseId: c.id }}
                  className="flex items-center justify-between text-xs font-medium text-foreground hover:text-primary p-2 rounded-md hover:bg-muted/60 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-amber-500" />
                    Past Paper Intelligence
                  </span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
                <Link
                  to="/simulator"
                  search={{ courseId: c.id }}
                  className="flex items-center justify-between text-xs font-medium text-foreground hover:text-primary p-2 rounded-md hover:bg-muted/60 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <Award className="h-4 w-4 text-emerald-500" />
                    Exam Simulator
                  </span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          ))}
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
              placeholder="e.g. Artificial Intelligence & Data Science"
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
