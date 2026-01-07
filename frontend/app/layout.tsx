import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-sora',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({ 
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'FESP-AI | Assistente Inteligente UNIFESP',
  description: 'Sistema de IA para consulta de informações acadêmicas da UNIFESP Campus São José dos Campos - Powered by Advanced RAG',
  keywords: ['UNIFESP', 'IA', 'Assistente', 'São José dos Campos', 'RAG'],
  authors: [{ name: 'FESP-AI Team' }],
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
    <html lang="pt-BR" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased bg-[#030712]">{children}</body>
    </html>
  )
}
