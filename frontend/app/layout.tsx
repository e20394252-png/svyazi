import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Связи — Нетворкинг и матчинг',
  description: 'Находите нужных людей по принципу Хочу/Могу/Имею. ИИ-матчинг для деловых знакомств.',
  keywords: 'нетворкинг, матчинг, деловые знакомства, связи, бизнес',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  )
}
