import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Sparkles, BookOpen, Brain, LayoutDashboard, Menu, MessageSquare,
  Search, Settings as SettingsIcon, ListChecks, CalendarCheck,
  LogOut, Layers, TrendingUp, Award, BarChart2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api } from '../../lib/api'
import { useUi, useServerHealth } from '../../lib/store'
import { startHealthMonitoring } from '../../lib/serverHealth'
import { jobSocket } from '../../lib/ws'
import { cn, modKey } from '../../lib/utils'
import type { User } from '../../lib/types'
import { Badge, Button, Kbd, Tooltip } from '../ui'
import { CommandPalette } from '../CommandPalette'
import { JobTray } from './JobTray'
import { AuthScreen } from '../auth/AuthScreen'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/courses', label: 'My Courses', icon: BookOpen },
  { to: '/syllabus', label: 'Syllabus Map', icon: Layers },
  { to: '/papers', label: 'Paper Analytics', icon: TrendingUp },
  { to: '/simulator', label: 'Exam Simulator', icon: Award },
  { to: '/performance', label: 'My Performance', icon: BarChart2 },
  { to: '/adaptive', label: 'Adaptive Revision', icon: CalendarCheck },
  { to: '/chat', label: 'Study Assistant', icon: MessageSquare },
  { to: '/library', label: 'Study Library', icon: Sparkles },
  { to: '/review', label: 'Flashcards', icon: Brain, badge: 'due' as const },
  { to: '/quiz', label: 'Practice Quiz', icon: ListChecks },
]

export function AppShell() {
  const { sidebarOpen, setSidebarOpen, setPaletteOpen } = useUi()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const queryClient = useQueryClient()

  const [currentUser, setCurrentUser] = useState<User | null>(() => {
    if (typeof localStorage === 'undefined') return null
    const cached = localStorage.getItem('eduverse_user')
    const token = localStorage.getItem('eduverse_token')
    if (cached && token) {
      try {
        return JSON.parse(cached)
      } catch {
        return null
      }
    }
    return null
  })

  // Continuous server and model health monitoring
  useEffect(() => {
    const stopMonitoring = startHealthMonitoring()
    return () => stopMonitoring()
  }, [])

  // Connect socket only when logged in
  useEffect(() => {
    if (!currentUser) return
    jobSocket.connect()
    return () => jobSocket.disconnect()
  }, [currentUser])

  // Global hotkeys
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPaletteOpen])

  // Listen to 401 unauthorized events to force sign-in
  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem('eduverse_token')
      localStorage.removeItem('eduverse_user')
      queryClient.clear()
      setCurrentUser(null)
      toast.error('Your session has expired. Please sign in again.')
    }
    window.addEventListener('eduverse:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('eduverse:unauthorized', handleUnauthorized)
  }, [queryClient])

  // Close the drawer after navigating on mobile
  useEffect(() => {
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }, [pathname, setSidebarOpen])

  const { data: counts } = useQuery({
    queryKey: ['card-counts'],
    queryFn: () => api.cardCounts(),
    enabled: !!currentUser,
    refetchInterval: 60_000,
  })
  const dueTotal = (counts?.due ?? 0) + (counts?.new ?? 0)

  const handleLogout = async () => {
    try {
      await api.logout()
    } catch {
      // Safe fallback on network error
    } finally {
      localStorage.removeItem('eduverse_token')
      localStorage.removeItem('eduverse_user')
      queryClient.clear()
      setCurrentUser(null)
      toast.success('Signed out successfully.')
    }
  }

  // If not logged in, render the premium split-layout AuthScreen
  if (!currentUser) {
    return (
      <AuthScreen
        onSuccess={(user) => {
          setCurrentUser(user)
          queryClient.invalidateQueries()
        }}
      />
    )
  }

  return (
    <div className="flex h-full overflow-hidden bg-[var(--bg)] text-[var(--text)]">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-[var(--border)]',
          'bg-[var(--bg-raised)] transition-transform lg:static lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-[var(--border)] px-4">
          <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--accent)] text-black shadow-sm shadow-[var(--accent)]/30">
              <Sparkles className="h-4.5 w-4.5" />
            </span>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight text-[var(--text)]">EduVerse AI</span>
              <span className="text-[10px] text-[var(--text-muted)] font-normal">ICEM • AI & DS Dept</span>
            </div>
          </Link>
          <Badge tone="accent" className="text-[10px] px-1.5 py-0.5">SPPU v1.0</Badge>
        </div>

        <div className="px-3 pb-2 pt-2.5">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] px-2.5 py-1.5 text-[13px] text-[var(--text-muted)] transition hover:border-[var(--accent)]/40 hover:text-[var(--text)]"
          >
            <Search className="h-3.5 w-3.5" />
            <span className="flex-1 text-left">Search library…</span>
            <Kbd>{modKey}K</Kbd>
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-1">
          {NAV.map((item) => {
            const active = item.exact ? pathname === item.to : pathname.startsWith(item.to)
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                    : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
                {item.badge === 'due' && dueTotal > 0 && (
                  <Badge tone="accent">{dueTotal > 999 ? '999+' : dueTotal}</Badge>
                )}
              </Link>
            )
          })}
        </nav>

        {/* User Account & Settings Footer */}
        <div className="border-t border-[var(--border)] p-3 space-y-2 bg-[var(--bg-sunken)]/30">
          <div className="flex items-center gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg-raised)] p-2">
            <div
              className="grid h-7 w-7 place-items-center rounded-md text-xs font-bold text-white shadow-xs shrink-0"
              style={{ backgroundColor: currentUser.avatar_color || '#7C3AED' }}
            >
              {currentUser.username.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-xs font-semibold text-[var(--text)]">
                {currentUser.full_name || currentUser.username}
              </p>
              <p className="truncate text-[10px] text-[var(--text-muted)]">
                {currentUser.email}
              </p>
            </div>
            <Tooltip label="Sign out">
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="h-7 w-7 text-[var(--text-muted)] hover:text-red-500 shrink-0"
              >
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          </div>

          <LlmIndicator />

          <JobTray />

          <Link
            to="/settings"
            className={cn(
              'flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
              pathname.startsWith('/settings')
                ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text)]',
            )}
          >
            <SettingsIcon className="h-3.5 w-3.5" />
            <span>Settings & AI Models</span>
          </Link>
        </div>
      </aside>

      {/* Main Body */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border)] px-3 lg:hidden bg-[var(--bg-raised)]">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <Menu className="h-4 w-4" />
          </Button>
          <span className="font-semibold text-sm">EduVerse AI</span>
          <div className="flex-1" />
          <Tooltip label="Search">
            <Button variant="ghost" size="icon" onClick={() => setPaletteOpen(true)}>
              <Search className="h-4 w-4" />
            </Button>
          </Tooltip>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      <CommandPalette />
      <ConnectionBanner />
    </div>
  )
}

function LlmIndicator() {
  const llmStatus = useServerHealth((state) => state.llmStatus)
  if (!llmStatus) return null
  const isOnline = llmStatus.status === 'connected'
  const isLoading = llmStatus.status === 'loading'

  return (
    <div
      title={llmStatus.message || undefined}
      className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] px-2.5 py-1.5 text-[11px]"
    >
      <div className="flex items-center gap-1.5 min-w-0">
        <span
          className={cn(
            'h-2 w-2 rounded-full shrink-0',
            isOnline
              ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50'
              : isLoading
              ? 'bg-amber-500 animate-pulse'
              : 'bg-zinc-400',
          )}
        />
        <span className="truncate font-medium text-[var(--text)]">
          {isOnline ? llmStatus.model || 'qwen3.5:4b' : isLoading ? 'Model loading…' : 'Ollama offline'}
        </span>
      </div>
      <span className="text-[10px] text-[var(--text-muted)] shrink-0 capitalize">
        {isOnline ? `${llmStatus.thinking || 'high'} reason` : 'offline'}
      </span>
    </div>
  )
}

function ConnectionBanner() {
  const serverConnected = useServerHealth((state) => state.serverConnected)
  const [visible, setVisible] = useDelayed(!serverConnected, 4000)
  if (!visible) return null
  return (
    <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-700 shadow-lg backdrop-blur dark:text-amber-300">
      Reconnecting to EduVerse server…
      <button className="ml-2 underline hover:text-amber-900 dark:hover:text-amber-100" onClick={() => setVisible(false)}>
        dismiss
      </button>
    </div>
  )
}

function useDelayed(value: boolean, delay: number): [boolean, (v: boolean) => void] {
  const [state, setState] = useState(false)
  useEffect(() => {
    if (!value) {
      setState(false)
      return
    }
    const handle = setTimeout(() => setState(true), delay)
    return () => clearTimeout(handle)
  }, [value, delay])
  return [state, setState]
}
