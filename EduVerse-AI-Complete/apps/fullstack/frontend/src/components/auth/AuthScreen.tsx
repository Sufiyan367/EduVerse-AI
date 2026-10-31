import { useEffect, useState } from 'react'
import {
  Brain, BookOpen, Sparkles, ShieldCheck, Eye, EyeOff, ArrowRight,
  GraduationCap, CheckCircle2, AlertCircle, Layers, ArrowLeft, KeyRound
} from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import type { User } from '../../lib/types'
import { Button, Input, Badge } from '../ui'

interface AuthScreenProps {
  onSuccess: (user: User, token: string) => void
}

type AuthMode = 'login' | 'register' | 'forgot' | 'reset'

export function AuthScreen({ onSuccess }: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)

  // Check URL query parameters for reset token
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('reset_token')
      if (token) {
        setResetToken(token)
        setMode('reset')
      }
    }
  }, [])

  const handleLoginOrRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)
    setLoading(true)

    try {
      if (mode === 'login') {
        const res = await api.login({ username: email.trim(), password })
        localStorage.setItem('eduverse_token', res.token)
        localStorage.setItem('eduverse_user', JSON.stringify(res.user))
        onSuccess(res.user, res.token)
      } else if (mode === 'register') {
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

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)
    setLoading(true)

    try {
      const res = await api.forgotPassword(email.trim().toLowerCase())
      setInfoMessage(res.message || 'If an account matches that email address, password reset instructions have been sent.')
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Unable to process password reset request at this time.')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters long.')
      return
    }

    setLoading(true)
    try {
      const res = await api.resetPassword({
        token: resetToken.trim(),
        new_password: newPassword,
      })
      setInfoMessage(res.message || 'Password successfully reset. You may now sign in.')
      setMode('login')
      setPassword('')
      setNewPassword('')
      setResetToken('')
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Invalid or expired password reset token.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-[var(--bg)] text-[var(--text)]">
      {/* Left Column: Brand & Academic Overview */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-[var(--bg-raised)] border-r border-[var(--border)] relative overflow-hidden">
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
                <Badge tone="accent" className="text-[10px] font-semibold tracking-wide">Study Platform v1.0</Badge>
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
              <GraduationCap className="h-3.5 w-3.5" /> AI-Powered Study Workspace
            </span>
            <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight leading-tight text-[var(--text)]">
              Transform Course Materials Into <span className="text-[var(--accent)]">Mastered Knowledge</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed">
              An intelligent, grounded study workspace inspired by Google NotebookLM. Ingest syllabi, lecture slides,
              and academic PDFs with traceable source citations, FSRS-6 spaced repetition, and real-time gap analysis.
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
                  AI tutor responses are scoped to your documents and cite traceable passage coordinates and page numbers.
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
                  Memory scheduling with 4-grade feedback that predicts memory retention curves for upcoming exams.
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
                  Identifies misconceptions from quiz practice and schedules targeted remedial revision sessions.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Security Footer */}
        <div className="relative z-10 flex items-center justify-between text-xs text-[var(--text-muted)] border-t border-[var(--border)] pt-6">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[var(--accent)]" />
            <span>Argon2id Hashed Passwords & Tenant Isolated</span>
          </div>
          <span>Department of Artificial Intelligence & Data Science</span>
        </div>
      </div>

      {/* Right Column: Authentication & Password Reset Forms */}
      <div className="flex-1 flex flex-col justify-center items-center p-6 sm:p-12 lg:p-16">
        <div className="w-full max-w-md space-y-6">
          {/* Mobile Header */}
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
              {mode === 'login' && 'Sign in to your workspace'}
              {mode === 'register' && 'Create student account'}
              {mode === 'forgot' && 'Reset your password'}
              {mode === 'reset' && 'Set a new password'}
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              {mode === 'login' && 'Access your course materials, active flashcards, and grounded AI tutor.'}
              {mode === 'register' && 'Join EduVerse AI to manage your academic notes and revision schedules.'}
              {mode === 'forgot' && 'Enter your registered email address to receive password reset instructions.'}
              {mode === 'reset' && 'Enter your reset token and choose a new secure password.'}
            </p>
          </div>

          {/* Tab Selector (only in login/register modes) */}
          {(mode === 'login' || mode === 'register') && (
            <div className="grid grid-cols-2 rounded-lg bg-[var(--bg-sunken)] p-1 border border-[var(--border)]">
              <button
                type="button"
                onClick={() => { setMode('login'); setError(null); setInfoMessage(null) }}
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
                onClick={() => { setMode('register'); setError(null); setInfoMessage(null) }}
                className={`py-1.5 text-xs font-semibold rounded-md transition-all ${
                  mode === 'register'
                    ? 'bg-[var(--bg-raised)] text-[var(--text)] shadow-xs'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                }`}
              >
                Create Account
              </button>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{error}</div>
            </div>
          )}

          {/* Info Banner */}
          {infoMessage && (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-[var(--accent-soft)] border border-[var(--accent)]/30 text-[var(--accent)] text-xs">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{infoMessage}</div>
            </div>
          )}

          {/* Mode: Login or Register */}
          {(mode === 'login' || mode === 'register') && (
            <form onSubmit={handleLoginOrRegister} className="space-y-4">
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
                  placeholder={mode === 'login' ? 'student@icem.edu.in' : 'student@icem.edu.in'}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-[var(--text)]">Password</label>
                  {mode === 'login' && (
                    <button
                      type="button"
                      onClick={() => { setMode('forgot'); setError(null); setInfoMessage(null) }}
                      className="text-[11px] text-[var(--accent)] hover:underline cursor-pointer"
                    >
                      Forgot password?
                    </button>
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
                {mode === 'login' ? 'Sign In' : 'Create Account'}
                {!loading && <ArrowRight className="h-4 w-4 ml-1.5" />}
              </Button>
            </form>
          )}

          {/* Mode: Forgot Password */}
          {mode === 'forgot' && (
            <div className="space-y-4">
              <form onSubmit={handleForgotPassword} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text)]">Registered Email Address</label>
                  <Input
                    type="email"
                    placeholder="student@icem.edu.in"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  className="w-full justify-center h-10 text-sm font-semibold"
                  disabled={loading || !email.trim()}
                  loading={loading}
                >
                  Send Reset Instructions
                </Button>
              </form>

              <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
                <button
                  type="button"
                  onClick={() => { setMode('login'); setError(null); setInfoMessage(null) }}
                  className="flex items-center gap-1 hover:text-[var(--text)] transition"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Back to Sign In
                </button>
                <button
                  type="button"
                  onClick={() => { setMode('reset'); setError(null); setInfoMessage(null) }}
                  className="text-[var(--accent)] hover:underline"
                >
                  Already have a reset token?
                </button>
              </div>
            </div>
          )}

          {/* Mode: Reset Password with Token */}
          {mode === 'reset' && (
            <div className="space-y-4">
              <form onSubmit={handleResetPassword} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text)]">Reset Token</label>
                  <Input
                    placeholder="Paste your reset token..."
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text)]">New Password</label>
                  <div className="relative">
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Minimum 8 characters"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
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
                  <div className="flex items-center gap-1.5 mt-1 text-[11px] text-[var(--text-muted)]">
                    <CheckCircle2 className={`h-3 w-3 ${newPassword.length >= 8 ? 'text-green-500' : 'text-zinc-500'}`} />
                    <span>Must be at least 8 characters long</span>
                  </div>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  className="w-full justify-center h-10 text-sm font-semibold"
                  disabled={loading || !resetToken.trim() || newPassword.length < 8}
                  loading={loading}
                >
                  <KeyRound className="h-4 w-4 mr-1.5" /> Set New Password
                </Button>
              </form>

              <div className="pt-2 border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
                <button
                  type="button"
                  onClick={() => { setMode('login'); setError(null); setInfoMessage(null) }}
                  className="flex items-center gap-1 hover:text-[var(--text)] transition"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Return to Sign In
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
