'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Navbar from '@/components/Navbar'

const PAGE_SIZE = 20

export default function AdminPage() {
  const router = useRouter()
  const [profile, setProfile] = useState<any>(null)
  const [settings, setSettings] = useState<any>(null)
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [page, setPage] = useState(1)

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
  const totalPages = Math.ceil(users.length / PAGE_SIZE)
  const pageUsers = users.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <div>
      <Navbar profile={profile} />
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 20px' }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>⚙️ Панель администратора</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 32 }}>
          Управление настройками платформы
        </p>

        {message && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>{message}</div>
        )}

        {/* ── Settings row: DB + Webhooks side by side ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
          {/* Database switcher */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>📊 База данных</h2>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className={`btn btn-sm ${settings?.active_database === 'networkers' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => switchDatabase('networkers')}
                disabled={saving}
                style={{ flex: 1 }}
              >
                👥 Нетворкеры
              </button>
              <button
                className={`btn btn-sm ${settings?.active_database === 'new' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => switchDatabase('new')}
                disabled={saving}
                style={{ flex: 1 }}
              >
                🆕 Новая
              </button>
            </div>
          </div>

          {/* Webhook info */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>🔗 Вебхуки</h2>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              <div><strong>Мэтчинг:</strong> {settings?.n8n_matching_webhook ? '✅' : '❌'}</div>
              <div><strong>Новая:</strong> {settings?.n8n_matching_webhook_new ? '✅' : '❌'}</div>
              <div><strong>Профили:</strong> {settings?.n8n_profile_webhook ? '✅' : '❌'}</div>
            </div>
          </div>
        </div>

        {/* ── Users list with pagination ── */}
        <div style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600 }}>👥 Пользователи ({users.length})</h2>
            <div style={{ display: 'flex', gap: 12, fontSize: 13, color: 'var(--text-muted)' }}>
              <span style={{ color: '#0088cc' }}>📱 TG: {tgUsers.length}</span>
              <span>✉️ Email: {emailUsers.length}</span>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={thStyle}>Имя</th>
                  <th style={thStyle}>Telegram</th>
                  <th style={thStyle}>Email</th>
                  <th style={thStyle}>Способ</th>
                  <th style={thStyle}>Регистрация</th>
                  <th style={thStyle}>Посл. вход</th>
                </tr>
              </thead>
              <tbody>
                {pageUsers.map((u, i) => (
                  <tr key={u.id} style={{
                    borderBottom: '1px solid var(--border)',
                    background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)',
                  }}>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 500, whiteSpace: 'nowrap' }}>{u.name || '—'}</div>
                    </td>
                    <td style={tdStyle}>
                      {u.telegram ? (
                        <a
                          href={`https://t.me/${u.telegram.replace('@', '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#0088cc', textDecoration: 'none', fontWeight: 500, whiteSpace: 'nowrap' }}
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
                        whiteSpace: 'nowrap',
                      }}>
                        {u.email?.includes('@telegram.local') ? '—' : u.email}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      {u.auth_method === 'telegram' ? (
                        <span style={badgeStyle('#0088cc')}>📱 TG</span>
                      ) : (
                        <span style={badgeStyle('#7c3aed')}>✉️ Email</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(u.created_at)}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      {u.last_login_at ? (
                        <span style={{ fontSize: 12, color: '#16a34a', fontWeight: 500, whiteSpace: 'nowrap' }}>
                          {formatDate(u.last_login_at)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Pagination ── */}
          {totalPages > 1 && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              marginTop: 20,
              paddingTop: 16,
              borderTop: '1px solid var(--border)',
            }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage(1)}
                disabled={page === 1}
                style={{ fontSize: 13 }}
              >«</button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{ fontSize: 13 }}
              >‹</button>

              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
                .reduce((acc: (number | string)[], p, i, arr) => {
                  if (i > 0 && typeof arr[i - 1] === 'number' && (p as number) - (arr[i - 1] as number) > 1) {
                    acc.push('...')
                  }
                  acc.push(p)
                  return acc
                }, [])
                .map((p, i) =>
                  p === '...' ? (
                    <span key={`dots-${i}`} style={{ padding: '0 4px', color: 'var(--text-muted)' }}>…</span>
                  ) : (
                    <button
                      key={p}
                      className={`btn btn-sm ${page === p ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => setPage(p as number)}
                      style={{ minWidth: 36, fontSize: 13 }}
                    >{p}</button>
                  )
                )
              }

              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                style={{ fontSize: 13 }}
              >›</button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage(totalPages)}
                disabled={page === totalPages}
                style={{ fontSize: 13 }}
              >»</button>

              <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, users.length)} из {users.length}
              </span>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface)',
  borderRadius: 16,
  padding: 24,
  border: '1px solid var(--border)',
  marginBottom: 24,
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 10px',
  fontWeight: 600,
  fontSize: 12,
  color: 'var(--text-muted)',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '8px 10px',
  verticalAlign: 'middle',
}

function badgeStyle(color: string): React.CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    borderRadius: 8,
    background: `${color}18`,
    color,
    fontSize: 12,
    fontWeight: 600,
  }
}
