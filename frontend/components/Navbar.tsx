'use client'
import { useRouter, usePathname } from 'next/navigation'
import styles from './Navbar.module.css'

function getInitials(name: string) {
  if (!name) return '?'
  return name.split(' ').slice(0, 2).map((n: string) => n[0]).join('').toUpperCase()
}

export default function Navbar({ profile }: { profile: any }) {
  const router = useRouter()
  const pathname = usePathname()

  function logout() {
    localStorage.removeItem('token')
    router.push('/')
  }

  const nav = [
    { href: '/dashboard', icon: '⚡', label: 'Мэтчи' },
    { href: '/profile', icon: '👤', label: 'Профиль' },
    { href: '/chat', icon: '💬', label: 'Чат' },
    ...(profile?.is_admin ? [{ href: '/admin', icon: '⚙️', label: 'Админ' }] : []),
  ]

  return (
    <nav className={styles.nav}>
      <div className={styles.inner}>
        <button className={styles.logo} onClick={() => router.push('/dashboard')}>
          <span className={styles.logoIcon}>⚡</span>
          <span className="gradient-text">Связи</span>
        </button>

        <div className={styles.links}>
          {nav.map(item => (
            <button
              key={item.href}
              className={`${styles.link} ${pathname === item.href ? styles.active : ''}`}
              onClick={() => router.push(item.href)}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className={styles.right}>
          {profile && (
            <div
              className={styles.avatar}
              onClick={() => router.push('/profile')}
              title={profile.name}
            >
              {getInitials(profile.name)}
            </div>
          )}
          <button className="btn btn-ghost btn-sm" onClick={logout}>
            Выйти
          </button>
        </div>
      </div>
    </nav>
  )
}
