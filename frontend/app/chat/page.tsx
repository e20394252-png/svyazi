'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import Navbar from '@/components/Navbar'
import styles from './chat.module.css'

export default function ChatListPage() {
  const router = useRouter()
  const [conversations, setConversations] = useState<any[]>([])
  const [profile, setProfile] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.push('/auth/login'); return }

    Promise.all([api.getMyProfile(), api.getConversations()]).then(([p, convs]) => {
      setProfile(p)
      setConversations(convs)
      setLoading(false)
    }).catch(() => router.push('/auth/login'))
  }, [router])

  function getInitials(name: string) {
    return name.split(' ').slice(0, 2).map((n: string) => n[0]).join('').toUpperCase()
  }

  function formatTime(time: string) {
    if (!time) return ''
    const d = new Date(time)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    if (isToday) return d.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString('ru', { day: 'numeric', month: 'short' })
  }

  return (
    <div className={styles.page}>
      <Navbar profile={profile} />
      <main className={styles.main}>
        <h1 className={styles.title}>Чат</h1>

        {loading ? (
          <div className="empty-state">
            <span className="spinner spinner-lg" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="empty-state">
            <div className="icon">💬</div>
            <h3>Нет переписок</h3>
            <p>Начните знакомство в разделе «Мэтчи»</p>
            <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={() => router.push('/dashboard')}>
              Перейти к мэтчам
            </button>
          </div>
        ) : (
          <div className={styles.convList}>
            {conversations.map(conv => (
              <div
                key={conv.user_id}
                className={styles.convItem}
                onClick={() => router.push(`/chat/${conv.user_id}`)}
              >
                <div className="avatar">{getInitials(conv.user_name)}</div>
                <div className={styles.convInfo}>
                  <div className={styles.convHeader}>
                    <span className={styles.convName}>{conv.user_name}</span>
                    <span className={styles.convTime}>{formatTime(conv.last_message_time)}</span>
                  </div>
                  <div className={styles.convPreview}>{conv.last_message}</div>
                </div>
                {conv.unread_count > 0 && (
                  <div className={styles.unread}>{conv.unread_count}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
