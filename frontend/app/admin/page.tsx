'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Navbar from '@/components/Navbar'

export default function AdminPage() {
  const router = useRouter()
  const [profile, setProfile] = useState<any>(null)
  const [settings, setSettings] = useState<any>(null)
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.push('/auth/login'); return }

    Promise.all([
      api.getMyProfile(),
      api.getAdminSettings(),
      api.getAdminUsers(),
    ]).then(([p, s, u]) => {
      if (!p.is_admin) { router.push('/dashboard'); return }
      setProfile(p)
      setSettings(s)
      setUsers(u)
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

  function formatDate(iso: string) {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' }) +
      ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  if (loading) return (
    <div style={{ padding: 80, textAlign: 'center' }}>
      <span className="spinner spinner-lg" />
    </div>
  )

  const tgUsers = users.filter(u => u.auth_method === 'telegram')
  const emailUsers = users.filter(u => u.auth_method === 'email')

  return (
    <div>
      <Navbar profile={profile} />
      <main style={{ maxWidth: 900, margin: '0 auto', padding: '40px 20px' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>⚙️ Панель администратора</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 32 }}>
          Управление настройками платформы
        </p>

        {message && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>{message}</div>
        )}

        {/* ── Users list ── */}
        <div style={{
          background: 'var(--surface)',
          borderRadius: 16,
          padding: 24,
          border: '1px solid var(--border)',
          marginBottom: 24,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600 }}>👥 Пользователи ({users.length})</h2>
            <div style={{ display: 'flex', gap: 12, fontSize: 13, color: 'var(--text-muted)' }}>
              <span style={{ color: '#0088cc' }}>📱 Telegram: {tgUsers.length}</span>
              <span>✉️ Email: {emailUsers.length}</span>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 14,
            }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={thStyle}>#</th>
                  <th style={thStyle}>Имя</th>
                  <th style={thStyle}>Telegram</th>
                  <th style={thStyle}>Email</th>
                  <th style={thStyle}>Вход</th>
                  <th style={thStyle}>Регистрация</th>
                  <th style={thStyle}>Посл. вход</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u, i) => (
                  <tr key={u.id} style={{
                    borderBottom: '1px solid var(--border)',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)',
                  }}>
                    <td style={tdStyle}>
                      <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{u.id}</span>
                    </td>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 500 }}>{u.name || '—'}</div>
                      {u.city && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{u.city}</div>}
                    </td>
                    <td style={tdStyle}>
                      {u.telegram ? (
                        <a
                          href={`https://t.me/${u.telegram.replace('@', '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#0088cc', textDecoration: 'none', fontWeight: 500 }}
                        >
                          {u.telegram.startsWith('@') ? u.telegram : `@${u.telegram}`}
                        </a>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        fontSize: 13,
                        color: u.email?.includes('@telegram.local') ? 'var(--text-muted)' : 'inherit',
                      }}>
                        {u.email?.includes('@telegram.local') ? '—' : u.email}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      {u.auth_method === 'telegram' ? (
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          padding: '2px 8px',
                          borderRadius: 8,
                          background: 'rgba(0, 136, 204, 0.1)',
                          color: '#0088cc',
                          fontSize: 12,
                          fontWeight: 600,
                        }}>📱 TG</span>
                      ) : (
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          padding: '2px 8px',
                          borderRadius: 8,
                          background: 'rgba(124, 58, 237, 0.1)',
                          color: '#7c3aed',
                          fontSize: 12,
                          fontWeight: 600,
                        }}>✉️ Email</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                        {formatDate(u.created_at)}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      {u.last_login_at ? (
                        <span style={{ fontSize: 13, color: '#16a34a', fontWeight: 500 }}>
                          {formatDate(u.last_login_at)}
                        </span>
                      ) : (
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

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

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '10px 12px',
  fontWeight: 600,
  fontSize: 13,
  color: 'var(--text-muted)',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '10px 12px',
  verticalAlign: 'top',
}
