'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Link from 'next/link'
import styles from '../auth.module.css'

type AuthMode = 'choose' | 'telegram' | 'email'

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<AuthMode>('choose')

  // ── Email login state ──
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // ── Telegram login state ──
  const [tgStatus, setTgStatus] = useState<'init' | 'waiting' | 'success' | 'error'>('init')
  const [tgError, setTgError] = useState('')
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // ── Telegram flow — one click: opens bot + starts polling ──
  async function handleTelegramLogin() {
    setMode('telegram')
    setTgStatus('waiting')
    setTgError('')
    setError('')

    // Open window SYNCHRONOUSLY before await — iOS Safari blocks popups after async calls
    const botWindow = window.open('about:blank', '_blank')

    try {
      const data = await api.telegramInit()

      // Redirect the already-opened window to bot URL
      if (botWindow && !botWindow.closed) {
        botWindow.location.href = data.bot_url
      } else {
        // Fallback: popup was blocked, navigate current tab
        window.location.href = data.bot_url
        return
      }

      // Start polling
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const check = await api.telegramCheck(data.code)
          if (check.status === 'ok' && check.access_token) {
            clearInterval(pollRef.current!)
            pollRef.current = null
            setTgStatus('success')
            localStorage.setItem('token', check.access_token)
            router.push('/dashboard')
          }
        } catch (e: any) {
          if (e.message?.includes('истёк') || e.message?.includes('использован')) {
            clearInterval(pollRef.current!)
            pollRef.current = null
            setTgStatus('error')
            setTgError('Время истекло. Попробуйте снова.')
          }
        }
      }, 2000)
    } catch (e: any) {
      if (botWindow && !botWindow.closed) botWindow.close()
      setTgStatus('error')
      setTgError(e.message || 'Ошибка инициализации')
    }
  }

  // ── Email login ──
  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await api.login(form)
      localStorage.setItem('token', data.access_token)
      router.push('/dashboard')
    } catch (e: any) {
      setError(e.message || 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.orb1} />
      <div className={styles.orb2} />

      <div className={styles.card}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon}>⚡</span>
          <span className="gradient-text">Связи</span>
        </Link>

        <h1 className={styles.title}>Войти в аккаунт</h1>
        <p className={styles.subtitle}>Добро пожаловать обратно</p>

        {error && <div className="alert alert-error">{error}</div>}

        {/* ── Telegram Auth Section ── */}
        {(mode === 'choose' || mode === 'telegram') && (
          <>
            {tgStatus === 'init' && (
              <button
                type="button"
                className={styles.tgButton}
                onClick={handleTelegramLogin}
                id="telegram-login-btn"
              >
                <svg className={styles.tgIcon} viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                </svg>
                <span>Войти через Telegram</span>
              </button>
            )}

            {tgStatus === 'waiting' && (
              <div className={styles.tgWaiting}>
                <div className={styles.tgPulse}>
                  <span className="spinner" />
                  <span>Нажмите «Start» в боте и вернитесь сюда</span>
                </div>
                <button
                  type="button"
                  className={styles.tgButton}
                  onClick={handleTelegramLogin}
                >
                  <svg className={styles.tgIcon} viewBox="0 0 24 24" fill="currentColor">
                    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                  </svg>
                  <span>Открыть бота ещё раз</span>
                </button>
              </div>
            )}

            {tgStatus === 'success' && (
              <div className={styles.tgSuccess}>
                <span>✅</span>
                <span>Вход выполнен! Перенаправляем...</span>
              </div>
            )}

            {tgStatus === 'error' && (
              <div className={styles.tgError}>
                <div className="alert alert-error">{tgError}</div>
                <button
                  type="button"
                  className={styles.tgButton}
                  onClick={handleTelegramLogin}
                >
                  🔄 Попробовать снова
                </button>
              </div>
            )}
          </>
        )}

        {/* ── Divider ── */}
        <div className={styles.divider}>
          <span>или</span>
        </div>

        {/* ── Email Login (collapsible) ── */}
        {mode === 'choose' && (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => setMode('email')}
            id="email-login-toggle"
          >
            ✉️ Войти по Email
          </button>
        )}

        {mode === 'email' && (
          <form onSubmit={handleEmailSubmit}>
            <div className="input-group">
              <label className="input-label">Email</label>
              <input
                type="email"
                className="input-field"
                placeholder="your@email.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div className="input-group">
              <label className="input-label">Пароль</label>
              <input
                type="password"
                className="input-field"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
              disabled={loading}
            >
              {loading ? <><span className="spinner" /><span>Входим...</span></> : 'Войти'}
            </button>
          </form>
        )}

        <div className={styles.divider}>
          <span>или</span>
        </div>

        <p className={styles.switchText}>
          Нет аккаунта?{' '}
          <Link href="/auth/register" className={styles.link}>
            Зарегистрироваться
          </Link>
        </p>
      </div>
    </div>
  )
}
