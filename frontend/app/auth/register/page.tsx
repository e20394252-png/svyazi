'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Link from 'next/link'
import styles from '../auth.module.css'

type RegMode = 'choose' | 'telegram' | 'email'

export default function RegisterPage() {
  const router = useRouter()
  const [mode, setMode] = useState<RegMode>('choose')

  // ── Email registration state ──
  const [form, setForm] = useState({
    name: '', email: '', password: '',
    telegram: '', phone: '', occupation: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // ── Telegram state ──
  const [tgStatus, setTgStatus] = useState<'init' | 'waiting' | 'success' | 'error'>('init')
  const [tgError, setTgError] = useState('')
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value })

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // ── Telegram flow — one click ──
  async function handleTelegramRegister() {
    setMode('telegram')
    setTgStatus('waiting')
    setTgError('')
    setError('')

    try {
      const data = await api.telegramInit()

      // Immediately open bot
      window.open(data.bot_url, '_blank')

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
      setTgStatus('error')
      setTgError(e.message || 'Ошибка инициализации')
    }
  }

  // ── Email registration ──
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (form.password.length < 6) {
      setError('Пароль должен быть не менее 6 символов')
      return
    }
    setLoading(true)
    try {
      const data = await api.register(form)
      localStorage.setItem('token', data.access_token)
      router.push('/dashboard')
    } catch (e: any) {
      setError(e.message || 'Ошибка регистрации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.orb1} />
      <div className={styles.orb2} />

      <div className={styles.card} style={{ maxWidth: '480px' }}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon}>⚡</span>
          <span className="gradient-text">Связи</span>
        </Link>

        <h1 className={styles.title}>Создать аккаунт</h1>
        <p className={styles.subtitle}>Присоединяйся к 1000+ нетворкерам</p>

        {error && <div className="alert alert-error">{error}</div>}

        {/* ── Telegram Auth ── */}
        {(mode === 'choose' || mode === 'telegram') && (
          <>
            {tgStatus === 'init' && (
              <button
                type="button"
                className={styles.tgButton}
                onClick={handleTelegramRegister}
                id="telegram-register-btn"
              >
                <svg className={styles.tgIcon} viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                </svg>
                <span>Регистрация через Telegram</span>
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
                  onClick={handleTelegramRegister}
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
                <span>Регистрация выполнена! Перенаправляем...</span>
              </div>
            )}

            {tgStatus === 'error' && (
              <div className={styles.tgError}>
                <div className="alert alert-error">{tgError}</div>
                <button
                  type="button"
                  className={styles.tgButton}
                  onClick={handleTelegramRegister}
                >
                  🔄 Попробовать снова
                </button>
              </div>
            )}
          </>
        )}

        {/* ── Divider ── */}
        <div className={styles.divider}><span>или</span></div>

        {/* ── Email Registration (collapsible) ── */}
        {mode === 'choose' && (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => setMode('email')}
            id="email-register-toggle"
          >
            ✉️ Регистрация по Email
          </button>
        )}

        {mode === 'email' && (
          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label className="input-label">Имя и фамилия *</label>
              <input className="input-field" placeholder="Иван Иванов" value={form.name} onChange={set('name')} required />
            </div>
            <div className="input-group">
              <label className="input-label">Email *</label>
              <input type="email" className="input-field" placeholder="your@email.com" value={form.email} onChange={set('email')} required />
            </div>
            <div className="input-group">
              <label className="input-label">Пароль *</label>
              <input type="password" className="input-field" placeholder="Минимум 6 символов" value={form.password} onChange={set('password')} required />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="input-group">
                <label className="input-label">Telegram</label>
                <input className="input-field" placeholder="@username" value={form.telegram} onChange={set('telegram')} />
              </div>
              <div className="input-group">
                <label className="input-label">Телефон</label>
                <input className="input-field" placeholder="+7..." value={form.phone} onChange={set('phone')} />
              </div>
            </div>
            <div className="input-group">
              <label className="input-label">
                Чем занимаетесь? <span style={{ color: 'var(--text-muted)' }}>(ИИ разберёт сам)</span>
              </label>
              <textarea
                className="input-field"
                placeholder="Опишите свою деятельность, что предлагаете и что ищете. Чем подробнее, тем точнее мэтчинг."
                value={form.occupation}
                onChange={set('occupation')}
                rows={3}
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
              disabled={loading}
            >
              {loading ? <><span className="spinner" /><span>Регистрируемся...</span></> : '⚡ Начать поиск связей'}
            </button>
          </form>
        )}

        <div className={styles.divider}><span>или</span></div>
        <p className={styles.switchText}>
          Уже есть аккаунт?{' '}
          <Link href="/auth/login" className={styles.link}>Войти</Link>
        </p>
      </div>
    </div>
  )
}
