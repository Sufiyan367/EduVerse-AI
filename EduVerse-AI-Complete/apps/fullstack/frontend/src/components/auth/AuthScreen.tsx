import { useState } from 'react'
import {
  Brain, BookOpen, Sparkles, ShieldCheck, Eye, EyeOff, ArrowRight,
  GraduationCap, CheckCircle2, AlertCircle, Zap, Layers
} from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import type { User } from '../../lib/types'
import { Button, Input, Badge } from '../ui'

interface AuthScreenProps {
  onSuccess: (user: User, token: string) => void
}

export function AuthScreen({ onSuccess }: AuthScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      if (mode === 'login') {
        const res = await api.login({ username: email.trim(), password })
        localStorage.setItem('eduverse_token', res.token)
        localStorage.setItem('eduverse_user', JSON.stringify(res.user))
        onSuccess(res.user, res.token)
      } else {
        if (password.length < 8) {
          setError('Password must be at least 8 characters long.')
          setLoading(false)
          return
        }
        const res = await api.register({
          email: email.trim().toLowerCase(),
          username: username.trim(),
          password,
          full_name: fullName.trim() || undefined,
        })
        localStorage.setItem('eduverse_token', res.token)
        localStorage.setItem('eduverse_user', JSON.stringify(res.user))
        onSuccess(res.user, res.token)
      }
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : (err?.message || 'Authentication failed. Please check credentials.'))
    } finally {
      setLoading(false)
    }
  }

  const handleDemoLogin = async () => {
    setError(null)
    setLoading(true)
    setEmail('student@eduverse.ai')
    setPassword('demo123')
    try {
      const res = await api.login({ username: 'student@eduverse.ai', password: 'demo123' })
      localStorage.setItem('eduverse_token', res.token)
      localStorage.setItem('eduverse_user', JSON.stringify(res.user))
      onSuccess(res.user, res.token)
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Demo account login failed. Ensure backend seed is active.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-[var(--bg)] text-[var(--text)]">
      {/* Left Column: Brand Hero & Academic Context */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-[var(--bg-raised)] border-r border-[var(--border)] relative overflow-hidden">
        {/* Decorative subtle background elements */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 rounded-full bg-[var(--accent)]/5 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-96 h-96 rounded-full bg-blue-500/5 blur-3xl pointer-events-none" />

        {/* Top Header */}
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--accent)] text-black shadow-md shadow-[var(--accent)]/20">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight text-[var(--text)]">EduVerse AI</span>
                <Badge tone="accent" className="text-[10px] font-semibold tracking-wide">ENTERPRISE v1.0</Badge>
              </div>
              <p className="text-xs text-[var(--text-muted)] font-medium">
                Indira College of Engineering & Management (ICEM Pune)
              </p>
            </div>
          </div>
        </div>

        {/* Center Content */}
        <div className="relative z-10 max-w-lg space-y-8 my-auto py-10">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[var(--accent-soft)] text-[var(--accent)]">
              <GraduationCap className="h-3.5 w-3.5" /> SPPU AI & Data Science Curriculum
            </span>
            <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight leading-tight text-[var(--text)]">
              Transform Course Materials Into <span className="text-[var(--accent)]">Mastered Knowledge</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed">
              An intelligent, grounded study workspace inspired by Google NotebookLM. Ingest syllabi, lecture slides,
              and academic PDFs with guaranteed citation grounding, FSRS-6 spaced repetition, and real-time gap analysis.
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex items-start gap-3.5 p-3.5 rounded-xl border border-[var(--border)] bg-[var(--bg-sunken)]/60">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                <BookOpen className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-xs font-semibold text-[var(--text)]">Grounded Source Intelligence</h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  AI tutor responses are strictly scoped and cite exact page numbers and bracketed passage references.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-3.5 rounded-xl border border-[var(--border)] bg-[var(--bg-sunken)]/60">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                <Brain className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-xs font-semibold text-[var(--text)]">FSRS-6 Spaced Repetition</h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Scientific memory scheduling with 4-grade feedback that predicts forgetting curves for upcoming exams.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-3.5 rounded-xl border border-[var(--border)] bg-[var(--bg-sunken)]/60">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                <Layers className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-xs font-semibold text-[var(--text)]">Continuous Knowledge Gap Detection</h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Identifies misconceptions from quiz performance and automatically schedules remedial revision sessions.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Trust Footer */}
        <div className="relative z-10 flex items-center justify-between text-xs text-[var(--text-muted)] border-t border-[var(--border)] pt-6">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[var(--accent)]" />
            <span>Argon2id Encrypted & Tenant Isolated</span>
          </div>
          <span>SPPU BE Final Year Capstone</span>
        </div>
      </div>

      {/* Right Column: Authentication Form Card */}
      <div className="flex-1 flex flex-col justify-center items-center p-6 sm:p-12 lg:p-16">
        <div className="w-full max-w-md space-y-6">
          {/* Mobile Brand Header */}
          <div className="flex items-center gap-3 lg:hidden mb-6">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-[var(--accent)] text-black">
              <Sparkles className="h-4.5 w-4.5" />
            </div>
            <div>
              <span className="text-lg font-bold text-[var(--text)]">EduVerse AI</span>
              <p className="text-xs text-[var(--text-muted)]">ICEM Pune • AI & Data Science</p>
            </div>
          </div>

          {/* Form Header */}
          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight text-[var(--text)]">
              {mode === 'login' ? 'Sign in to your workspace' : 'Create student account'}
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              {mode === 'login'
                ? 'Access your course materials, active flashcards, and AI tutor.'
                : 'Join EduVerse AI to manage your academic notes and revision schedules.'}
            </p>
          </div>

          {/* Tab Selector */}
          <div className="grid grid-cols-2 rounded-lg bg-[var(--bg-sunken)] p-1 border border-[var(--border)]">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(null) }}
              className={`py-1.5 text-xs font-semibold rounded-md transition-all ${
                mode === 'login'
                  ? 'bg-[var(--bg-raised)] text-[var(--text)] shadow-xs'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)]'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(null) }}
              className={`py-1.5 text-xs font-semibold rounded-md transition-all ${
                mode === 'register'
                  ? 'bg-[var(--bg-raised)] text-[var(--text)] shadow-xs'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)]'
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{error}</div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text)]">Full Name</label>
                  <Input
                    placeholder="e.g. Sufiyan Sayyed"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text)]">Username</label>
                  <Input
                    placeholder="e.g. sufiyan_ai"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </div>
              </>
            )}

            <div className="space-y-1">
              <label className="text-xs font-semibold text-[var(--text)]">
                {mode === 'login' ? 'Email or Username' : 'Email Address'}
              </label>
              <Input
                type={mode === 'register' ? 'email' : 'text'}
                placeholder={mode === 'login' ? 'student@eduverse.ai' : 'student@icem.edu.in'}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-[var(--text)]">Password</label>
                {mode === 'login' && (
                  <span className="text-[11px] text-[var(--accent)] hover:underline cursor-pointer">
                    Forgot password?
                  </span>
                )}
              </div>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text)] p-1 rounded"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {mode === 'register' && (
                <div className="flex items-center gap-1.5 mt-1 text-[11px] text-[var(--text-muted)]">
                  <CheckCircle2 className={`h-3 w-3 ${password.length >= 8 ? 'text-green-500' : 'text-zinc-500'}`} />
                  <span>Must be at least 8 characters long</span>
                </div>
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full justify-center h-10 text-sm font-semibold"
              disabled={loading}
              loading={loading}
            >
              {mode === 'login' ? 'Sign In to EduVerse' : 'Complete Registration'}
              {!loading && <ArrowRight className="h-4 w-4 ml-1.5" />}
            </Button>
          </form>

          {/* Quick Demo Access Divider */}
          <div className="relative flex py-1 items-center">
            <div className="flex-grow border-t border-[var(--border)]" />
            <span className="flex-shrink mx-3 text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
              Evaluator & Demo Access
            </span>
            <div className="flex-grow border-t border-[var(--border)]" />
          </div>

          {/* One-Click Demo Student Access */}
          <Button
            type="button"
            variant="secondary"
            onClick={handleDemoLogin}
            disabled={loading}
            className="w-full justify-center h-10 border-[var(--accent)]/30 hover:border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)] hover:bg-[var(--accent)]/15 transition-all text-xs font-semibold"
          >
            <Zap className="h-4 w-4 mr-1.5 text-[var(--accent)]" />
            ⚡ One-Click Demo Student Access
          </Button>

          <p className="text-center text-[11px] text-[var(--text-muted)]">
            Preset: <span className="font-mono">student@eduverse.ai</span> / <span className="font-mono">demo123</span>
          </p>
        </div>
      </div>
    </div>
  )
}
