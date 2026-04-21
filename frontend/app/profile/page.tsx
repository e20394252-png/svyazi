'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Navbar from '@/components/Navbar'
import styles from './profile.module.css'

export default function ProfilePage() {
  const router = useRouter()
  const [profile, setProfile] = useState<any>(null)
  const [form, setForm] = useState<any>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [message, setMessage] = useState({ text: '', type: '' })

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.push('/auth/login'); return }
    api.getMyProfile().then(p => {
      setProfile(p)
      setForm({
        name: p.name || '',
        telegram: p.telegram || '',
        phone: p.phone || '',
        occupation: p.occupation || '',
        bio: p.bio || '',
        city: p.city || '',
        wants: p.wants || '',
        cans: p.cans || '',
        has_items: p.has_items || '',
      })
      setLoading(false)
    }).catch(() => router.push('/auth/login'))
  }, [router])

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f: any) => ({ ...f, [key]: e.target.value }))

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await api.updateProfile(form)
      setProfile(updated)
      showMessage('Профиль сохранён', 'success')
    } catch (e: any) {
      showMessage(e.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true)
    try {
      const result = await api.analyzeProfile()
      const p = result.profile
      setForm((f: any) => ({
        ...f,
        wants: p.wants || f.wants,
        cans: p.cans || f.cans,
        has_items: p.has_items || f.has_items,
      }))
      setProfile(p)
      showMessage('ИИ проанализировал ваш профиль и обновил мэтчинг', 'success')
    } catch (e: any) {
      showMessage(e.message, 'error')
    } finally {
      setAnalyzing(false)
    }
  }

  function showMessage(text: string, type: string) {
    setMessage({ text, type })
    setTimeout(() => setMessage({ text: '', type: '' }), 4000)
  }

  function getInitials(name: string) {
    return name.split(' ').slice(0, 2).map((n: string) => n[0]).join('').toUpperCase()
  }

  if (loading) return (
    <div className={styles.page}>
      <Navbar profile={null} />
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px' }}>
        <span className="spinner spinner-lg" />
      </div>
    </div>
  )

  return (
    <div className={styles.page}>
      <Navbar profile={profile} />
      <main className={styles.main}>
        <h1 className={styles.pageTitle}>Мой профиль</h1>

        {message.text && (
          <div className={`alert alert-${message.type}`}>{message.text}</div>
        )}

        {/* Profile header */}
        <div className={styles.profileHeader}>
          <div className="avatar avatar-lg">{getInitials(profile?.name || '?')}</div>
          <div>
            <div className={styles.profileName}>{profile?.name}</div>
            <div className={styles.profileEmail}>{profile?.email}</div>
            {profile?.telegram && (
              <a
                href={`https://t.me/${profile.telegram.replace('@', '')}`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.telegramLink}
              >
                ✈️ @{profile.telegram.replace('@', '')}
              </a>
            )}
          </div>
        </div>

        <form onSubmit={handleSave}>
          {/* Personal info */}
          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>📋 Личные данные</h2>
            <div className={styles.grid2}>
              <div className="input-group">
                <label className="input-label">Имя</label>
                <input className="input-field" value={form.name} onChange={set('name')} />
              </div>
              <div className="input-group">
                <label className="input-label">Город</label>
                <input className="input-field" placeholder="Сочи" value={form.city} onChange={set('city')} />
              </div>
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
              <label className="input-label">Чем занимаетесь (для ИИ анализа)</label>
              <textarea
                className="input-field"
                rows={3}
                placeholder="Опишите свою деятельность подробно..."
                value={form.occupation}
                onChange={set('occupation')}
              />
            </div>
          </div>

          {/* 3 dimensions */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>🎯 Хочу / Могу / Имею</h2>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleAnalyze}
                disabled={analyzing}
              >
                {analyzing ? <><span className="spinner" /><span>Анализирую...</span></> : '🤖 ИИ-анализ'}
              </button>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
              Нажмите «ИИ-анализ» и система автоматически заполнит эти поля из вашего описания
            </p>
            <div className="input-group">
              <label className="input-label" style={{ color: 'var(--accent-pink)' }}>🎯 ХОЧУ — что ищете</label>
              <textarea
                className="input-field"
                rows={2}
                placeholder="Инвестора, партнёра, клиентов, специалиста по..."
                value={form.wants}
                onChange={set('wants')}
              />
            </div>
            <div className="input-group">
              <label className="input-label" style={{ color: 'var(--accent-blue)' }}>⚡ МОГУ — что предлагаете</label>
              <textarea
                className="input-field"
                rows={2}
                placeholder="Маркетинг, разработка, консультации по..."
                value={form.cans}
                onChange={set('cans')}
              />
            </div>
            <div className="input-group">
              <label className="input-label" style={{ color: 'var(--accent-gold)' }}>💎 ИМЕЮ — ресурсы и активы</label>
              <textarea
                className="input-field"
                rows={2}
                placeholder="База клиентов, помещение, инвестиции, связи в сфере..."
                value={form.has_items}
                onChange={set('has_items')}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            disabled={saving}
          >
            {saving ? <><span className="spinner" /><span>Сохраняем...</span></> : '💾 Сохранить профиль'}
          </button>
        </form>
      </main>
    </div>
  )
}
