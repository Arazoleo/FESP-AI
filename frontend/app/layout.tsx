import type { Metadata } from 'next'
import { Inter, Space_Grotesk, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'FESP-AI | Assistente acadêmico da UNIFESP ICT',
  description:
    'Assistente acadêmico do Instituto de Ciência e Tecnologia da UNIFESP. Responde sobre disciplinas, docentes, cursos e regimentos consultando um grafo de conhecimento construído a partir de documentos oficiais.',
  keywords: ['UNIFESP', 'ICT', 'São José dos Campos', 'assistente acadêmico', 'knowledge graph'],
  authors: [{ name: 'FESP-AI' }],
  icons: {
    icon: '/fespai-removebg-preview.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="pt-BR"
      suppressHydrationWarning
      className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable}`}
    >
      <body className="font-sans antialiased bg-ink text-paper">
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('fesp-theme')==='light')document.documentElement.classList.add('light')}catch(e){}",
          }}
        />
        {children}
      </body>
    </html>
  )
}
