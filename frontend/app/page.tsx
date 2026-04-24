'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import styles from './page.module.css'

export default function LandingPage() {
  const router = useRouter()

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) router.push('/dashboard')
  }, [router])

  return (
    <div className={styles.page}>
      {/* Animated background orbs */}
      <div className={styles.orb1} />
      <div className={styles.orb2} />
      <div className={styles.orb3} />

      {/* Header */}
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>⚡</span>
          <span className="gradient-text">Связи</span>
        </div>
        <div className={styles.headerActions}>
          <button className="btn btn-ghost" onClick={() => router.push('/auth/login')}>
            Войти
          </button>
          <button className="btn btn-primary" onClick={() => router.push('/auth/register')}>
            Начать
          </button>
        </div>
      </header>

      {/* Hero */}
      <main className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.badge}>
            <span>✨</span>
            <span>ИИ-мэтчинг для нетворкеров</span>
          </div>

          <h1 className={styles.heroTitle}>
            Находи нужных людей
            <br />
            <span className="gradient-text">за секунды</span>
          </h1>

          <p className={styles.heroSubtitle}>
            Расскажи, что ты ищешь, что умеешь и что имеешь — 
            и ИИ сам найдёт тех, кто тебе подходит из сообщества 1000+ нетворкеров
          </p>

          <div className={styles.ctaGroup}>
            <button
              className="btn btn-primary btn-lg"
              onClick={() => router.push('/auth/register')}
            >
              Найти связи
            </button>
            <button
              className="btn btn-secondary btn-lg"
              onClick={() => router.push('/auth/login')}
            >
              Войти
            </button>
          </div>

          {/* Stats */}
          <div className={styles.stats}>
            <div className={styles.stat}>
              <span className={styles.statNum}>1000+</span>
              <span className={styles.statLabel}>нетворкеров</span>
            </div>
            <div className={styles.statDivider} />
            <div className={styles.stat}>
              <span className={styles.statNum}>ИИ</span>
              <span className={styles.statLabel}>мэтчинг</span>
            </div>
            <div className={styles.statDivider} />
            <div className={styles.stat}>
              <span className={styles.statNum}>Сочи</span>
              <span className={styles.statLabel}>и не только</span>
            </div>
          </div>
        </div>

        {/* Feature cards */}
        <div className={styles.features}>
          <div className={styles.featureCard}>
            <div className={styles.featureIcon} style={{ background: 'rgba(236,72,153,0.15)' }}>
              🎯
            </div>
            <div>
              <div className={styles.featureDim} style={{ color: 'var(--accent-pink)' }}>ХОЧУ</div>
              <div className={styles.featureText}>Что вы ищете: инвестора, клиентов, партнёра, специалиста</div>
            </div>
          </div>
          <div className={styles.featureCard}>
            <div className={styles.featureIcon} style={{ background: 'rgba(59,130,246,0.15)' }}>
              ⚡
            </div>
            <div>
              <div className={styles.featureDim} style={{ color: 'var(--accent-blue)' }}>МОГУ</div>
              <div className={styles.featureText}>Ваши навыки и услуги: маркетинг, разработка, коучинг</div>
            </div>
          </div>
          <div className={styles.featureCard}>
            <div className={styles.featureIcon} style={{ background: 'rgba(245,158,11,0.15)' }}>
              💎
            </div>
            <div>
              <div className={styles.featureDim} style={{ color: 'var(--accent-gold)' }}>ИМЕЮ</div>
              <div className={styles.featureText}>Ресурсы: база клиентов, помещение, инвестиции, связи</div>
            </div>
          </div>
        </div>
      </main>

      {/* How it works */}
      <section className={styles.howItWorks}>
        <h2 className={styles.sectionTitle}>Как это работает</h2>
        <div className={styles.steps}>
          {[
            { num: '1', icon: '📝', title: 'Заполни профиль', text: 'Расскажи о себе: что умеешь, что ищешь, чем располагаешь' },
            { num: '2', icon: '🤖', title: 'ИИ анализирует', text: 'Алгоритм находит смысловые совпадения с другими участниками' },
            { num: '3', icon: '⚡', title: 'Получи мэтчи', text: 'Смотри топ совпадений с объяснением почему вам стоит познакомиться' },
            { num: '4', icon: '🤝', title: 'Знакомься', text: 'Принимай запросы, пиши в Telegram и строй полезные связи' },
          ].map((s) => (
            <div key={s.num} className={styles.step}>
              <div className={styles.stepNum}>{s.num}</div>
              <div className={styles.stepIcon}>{s.icon}</div>
              <h3 className={styles.stepTitle}>{s.title}</h3>
              <p className={styles.stepText}>{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className={styles.footer}>
        <span className="gradient-text" style={{ fontWeight: 700 }}>Связи</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
          Нетворкинг + ИИ мэтчинг © 2026
        </span>
      </footer>
    </div>
  )
}
