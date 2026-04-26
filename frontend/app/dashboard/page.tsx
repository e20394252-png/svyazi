'use client'
import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import styles from './dashboard.module.css'
import Navbar from '@/components/Navbar'

type MatchItem = {
  id: number
  user: any
  score: number | null
  reasoning: string | null
  status: string
  created_at: string
  is_mutual?: boolean
}

const TABS = [
  { key: 'top', label: 'Топ мэтчи', icon: '⚡' },
  { key: 'incoming', label: 'Входящие', icon: '📩' },
  { key: 'accepted', label: 'Мои связи', icon: '🤝' },
  { key: 'awaiting', label: 'Ожидают', icon: '⏳' },
]

export default function DashboardPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState('top')
  const [matches, setMatches] = useState<MatchItem[]>([])
  const [loading, setLoading] = useState(true)
  const [finding, setFinding] = useState(false)
  const [message, setMessage] = useState('')
  const [profile, setProfile] = useState<any>(null)
  const [matchStatus, setMatchStatus] = useState<any>(null)
  const [showLog, setShowLog] = useState(false)

  const loadMatches = useCallback(async () => {
    setLoading(true)
    try {
      let data: MatchItem[] = []
      if (activeTab === 'top') data = await api.getTopMatches()
      else if (activeTab === 'incoming') data = await api.getIncomingRequests()
      else if (activeTab === 'accepted') data = await api.getAcceptedMatches()
      else if (activeTab === 'awaiting') data = await api.getAwaitingMatches()
      setMatches(data)
    } catch (e: any) {
      if (e.message === 'Сессия истекла') return
      setMessage(e.message)
    } finally {
      setLoading(false)
    }
  }, [activeTab])

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.push('/auth/login'); return }
    api.getMyProfile().then(setProfile).catch(() => router.push('/auth/login'))
    loadMatches()
  }, [loadMatches, router])

  const profileFilled = !!(
    profile?.wants?.trim() || profile?.cans?.trim() ||
    profile?.has_items?.trim() || profile?.occupation?.trim()
  )

  async function handleFindMatches() {
    if (!profileFilled) {
      setMessage('Сначала заполните профиль: укажите что вы хотите, можете или имеете')
      return
    }
    setFinding(true)
    setMessage('')
    setMatchStatus(null)
    setShowLog(false)
    try {
      const result = await api.findMatches()
      setMessage(result.message)
      // Start polling for status
      pollStatus()
    } catch (e: any) {
      setMessage(e.message)
      setFinding(false)
    }
  }

  function pollStatus() {
    const interval = setInterval(async () => {
      try {
        const status = await api.getMatchingStatus()
        setMatchStatus(status)
        if (status.status === 'done' || status.status === 'error' || status.status === 'idle') {
          clearInterval(interval)
          setFinding(false)
          if (status.status === 'done') {
            await loadMatches()
          }
        }
      } catch {
        clearInterval(interval)
        setFinding(false)
      }
    }, 2000)
  }

  async function handleAccept(matchId: number) {
    await api.acceptMatch(matchId)
    setMatches(prev => prev.filter(m => m.id !== matchId))
    setMessage('Запрос отправлен! Человек получит уведомление.')
    setTimeout(() => setMessage(''), 3000)
  }

  async function handleDismiss(matchId: number) {
    await api.dismissMatch(matchId)
    setMatches(prev => prev.filter(m => m.id !== matchId))
  }

  function getScoreClass(score: number | null) {
    if (!score) return 'score-low'
    if (score >= 75) return 'score-high'
    if (score >= 45) return 'score-mid'
    return 'score-low'
  }

  function getInitials(name: string) {
    return name.split(' ').slice(0, 2).map((n: string) => n[0]).join('').toUpperCase()
  }

  return (
    <div className={styles.page}>
      <Navbar profile={profile} />

      <main className={styles.main}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>Match Hub</h1>
            <p className={styles.subtitle}>Люди, с которыми вам стоит познакомиться</p>
          </div>
          <div className={styles.actions}>
            <button
              className="btn btn-primary"
              onClick={handleFindMatches}
              disabled={finding}
            >
              {finding ? (
                <><span className="spinner" /><span>Ищем...</span></>
              ) : (
                <><span>⚡</span><span>Найти мэтчи</span></>
              )}
            </button>
          </div>
        </div>

        {message && (
          <div className={`alert ${message.includes('Найдено') || message.includes('отправлен') ? 'alert-success' : 'alert-info'}`}>
            {message}
          </div>
        )}

        {/* Matching Status Tracker */}
        {matchStatus && matchStatus.status !== 'idle' && (
          <div style={{
            background: matchStatus.status === 'error' ? 'rgba(239,68,68,0.06)' : matchStatus.status === 'done' ? 'rgba(5,150,105,0.06)' : 'rgba(124,58,237,0.06)',
            border: `1px solid ${matchStatus.status === 'error' ? 'rgba(239,68,68,0.2)' : matchStatus.status === 'done' ? 'rgba(5,150,105,0.2)' : 'rgba(124,58,237,0.2)'}`,
            borderRadius: 'var(--radius-md)',
            padding: '16px',
            marginBottom: '20px',
            fontSize: '14px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: matchStatus.log ? '10px' : '0' }}>
              {matchStatus.status !== 'done' && matchStatus.status !== 'error' && (
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
              )}
              <span style={{ fontWeight: 600, color: matchStatus.status === 'error' ? '#dc2626' : matchStatus.status === 'done' ? '#059669' : '#7c3aed' }}>
                {matchStatus.status === 'done' ? '✅' : matchStatus.status === 'error' ? '❌' : '🔄'}
                {' '}{matchStatus.message}
              </span>
            </div>

            {matchStatus.status === 'done' && matchStatus.saved !== undefined && (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: matchStatus.log ? '8px' : '0' }}>
                📊 ИИ нашёл: {matchStatus.raw_found || 0} | Сохранено: {matchStatus.saved || 0} | Пропущено: {matchStatus.skipped || 0} | Не найдено в БД: {matchStatus.not_found || 0}
              </div>
            )}

            {matchStatus.log && matchStatus.log.length > 0 && (
              <div>
                <button
                  onClick={() => setShowLog(!showLog)}
                  style={{ background: 'none', color: 'var(--accent-purple)', fontSize: 13, fontWeight: 600, cursor: 'pointer', padding: 0 }}
                >
                  {showLog ? '▼ Скрыть детали' : '▶ Показать детали'}
                </button>
                {showLog && (
                  <div style={{
                    marginTop: '8px',
                    maxHeight: '200px',
                    overflowY: 'auto',
                    background: 'rgba(0,0,0,0.03)',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: 12,
                    fontFamily: 'monospace',
                    lineHeight: 1.8,
                  }}>
                    {matchStatus.log.map((line: string, i: number) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="tabs" style={{ marginBottom: '24px' }}>
          {TABS.map(tab => (
            <button
              key={tab.key}
              className={`tab ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className={styles.skeletons}>
            {[1, 2, 3].map(i => (
              <div key={i} className={styles.skeletonCard}>
                <div className="skeleton" style={{ width: 56, height: 56, borderRadius: '50%' }} />
                <div style={{ flex: 1 }}>
                  <div className="skeleton" style={{ width: '60%', height: 18, marginBottom: 8 }} />
                  <div className="skeleton" style={{ width: '90%', height: 14, marginBottom: 6 }} />
                  <div className="skeleton" style={{ width: '75%', height: 14 }} />
                </div>
              </div>
            ))}
          </div>
        ) : matches.length === 0 ? (
          <div className="empty-state">
            <div className="icon">
              {activeTab === 'top' ? '⚡' : activeTab === 'incoming' ? '📩' : activeTab === 'accepted' ? '🤝' : '⏳'}
            </div>
            <h3>
              {activeTab === 'top' && 'Нажмите «Найти мэтчи»'}
              {activeTab === 'incoming' && 'Пока нет входящих запросов'}
              {activeTab === 'accepted' && 'Вы ещё никого не добавили'}
              {activeTab === 'awaiting' && 'Нет ожидающих ответа'}
            </h3>
            <p>
              {activeTab === 'top' && 'ИИ найдёт людей, чьи цели пересекаются с вашими'}
              {activeTab === 'incoming' && 'Когда кто-то захочет с вами познакомиться — они появятся здесь'}
              {activeTab === 'accepted' && 'Нажмите «Познакомиться» в топ-мэтчах'}
              {activeTab === 'awaiting' && 'Люди, которых вы добавили, но они ещё не ответили'}
            </p>
            {activeTab === 'top' && (
              <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={handleFindMatches} disabled={finding}>
                {finding ? 'Ищем...' : '⚡ Найти мэтчи'}
              </button>
            )}
          </div>
        ) : (
          <div className={styles.matchGrid}>
            {matches.map((match, idx) => (
              <div
                key={match.id}
                className={styles.matchCard}
                style={{ animationDelay: `${idx * 0.05}s` }}
              >
                {/* User info */}
                <div className={styles.cardHeader}>
                  <div className="avatar avatar-lg">
                    {getInitials(match.user.name)}
                  </div>
                  <div className={styles.userInfo}>
                    <div className={styles.userName}>{match.user.name}</div>
                    {match.user.city && (
                      <div className={styles.userCity}>📍 {match.user.city}</div>
                    )}
                    {match.score !== null && (
                      <span className={`score-badge ${getScoreClass(match.score)}`}>
                        ⚡ {match.score}% совпадение
                      </span>
                    )}
                    {match.is_mutual && (
                      <span className="score-badge score-high" style={{ marginLeft: 8 }}>
                        🤝 Взаимно
                      </span>
                    )}
                  </div>
                </div>

                {/* Occupation */}
                {match.user.occupation && (
                  <p className={styles.occupation}>{match.user.occupation}</p>
                )}

                {/* 3 dimensions */}
                <div className={styles.dimensions}>
                  {match.user.wants && (
                    <div className={styles.dim}>
                      <div className="dim-label dim-wants">🎯 Хочу</div>
                      <div className={styles.dimText}>{match.user.wants}</div>
                    </div>
                  )}
                  {match.user.cans && (
                    <div className={styles.dim}>
                      <div className="dim-label dim-cans">⚡ Могу</div>
                      <div className={styles.dimText}>{match.user.cans}</div>
                    </div>
                  )}
                  {match.user.has_items && (
                    <div className={styles.dim}>
                      <div className="dim-label dim-has">💎 Имею</div>
                      <div className={styles.dimText}>{match.user.has_items}</div>
                    </div>
                  )}
                </div>

                {/* Tags */}
                {(match.user.wants_tags?.length > 0 || match.user.cans_tags?.length > 0) && (
                  <div className={styles.tags}>
                    {match.user.wants_tags?.slice(0, 3).map((t: string) => (
                      <span key={t} className="tag tag-wants">{t}</span>
                    ))}
                    {match.user.cans_tags?.slice(0, 3).map((t: string) => (
                      <span key={t} className="tag tag-cans">{t}</span>
                    ))}
                  </div>
                )}

                {/* AI reasoning */}
                {match.reasoning && (
                  <div className={styles.reasoning}>
                    <div className={styles.reasoningIcon}>🤖</div>
                    <p className={styles.reasoningText}>{match.reasoning}</p>
                  </div>
                )}

                {/* Actions */}
                <div className={styles.cardActions}>
                  {/* Telegram button always shown */}
                  {match.user.telegram && (
                    <a
                      href={`https://t.me/${match.user.telegram.replace('@', '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary btn-sm"
                    >
                      <span>✈️</span>
                      <span>Telegram</span>
                    </a>
                  )}

                  {activeTab === 'top' && (
                    <>
                      <button className="btn btn-primary btn-sm" onClick={() => handleAccept(match.id)}>
                        <span>🤝</span><span>Познакомиться</span>
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => handleDismiss(match.id)}>
                        Пропустить
                      </button>
                    </>
                  )}
                  {activeTab === 'incoming' && (
                    <button className="btn btn-primary btn-sm" onClick={() => handleAccept(match.id)}>
                      <span>✅</span><span>Принять</span>
                    </button>
                  )}
                  {(activeTab === 'accepted' || activeTab === 'awaiting') && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => router.push(`/chat/${match.user.id}`)}
                    >
                      <span>💬</span><span>Написать</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
