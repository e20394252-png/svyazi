'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Navbar from '@/components/Navbar'

export default function AdminPage() {
  const router = useRouter()
  const [profile, setProfile] = useState<any>(null)
  const [settings, setSettings] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.push('/auth/login'); return }

    Promise.all([
      api.getMyProfile(),
      api.getAdminSettings(),
    ]).then(([p, s]) => {
      if (!p.is_admin) { router.push('/dashboard'); return }
      setProfile(p)
      setSettings(s)
      setLoading(false)
    }).catch(() => router.push('/auth/login'))
  }, [router])

  async function switchDatabase(db: string) {
    setSaving(true)
    try {
      const result = await api.updateAdminSettings({ active_database: db })
      setSettings((s: any) => ({ ...s, active_database: result.active_database }))
      setMessage(result.message)
      setTimeout(() => setMessage(''), 3000)
    } catch (e: any) {
      setMessage(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div style={{ padding: 80, textAlign: 'center' }}>
      <span className="spinner spinner-lg" />
    </div>
  )

  return (
    <div>
      <Navbar profile={profile} />
      <main style={{ maxWidth: 700, margin: '0 auto', padding: '40px 20px' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>⚙️ Панель администратора</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 32 }}>
          Управление настройками платформы
        </p>

        {message && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>{message}</div>
        )}

        {/* Database switcher */}
        <div style={{
          background: 'var(--surface)',
          borderRadius: 16,
          padding: 24,
          border: '1px solid var(--border)',
          marginBottom: 24,
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>📊 Активная база данных</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 20 }}>
            Выберите какую базу кандидатов использовать для мэтчинга
          </p>

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className={`btn ${settings?.active_database === 'networkers' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => switchDatabase('networkers')}
              disabled={saving}
              style={{ flex: 1 }}
            >
              <span>👥</span>
              <span>Нетворкеры</span>
            </button>
            <button
              className={`btn ${settings?.active_database === 'new' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => switchDatabase('new')}
              disabled={saving}
              style={{ flex: 1 }}
            >
              <span>🆕</span>
              <span>Новая база</span>
            </button>
          </div>

          <p style={{ marginTop: 12, fontSize: 13, color: 'var(--text-muted)' }}>
            Текущая: <strong>{settings?.active_database === 'new' ? 'Новая база' : 'Нетворкеры'}</strong>
          </p>
        </div>

        {/* Webhook info */}
        <div style={{
          background: 'var(--surface)',
          borderRadius: 16,
          padding: 24,
          border: '1px solid var(--border)',
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>🔗 Вебхуки n8n</h2>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            <p><strong>Мэтчинг (Нетворкеры):</strong><br/>{settings?.n8n_matching_webhook || '—'}</p>
            <p style={{ marginTop: 8 }}><strong>Мэтчинг (Новая):</strong><br/>{settings?.n8n_matching_webhook_new || '—'}</p>
            <p style={{ marginTop: 8 }}><strong>Синхронизация профилей:</strong><br/>{settings?.n8n_profile_webhook || '—'}</p>
          </div>
        </div>
      </main>
    </div>
  )
}
