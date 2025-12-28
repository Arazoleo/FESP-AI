import type { Metadata } from 'next'
import { Sora, Space_Mono } from 'next/font/google'
import './globals.css'

const sora = Sora({ 
  subsets: ['latin'],
  variable: '--font-sora',
  display: 'swap',
})

const spaceMono = Space_Mono({ 
  weight: ['400', '700'],
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'FESP-AI | Assistente Inteligente UNIFESP',
  description: 'Sistema de IA para consulta de informações acadêmicas da UNIFESP Campus São José dos Campos - Powered by Advanced RAG',
  icons: {
    icon: '/favicon.ico',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${sora.variable} ${spaceMono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  )
}
