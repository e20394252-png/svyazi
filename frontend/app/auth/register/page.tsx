'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Link from 'next/link'
import styles from '../auth.module.css'

export default function RegisterPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    name: '', email: '', password: '',
    telegram: '', phone: '', occupation: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value })

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
        <p className={styles.subtitle}>Присоединяйся к 666+ нетворкерам</p>

        {error && <div className="alert alert-error">{error}</div>}

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
              placeholder="Опишите свою деятельность, что предлагаете и что ищете. Чем подробнее, тем точнее матчинг."
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

        <div className={styles.divider}><span>или</span></div>
        <p className={styles.switchText}>
          Уже есть аккаунт?{' '}
          <Link href="/auth/login" className={styles.link}>Войти</Link>
        </p>
      </div>
    </div>
  )
}
