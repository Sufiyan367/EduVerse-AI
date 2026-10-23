import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  Sparkles,
  BookOpen, Brain, LayoutDashboard, Menu, Mic, MessageSquare, Headphones,
  Search, Settings as SettingsIcon, ListChecks, AlertTriangle, CalendarCheck,
  LogIn,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { useJobs, useUi } from '../../lib/store'
import { jobSocket } from '../../lib/ws'
import { cn, modKey } from '../../lib/utils'
import { Badge, Button, Input, Kbd, Tooltip } from '../ui'
import { CommandPalette } from '../CommandPalette'
import { JobTray } from './JobTray'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/library', label: 'Library', icon: BookOpen },
  { to: '/review', label: 'Review', icon: Brain, badge: 'due' as const },
  { to: '/quiz', label: 'Quiz', icon: ListChecks },
  { to: '/chat', label: 'AI Tutor', icon: MessageSquare },
  { to: '/knowledge-gap', label: 'Knowledge Gaps', icon: AlertTriangle },
  { to: '/revision', label: 'Revision Planner', icon: CalendarCheck },
  { to: '/podcasts', label: 'Podcasts', icon: Headphones },
  { to: '/record', label: 'Record', icon: Mic },
]

export function AppShell() {
  const { sidebarOpen, setSidebarOpen, setPaletteOpen } = useUi()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('student@eduverse.ai')
  const [password, setPassword] = useState('demo123')
  const [username, setUsername] = useState('demo_student')
  const [fullName, setFullName] = useState('EduVerse Scholar')
  const [authError, setAuthError] = useState<string | null>(null)
  const [currentUser, setCurrentUser] = useState<{ username: string; email: string; full_name: string; avatar_color: string } | null>(() => {
    const cached = localStorage.getItem('eduverse_user')
    return cached ? JSON.parse(cached) : { username: 'demo_student', email: 'student@eduverse.ai', full_name: 'EduVerse Scholar', avatar_color: '#7C3AED' }
  })

  // One socket for the whole app; see lib/ws.ts for why it is not a hook.
  useEffect(() => {
    jobSocket.connect()
    return () => jobSocket.disconnect()
  }, [])

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

  // Close the drawer after navigating on mobile, or it covers the page you just opened.
  useEffect(() => {
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }, [pathname, setSidebarOpen])

  const { data: counts } = useQuery({
    queryKey: ['card-counts'],
    queryFn: () => api.cardCounts(),
    refetchInterval: 60_000,
  })
  const dueTotal = (counts?.due ?? 0) + (counts?.new ?? 0)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    try {
      const res = await api.login({ username: email, password })
      localStorage.setItem('eduverse_token', res.token)
      localStorage.setItem('eduverse_user', JSON.stringify(res.user))
      setCurrentUser(res.user)
      setAuthModalOpen(false)
    } catch (err: any) {
      setAuthError(err.message || 'Login failed')
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    try {
      const res = await api.register({ email, username, password, full_name: fullName })
      localStorage.setItem('eduverse_token', res.token)
      localStorage.setItem('eduverse_user', JSON.stringify(res.user))
      setCurrentUser(res.user)
      setAuthModalOpen(false)
    } catch (err: any) {
      setAuthError(err.message || 'Registration failed')
    }
  }

  const handleQuickDemo = () => {
    setEmail('student@eduverse.ai')
    setPassword('demo123')
  }

  return (
    <div className="flex h-full overflow-hidden">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-[var(--border)]',
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
          <Badge tone="accent" className="text-[10px] px-1.5 py-0.5">v1.0 Demo</Badge>
        </div>

        <div className="px-3 pb-2 pt-2">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] px-2.5 py-1.5 text-[13px] text-[var(--text-muted)] transition hover:border-[var(--accent)]/40"
          >
            <Search className="h-3.5 w-3.5" />
            <span className="flex-1 text-left">Search…</span>
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
                    ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
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

        {/* User Account & Settings */}
        <div className="border-t border-[var(--border)] p-3 space-y-2">
          <button
            type="button"
            onClick={() => setAuthModalOpen(true)}
            className="flex w-full items-center gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] p-2 text-left transition hover:border-[var(--accent)]/40"
          >
            <div
              className="grid h-7 w-7 place-items-center rounded-md text-xs font-bold text-white shadow-xs"
              style={{ backgroundColor: currentUser?.avatar_color || '#7C3AED' }}
            >
              {currentUser?.username?.charAt(0).toUpperCase() || 'S'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-xs font-semibold text-[var(--text)]">
                {currentUser?.full_name || 'EduVerse Student'}
              </p>
              <p className="truncate text-[10px] text-[var(--text-muted)]">
                {currentUser?.email || 'student@eduverse.ai'}
              </p>
            </div>
            <LogIn className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
          </button>

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
            Settings & AI Provider
          </Link>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border)] px-3 lg:hidden">
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

      {/* Auth Modal */}
      {authModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-md bg-[var(--accent)] text-black text-xs font-bold">E</span>
                <h3 className="text-base font-bold text-[var(--text)]">
                  {authMode === 'login' ? 'Student Sign In' : 'Register New Account'}
                </h3>
              </div>
              <button
                onClick={() => setAuthModalOpen(false)}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
              >
                ✕
              </button>
            </div>

            {authError && (
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-400">
                {authError}
              </div>
            )}

            <form onSubmit={authMode === 'login' ? handleLogin : handleRegister} className="space-y-3">
              {authMode === 'register' && (
                <>
                  <div>
                    <label className="text-xs text-[var(--text-muted)] block mb-1">Full Name</label>
                    <Input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-muted)] block mb-1">Username</label>
                    <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
                  </div>
                </>
              )}

              <div>
                <label className="text-xs text-[var(--text-muted)] block mb-1">
                  {authMode === 'login' ? 'Email or Username' : 'Email Address'}
                </label>
                <Input value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>

              <div>
                <label className="text-xs text-[var(--text-muted)] block mb-1">Password</label>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>

              {authMode === 'login' && (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-sunken)] p-2.5 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-[var(--text)]">Default Demo Student:</span>
                    <button
                      type="button"
                      onClick={handleQuickDemo}
                      className="text-[var(--accent)] hover:underline font-medium text-[11px]"
                    >
                      Fill Demo
                    </button>
                  </div>
                  <p className="text-[11px] text-[var(--text-muted)]">student@eduverse.ai / demo123</p>
                </div>
              )}

              <Button type="submit" variant="primary" className="w-full">
                {authMode === 'login' ? 'Sign In' : 'Create Account'}
              </Button>
            </form>

            <div className="flex items-center justify-between border-t border-[var(--border)] pt-3 text-xs text-[var(--text-muted)]">
              <span>{authMode === 'login' ? "Don't have an account?" : 'Already registered?'}</span>
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'login' ? 'register' : 'login')
                  setAuthError(null)
                }}
                className="text-[var(--accent)] hover:underline font-medium"
              >
                {authMode === 'login' ? 'Register' : 'Sign In'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ConnectionBanner() {
  const connected = useJobs((state) => state.connected)
  const [visible, setVisible] = useDelayed(!connected, 3000)
  if (!visible) return null
  return (
    <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-700 shadow-lg dark:text-amber-300">
      Reconnecting to EduVerse AI server…
      <button className="ml-2 underline" onClick={() => setVisible(false)}>
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
