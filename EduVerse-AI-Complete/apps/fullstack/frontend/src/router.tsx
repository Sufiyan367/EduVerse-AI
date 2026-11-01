import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'
import { AppShell } from './components/layout/AppShell'
import { DashboardPage } from './routes/Dashboard'
import { CoursesPage } from './routes/Courses'
import { SyllabusMapPage } from './routes/SyllabusMap'
import { PaperAnalyticsPage } from './routes/PaperAnalytics'
import { ExamSimulatorPage } from './routes/ExamSimulator'
import { PerformancePage } from './routes/Performance'
import { AdaptiveRevisionPage } from './routes/AdaptiveRevision'
import { LibraryPage } from './routes/Library'
import { SourcePage } from './routes/Source'
import { ReviewPage } from './routes/Review'
import { QuizPage } from './routes/Quiz'
import { ChatPage } from './routes/Chat'
import { KnowledgeGapPage } from './routes/KnowledgeGap'
import { RevisionPage } from './routes/Revision'
import { PodcastsPage } from './routes/Podcasts'
import { RecordPage } from './routes/Record'
import { SettingsPage } from './routes/Settings'
import { AutomationCenterPage } from './routes/AutomationCenter'
import { NotFound } from './routes/NotFound'

const rootRoute = createRootRoute({
  component: AppShell,
  notFoundComponent: NotFound,
})

const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: DashboardPage })

// Course Workspace & Academic Domain Routes
const coursesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/courses', component: CoursesPage })

interface CourseContextSearch {
  courseId?: number
}

const syllabusRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/syllabus',
  component: SyllabusMapPage,
  validateSearch: (search: Record<string, unknown>): CourseContextSearch => ({
    courseId: search.courseId ? Number(search.courseId) : undefined,
  }),
})

const papersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/papers',
  component: PaperAnalyticsPage,
  validateSearch: (search: Record<string, unknown>): CourseContextSearch => ({
    courseId: search.courseId ? Number(search.courseId) : undefined,
  }),
})

const simulatorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/simulator',
  component: ExamSimulatorPage,
  validateSearch: (search: Record<string, unknown>): CourseContextSearch => ({
    courseId: search.courseId ? Number(search.courseId) : undefined,
  }),
})

const adaptiveRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/adaptive',
  component: AdaptiveRevisionPage,
  validateSearch: (search: Record<string, unknown>): CourseContextSearch => ({
    courseId: search.courseId ? Number(search.courseId) : undefined,
  }),
})

const performanceRoute = createRoute({ getParentRoute: () => rootRoute, path: '/performance', component: PerformancePage })

// Existing Study & Tool Routes
interface LibrarySearch {
  folder?: number
  tag?: string
}
const libraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/library',
  component: LibraryPage,
  validateSearch: (search: Record<string, unknown>): LibrarySearch => ({
    folder: search.folder ? Number(search.folder) : undefined,
    tag: typeof search.tag === 'string' ? search.tag : undefined,
  }),
})

interface SourceSearch {
  tab?: string
  seg?: number
  print?: boolean
}
const sourceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/library/$sourceId',
  component: SourcePage,
  validateSearch: (search: Record<string, unknown>): SourceSearch => ({
    tab: typeof search.tab === 'string' ? search.tab : undefined,
    seg: search.seg ? Number(search.seg) : undefined,
    print: search.print === true || search.print === 'true' ? true : undefined,
  }),
})

interface ReviewSearch {
  folder?: number
  source?: number
}
const reviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/review',
  component: ReviewPage,
  validateSearch: (search: Record<string, unknown>): ReviewSearch => ({
    folder: search.folder ? Number(search.folder) : undefined,
    source: search.source ? Number(search.source) : undefined,
  }),
})

interface QuizSearch {
  source?: number
  folder?: number
  mode?: string
}
const quizRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/quiz',
  component: QuizPage,
  validateSearch: (search: Record<string, unknown>): QuizSearch => ({
    source: search.source ? Number(search.source) : undefined,
    folder: search.folder ? Number(search.folder) : undefined,
    mode: typeof search.mode === 'string' ? search.mode : undefined,
  }),
})

interface ChatSearch {
  id?: number
  source?: number
}
const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/chat',
  component: ChatPage,
  validateSearch: (search: Record<string, unknown>): ChatSearch => ({
    id: search.id ? Number(search.id) : undefined,
    source: search.source ? Number(search.source) : undefined,
  }),
})

const knowledgeGapRoute = createRoute({ getParentRoute: () => rootRoute, path: '/knowledge-gap', component: KnowledgeGapPage })
const revisionRoute = createRoute({ getParentRoute: () => rootRoute, path: '/revision', component: RevisionPage })
const podcastsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/podcasts', component: PodcastsPage })
const recordRoute = createRoute({ getParentRoute: () => rootRoute, path: '/record', component: RecordPage })
const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/settings', component: SettingsPage })
const automationRoute = createRoute({ getParentRoute: () => rootRoute, path: '/automation', component: AutomationCenterPage })

const routeTree = rootRoute.addChildren([
  indexRoute,
  coursesRoute,
  syllabusRoute,
  papersRoute,
  simulatorRoute,
  adaptiveRoute,
  performanceRoute,
  libraryRoute,
  sourceRoute,
  reviewRoute,
  quizRoute,
  chatRoute,
  knowledgeGapRoute,
  revisionRoute,
  podcastsRoute,
  recordRoute,
  settingsRoute,
  automationRoute,
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
