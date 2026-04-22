'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { api } from '@/lib/api'
import Navbar from '@/components/Navbar'
import styles from '../chat.module.css'

export default function ChatPage() {
  const router = useRouter()
  const params = useParams()
  const userId = Number(params.userId)
  const [messages, setMessages] = useState<any[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [myProfile, setMyProfile] = useState<any>(null)
  const [theirProfile, setTheirProfile] = useState<any>(null)
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.push('/auth/login'); return }

    Promise.all([
      api.getMyProfile(),
      api.getProfile(userId),
      api.getMessages(userId),
    ]).then(([me, them, msgs]) => {
      setMyProfile(me)
      setTheirProfile(them)
      setMessages(msgs)
    })

    // Poll for new messages every 5s
    const interval = setInterval(async () => {
      try {
        const msgs = await api.getMessages(userId)
        setMessages(msgs)
      } catch (e) {}
    }, 5000)

    return () => clearInterval(interval)
  }, [userId, router])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!newMessage.trim()) return
    setSending(true)
    try {
      const msg = await api.sendMessage(userId, newMessage.trim())
      setMessages(prev => [...prev, msg])
      setNewMessage('')
    } catch (e: any) {
      alert(e.message)
    } finally {
      setSending(false)
    }
  }

  function getInitials(name: string) {
    if (!name) return '?'
    return name.split(' ').slice(0, 2).map((n: string) => n[0]).join('').toUpperCase()
  }

  function cleanText(text: string | null | undefined): string | null {
    if (!text) return null
    const qRatio = (text.match(/\?/g) || []).length / Math.max(text.length, 1)
    return qRatio > 0.2 ? null : text
  }

  function getSubtitle(profile: any): string | null {
    if (!profile) return null
    if (cleanText(profile.occupation)) return cleanText(profile.occupation)!.slice(0, 60)
    if (profile.cans) return profile.cans.slice(0, 60)
    if (profile.wants) return profile.wants.slice(0, 60)
    return null
  }

  function formatTime(ts: string) {
    return new Date(ts).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className={styles.page}>
      <Navbar profile={myProfile} />
      <div className={styles.chatLayout}>
        {/* Chat header */}
        <div className={styles.chatHeader}>
          <button className="btn btn-ghost btn-sm" onClick={() => router.back()}>← Назад</button>
          {theirProfile && (
            <div className={styles.chatPartner}>
              <div className="avatar avatar-sm">{getInitials(theirProfile.name)}</div>
              <div>
                <div className={styles.partnerName}>{theirProfile.name}</div>
                {getSubtitle(theirProfile) && (
                  <div className={styles.partnerOcc}>{getSubtitle(theirProfile)}</div>
                )}
              </div>
            </div>
          )}
          {theirProfile?.telegram && (
            <a
              href={`https://t.me/${theirProfile.telegram.replace('@', '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary btn-sm"
            >
              ✈️ Telegram
            </a>
          )}
        </div>

        {/* Messages */}
        <div className={styles.messages}>
          {messages.length === 0 && (
            <div className="empty-state" style={{ height: '100%' }}>
              <div className="icon">💬</div>
              <h3>Начните разговор</h3>
              <p>Напишите первое сообщение</p>
            </div>
          )}
          {messages.map(msg => {
            const isMe = msg.sender_id === myProfile?.id
            return (
              <div key={msg.id} className={`${styles.msgRow} ${isMe ? styles.msgMe : styles.msgThem}`}>
                {!isMe && (
                  <div className="avatar avatar-sm" style={{ flexShrink: 0 }}>
                    {getInitials(theirProfile?.name || '?')}
                  </div>
                )}
                <div className={`${styles.bubble} ${isMe ? styles.bubbleMe : styles.bubbleThem}`}>
                  <div className={styles.bubbleText}>{msg.content}</div>
                  <div className={styles.bubbleTime}>{formatTime(msg.created_at)}</div>
                </div>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className={styles.inputRow}>
          <input
            className="input-field"
            style={{ flex: 1 }}
            placeholder="Написать сообщение..."
            value={newMessage}
            onChange={e => setNewMessage(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={sending || !newMessage.trim()}>
            {sending ? <span className="spinner" /> : '→'}
          </button>
        </form>
      </div>
    </div>
  )
}
