import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { BookOpen, Brain, Compass, MessageSquare, ListChecks, CalendarCheck, Headphones, Mic, Settings, Search, Menu, LogOut, ArrowRight } from 'lucide-react'
import { api } from '../../lib/api'
import { queryClient } from '../../lib/queryClient'
import { jobSocket } from '../../lib/ws'
import { useUi } from '../../lib/store'
import type { User } from '../../lib/types'
import { Button, Dialog, DialogContent, DialogTitle, DialogDescription, Input } from '../ui'
import { CommandPalette } from '../CommandPalette'
import { JobTray } from './JobTray'

const sections = [
  {
    title: 'LEARN',
    links: [
      { to: '/', label: 'Workspace', Icon: Compass },
      { to: '/library', label: 'Study library', Icon: BookOpen },
      { to: '/chat', label: 'Source tutor', Icon: MessageSquare },
    ],
  },
  {
    title: 'PRACTISE',
    links: [
      { to: '/quiz', label: 'Quiz practice', Icon: ListChecks },
      { to: '/review', label: 'Flashcards', Icon: Brain },
      { to: '/knowledge-gap', label: 'Learning evidence', Icon: Compass },
      { to: '/revision', label: 'Revision plan', Icon: CalendarCheck },
    ],
  },
  {
    title: 'CAPTURE',
    links: [
      { to: '/record', label: 'Record a lecture', Icon: Mic },
      { to: '/podcasts', label: 'Audio study', Icon: Headphones },
    ],
  },
]

export function StudyShell() {
  const pathname = useRouterState({ select: s => s.location.pathname })
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [drawer, setDrawer] = useState(false)
  const [open, setOpen] = useState(false)
  const [register, setRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [online, setOnline] = useState(navigator.onLine)
  const setPalette = useUi(s => s.setPaletteOpen)

  const logout = () => {
    localStorage.removeItem('eduverse_token')
    localStorage.removeItem('eduverse_user')
    queryClient.clear()
    setUser(null)
  }

  useEffect(() => {
    const raw = localStorage.getItem('eduverse_user')
    const token = localStorage.getItem('eduverse_token')
    if (raw && token) {
      try {
        setUser(JSON.parse(raw))
      } catch {
        logout()
      }
    }
    setChecking(false)
  }, [])

  useEffect(() => {
    if (!user) return
    jobSocket.connect()
    return () => jobSocket.disconnect()
  }, [user])

  useEffect(() => {
    const changed = () => setOnline(navigator.onLine)
    const expired = () => { logout(); setError('Your session expired. Sign in again.'); setOpen(true) }
    const keys = (e: KeyboardEvent) => { if (user && (e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); setPalette(true) } }
    window.addEventListener('online', changed); window.addEventListener('offline', changed)
    window.addEventListener('eduverse:unauthorized', expired); window.addEventListener('keydown', keys)
    return () => { window.removeEventListener('online', changed); window.removeEventListener('offline', changed); window.removeEventListener('eduverse:unauthorized', expired); window.removeEventListener('keydown', keys) }
  }, [user])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const result = register ? await api.register({ email, username, password }) : await api.login({ username: email, password })
      queryClient.clear(); localStorage.setItem('eduverse_token', result.token)
      localStorage.setItem('eduverse_user', JSON.stringify(result.user)); setUser(result.user); setOpen(false)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not sign in. Try again.') }
    finally { setBusy(false) }
  }

  const allLinks = sections.flatMap(s => s.links)
  const matched = allLinks.find(l => l.to === pathname)
  const title = matched ? matched.label : (pathname.startsWith('/library/') ? 'Source workspace' : 'Settings')

  return <div className="study-shell">
    <a className="skip-link" href="#study-content">Skip to content</a>
    {drawer && <button className="drawer-shade" aria-label="Close navigation" onClick={() => setDrawer(false)} />}
    <aside className={`study-nav ${drawer ? 'is-open' : ''}`}>
      <Link to="/" className="study-brand"><span className="brand-symbol"><Compass size={22} /></span><span>eduverse<span className="brand-caption">A SPACE TO UNDERSTAND</span></span></Link>
      <button className="nav-search" onClick={() => setPalette(true)} disabled={!user}><Search size={16} /> Find in your library <kbd>⌘ K</kbd></button>
      <nav aria-label="Main navigation">
        {sections.map(section => (
          <div className="nav-section" key={section.title}>
            <p>{section.title}</p>
            {section.links.map(({ to, label, Icon }) => (
              <Link key={to} to={to} aria-current={pathname === to ? 'page' : undefined} className={`nav-item ${pathname === to ? 'active' : ''}`}>
                <Icon size={17} /><span>{label}</span>
              </Link>
            ))}
          </div>
        ))}
      </nav>
      <div className="nav-bottom">
        <Link to="/settings" className="nav-item"><Settings size={17} /> Settings</Link>
        {user && <JobTray />}
        <div className="account-row">
          <span className="account-initial">{user?.username[0]?.toUpperCase() || 'E'}</span>
          <div>
            <strong>{user?.full_name || user?.username || 'Your learning space'}</strong>
            <small>{user ? 'Personal workspace' : 'Sign in to begin'}</small>
          </div>
          {user && <button onClick={logout} aria-label="Sign out"><LogOut size={16} /></button>}
        </div>
      </div>
    </aside>
    <div className="study-body">
      <header className="study-topbar">
        <button className="mobile-menu" aria-label="Open navigation" onClick={() => setDrawer(true)}><Menu size={22} /></button>
        <div><span className="topbar-label">EDUVERSE /</span> {title}</div>
        <span className="session-label">{user ? 'PRIVATE WORKSPACE' : 'WELCOME'}</span>
      </header>
      {!online && <div role="status" className="offline-notice">You’re offline. Saved work remains available when the connection returns.</div>}
      <main id="study-content" className="study-main" tabIndex={-1}>
        {checking ? <div className="study-welcome" role="status">Opening your workspace…</div> : user ? <Outlet /> : <section className="study-welcome"><span className="eyebrow">YOUR MATERIAL. YOUR UNDERSTANDING.</span><h1>Make room for<br /><em>the next idea.</em></h1><p>Bring your engineering notes into one focused space. Explore concepts, question the source, and practise what you’ve learned.</p><Button variant="primary" size="lg" onClick={() => setOpen(true)}>Open your workspace <ArrowRight size={17} /></Button><small>PDF library · Source tutor · Practice · Learning evidence</small></section>}
      </main>
    </div>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="auth-dialog">
        <DialogTitle>{register ? 'Create your workspace' : 'Open your workspace'}</DialogTitle>
        <DialogDescription>{register ? 'Start a private repository for your notes, sources, and study progress.' : 'Enter your credentials to return to your materials and practice schedule.'}</DialogDescription>
        <form onSubmit={submit} className="auth-form">
          {register && <div className="auth-field"><label htmlFor="username">Username</label><Input id="username" value={username} onChange={e => setUsername(e.target.value)} required /></div>}
          <div className="auth-field"><label htmlFor="email">Email</label><Input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} required /></div>
          <div className="auth-field"><label htmlFor="password">Password</label><Input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} required /></div>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <Button type="submit" variant="primary" size="lg" disabled={busy}>{busy ? 'Processing…' : register ? 'Create account' : 'Sign in'}</Button>
        </form>
        <p className="auth-toggle">
          {register ? 'Already have a space?' : 'First time here?'}{' '}
          <button type="button" onClick={() => { setRegister(!register); setError('') }}>
            {register ? 'Sign in' : 'Create an account'}
          </button>
        </p>
      </DialogContent>
    </Dialog>
    <CommandPalette />
  </div>
}
