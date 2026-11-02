import { useState, useEffect } from 'react'
import { useSearch, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  Brain, ListChecks, Award, CalendarCheck, AlertCircle,
} from 'lucide-react'
import { api } from '../lib/api'
import { useActiveCourse } from '../lib/store'
import { cn } from '../lib/utils'
import { Badge, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui'
import { ReviewPage } from './Review'
import { QuizPage } from './Quiz'
import { ExamSimulatorPage } from './ExamSimulator'
import { AdaptiveRevisionPage } from './AdaptiveRevision'
import { KnowledgeGapPage } from './KnowledgeGap'

export type PracticeTab = 'flashcards' | 'quiz' | 'simulator' | 'adaptive' | 'gaps'

interface PracticeSearch {
  tab?: PracticeTab
  courseId?: number
  source?: number
  folder?: number
  mode?: string
}

export function PracticePage() {
  const search = (useSearch({ strict: false }) as PracticeSearch) || {}
  const navigate = useNavigate()
  const { activeCourseId, setActiveCourseId } = useActiveCourse()

  const [currentTab, setCurrentTab] = useState<PracticeTab>(() => {
    if (search.tab && ['flashcards', 'quiz', 'simulator', 'adaptive', 'gaps'].includes(search.tab)) {
      return search.tab
    }
    return 'flashcards'
  })

  // Synchronize search.tab when URL changes
  useEffect(() => {
    if (search.tab && search.tab !== currentTab) {
      setCurrentTab(search.tab)
    }
  }, [search.tab])

  const { data: courses = [] } = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.listCourses(),
  })

  const { data: counts } = useQuery({
    queryKey: ['card-counts'],
    queryFn: () => api.cardCounts(),
    refetchInterval: 30_000,
  })
  const dueTotal = (counts?.due ?? 0) + (counts?.new ?? 0)

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.dashboardStats(),
  })

  const handleTabChange = (tab: PracticeTab) => {
    setCurrentTab(tab)
    navigate({ to: '/practice', search: { ...search, tab } })
  }


  return (
    <div className="flex h-full flex-col overflow-hidden bg-[var(--bg)]">
      {/* Top Practice Command Bar */}
      <header className="shrink-0 border-b border-[var(--border)] bg-[var(--bg-raised)] px-4 py-3 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-[var(--text)]">Practice & Recall Hub</h1>
              <Badge tone="accent" className="text-[11px] font-semibold">Active Learning</Badge>
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Consolidated active recall, grounded exam simulation, spaced repetition, and adaptive remediation.
            </p>
          </div>

          {/* Course Scope Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-muted)] font-medium hidden sm:inline">Scope:</span>
            <Select
              value={activeCourseId ? String(activeCourseId) : 'all'}
              onValueChange={(val) => setActiveCourseId(val === 'all' ? null : Number(val))}
            >
              <SelectTrigger className="w-56 text-xs h-8">
                <SelectValue placeholder="All Courses (Global)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Courses & Documents</SelectItem>
                {courses.map((c: any) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.code}: {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Practice Modes Tabs */}
        <div className="mt-3 flex overflow-x-auto border-t border-[var(--border)] pt-2 gap-1.5 scrollbar-none">
          <button
            type="button"
            onClick={() => handleTabChange('flashcards')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all shrink-0',
              currentTab === 'flashcards'
                ? 'bg-[var(--accent)] text-black font-semibold shadow-xs'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
            )}
          >
            <Brain className="h-3.5 w-3.5" />
            <span>Flashcards (FSRS-6)</span>
            {dueTotal > 0 && (
              <span className={cn(
                'ml-1 rounded-full px-1.5 py-0.2 text-[10px] font-bold',
                currentTab === 'flashcards' ? 'bg-black/20 text-black' : 'bg-[var(--accent-soft)] text-[var(--accent)]'
              )}>
                {dueTotal}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('quiz')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all shrink-0',
              currentTab === 'quiz'
                ? 'bg-[var(--accent)] text-black font-semibold shadow-xs'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
            )}
          >
            <ListChecks className="h-3.5 w-3.5" />
            <span>Practice Quiz</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('simulator')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all shrink-0',
              currentTab === 'simulator'
                ? 'bg-[var(--accent)] text-black font-semibold shadow-xs'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
            )}
          >
            <Award className="h-3.5 w-3.5" />
            <span>Exam Simulator</span>
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('adaptive')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all shrink-0',
              currentTab === 'adaptive'
                ? 'bg-[var(--accent)] text-black font-semibold shadow-xs'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
            )}
          >
            <CalendarCheck className="h-3.5 w-3.5" />
            <span>Adaptive Revision</span>
            {stats && stats.pending_revision_count > 0 && (
              <span className={cn(
                'ml-1 rounded-full px-1.5 py-0.2 text-[10px] font-bold',
                currentTab === 'adaptive' ? 'bg-black/20 text-black' : 'bg-amber-500/20 text-amber-400'
              )}>
                {stats.pending_revision_count}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => handleTabChange('gaps')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all shrink-0',
              currentTab === 'gaps'
                ? 'bg-[var(--accent)] text-black font-semibold shadow-xs'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
            )}
          >
            <AlertCircle className="h-3.5 w-3.5" />
            <span>Knowledge Gaps</span>
            {stats && stats.critical_gaps_count > 0 && (
              <span className={cn(
                'ml-1 rounded-full px-1.5 py-0.2 text-[10px] font-bold',
                currentTab === 'gaps' ? 'bg-black/20 text-black' : 'bg-rose-500/20 text-rose-400'
              )}>
                {stats.critical_gaps_count}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Main Tab Content View */}
      <main className="min-h-0 flex-1 overflow-y-auto">
        {currentTab === 'flashcards' && <ReviewPage />}
        {currentTab === 'quiz' && <QuizPage />}
        {currentTab === 'simulator' && <ExamSimulatorPage />}
        {currentTab === 'adaptive' && <AdaptiveRevisionPage />}
        {currentTab === 'gaps' && <KnowledgeGapPage />}
      </main>
    </div>
  )
}
