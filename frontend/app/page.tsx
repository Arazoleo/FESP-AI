'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { 
  Sparkles, 
  Brain, 
  Zap, 
  ArrowRight,
  GraduationCap,
  BookOpen,
  Users,
  Clock,
  ChevronDown,
} from 'lucide-react'

export default function LandingPage() {
  const router = useRouter()
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })
  const [isLoaded, setIsLoaded] = useState(false)
  const heroRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setIsLoaded(true)
    
    const handleMouseMove = (e: MouseEvent) => {
      if (heroRef.current) {
        const rect = heroRef.current.getBoundingClientRect()
        setMousePosition({
          x: (e.clientX - rect.left) / rect.width,
          y: (e.clientY - rect.top) / rect.height,
        })
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const features = [
    {
      icon: BookOpen,
      title: 'Disciplinas',
      description: 'Informações completas sobre ementas, pré-requisitos e bibliografia',
      gradient: 'from-emerald-400 to-emerald-600',
    },
    {
      icon: Users,
      title: 'Docentes',
      description: 'Descubra quem leciona cada disciplina e suas especialidades',
      gradient: 'from-emerald-500 to-emerald-700',
    },
    {
      icon: Clock,
      title: 'Carga Horária',
      description: 'Consulte horas teóricas, práticas e de extensão',
      gradient: 'from-emerald-300 to-emerald-500',
    },
    {
      icon: GraduationCap,
      title: 'Regimentos',
      description: 'Acesse normas, regulamentos e informações institucionais',
      gradient: 'from-emerald-600 to-emerald-800',
    },
  ]

  return (
    <div className="relative min-h-screen bg-[#030712] text-white overflow-hidden">
      {/* ===== ANIMATED BACKGROUND ===== */}
      <div className="fixed inset-0 overflow-hidden">
        {/* Gradient Orbs - Monocromático Verde */}
        <div 
          className="absolute w-[800px] h-[800px] rounded-full opacity-30 blur-[120px] transition-all duration-1000 ease-out"
          style={{
            background: 'radial-gradient(circle, rgba(16, 185, 129, 0.8) 0%, transparent 70%)',
            left: `${mousePosition.x * 20 - 10}%`,
            top: `${mousePosition.y * 20 - 10}%`,
          }}
        />
        <div 
          className="absolute w-[600px] h-[600px] rounded-full opacity-25 blur-[100px] transition-all duration-1000 ease-out"
          style={{
            background: 'radial-gradient(circle, rgba(52, 211, 153, 0.7) 0%, transparent 70%)',
            right: `${(1 - mousePosition.x) * 20 - 10}%`,
            bottom: `${(1 - mousePosition.y) * 20 - 10}%`,
          }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full opacity-20 blur-[80px] bg-gradient-to-r from-emerald-700 to-emerald-500 animate-pulse" />
        
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cpath%20d%3D%22M0%200h60v60H0z%22%2F%3E%3Cpath%20d%3D%22M60%200v60H0%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.03)%22%20stroke-width%3D%221%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E')] opacity-50" />
      
        {/* Floating Particles - Verde */}
        {[...Array(40)].map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full animate-float-particle"
            style={{
              width: `${2 + Math.random() * 3}px`,
              height: `${2 + Math.random() * 3}px`,
              background: `rgba(16, 185, 129, ${0.3 + Math.random() * 0.5})`,
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${8 + Math.random() * 10}s`,
              boxShadow: `0 0 ${4 + Math.random() * 6}px rgba(16, 185, 129, 0.5)`,
            }}
          />
        ))}

        {/* Horizontal Lines */}
        <div className="absolute inset-0">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="absolute h-px w-full bg-gradient-to-r from-transparent via-emerald-500/30 to-transparent animate-scan-line"
              style={{
                top: `${20 + i * 15}%`,
                animationDelay: `${i * 0.5}s`,
              }}
            />
          ))}
        </div>
      </div>
                
      {/* ===== HERO SECTION ===== */}
      <section ref={heroRef} className="relative min-h-screen flex flex-col items-center justify-center px-6 py-20">
        {/* Glowing Badge */}
        <div 
          className={`
            mb-8 px-5 py-2.5 rounded-full
            bg-emerald-500/10
            border border-emerald-500/30
            backdrop-blur-xl
            flex items-center gap-3
            transition-all duration-1000
            ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}
          `}
        >
          <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="text-sm font-medium text-emerald-300">
            Powered by Advanced RAG Technology
                  </span>
              </div>

        {/* Main Title */}
        <div className="text-center max-w-5xl mx-auto">
          <h1 
            className={`
              text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-black tracking-tighter mb-6
              transition-all duration-1000 delay-200
              ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}
            `}
          >
            {/* FESP-AI em uma linha com estilo premium */}
            <div className="flex items-center justify-center gap-2 sm:gap-4">
              <span className="bg-gradient-to-b from-white via-emerald-100 to-emerald-200 bg-clip-text text-transparent drop-shadow-2xl">
                FESP
              </span>
              <span className="relative">
                <span className="absolute inset-0 bg-emerald-500 blur-2xl opacity-50 animate-pulse" />
                <span className="relative bg-gradient-to-br from-emerald-300 via-emerald-400 to-emerald-600 bg-clip-text text-transparent">
                  AI
                </span>
              </span>
            </div>
          </h1>

          {/* Subtitle */}
          <p 
            className={`
              text-xl sm:text-2xl md:text-3xl text-slate-400 max-w-3xl mx-auto mb-12
              transition-all duration-1000 delay-300
              ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}
            `}
          >
            O assistente inteligente da{' '}
            <span className="text-white font-semibold">UNIFESP</span>
            <br className="hidden sm:block" />
            {' '}que entende suas dúvidas acadêmicas
          </p>

          {/* CTA Button */}
          <div 
            className={`
              flex flex-col sm:flex-row items-center justify-center gap-4
              transition-all duration-1000 delay-500
              ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}
            `}
          >
              <button
              onClick={() => router.push('/chat')}
                className="
                group relative px-10 py-5 rounded-2xl
                bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-500
                text-white font-bold text-lg
                overflow-hidden
                transition-all duration-500
                hover:scale-105
                hover:shadow-[0_0_60px_rgba(16,185,129,0.6)]
                active:scale-95
                border border-emerald-400/30
              "
            >
              {/* Shine Effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
              
              {/* Button Content */}
              <span className="relative flex items-center gap-3">
                <Sparkles className="w-5 h-5" />
                Experimentar Agora
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </span>
              </button>

            {/* Secondary Info */}
            <div className="flex items-center gap-2 text-slate-500 text-sm">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span>Respostas instantâneas</span>
            </div>
          </div>
        </div>

        {/* Scroll Indicator */}
        <div 
          className={`
            absolute bottom-10 left-1/2 -translate-x-1/2
            flex flex-col items-center gap-2
            transition-all duration-1000 delay-700
            ${isLoaded ? 'opacity-100' : 'opacity-0'}
          `}
        >
          <span className="text-xs text-slate-500 uppercase tracking-widest">Explore</span>
          <ChevronDown className="w-5 h-5 text-slate-500 animate-bounce" />
        </div>

        {/* Decorative Brain Icon */}
        <div 
          className={`
            absolute right-10 top-1/2 -translate-y-1/2 hidden xl:block
            transition-all duration-1000 delay-500
            ${isLoaded ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-20'}
          `}
        >
          <div className="relative">
            <div className="absolute inset-0 bg-emerald-500/40 rounded-full blur-3xl animate-pulse" />
            <Brain className="w-32 h-32 text-emerald-500/40" strokeWidth={0.5} />
          </div>
        </div>
      </section>

      {/* ===== FEATURES SECTION ===== */}
      <section className="relative py-32 px-6">
        <div className="max-w-7xl mx-auto">
          {/* Section Header */}
          <div className="text-center mb-20">
            <h2 className="text-4xl sm:text-5xl font-bold mb-6">
              <span className="bg-gradient-to-r from-white via-emerald-50 to-emerald-100 bg-clip-text text-transparent">
                Tudo que você precisa saber
              </span>
            </h2>
            <p className="text-xl text-slate-500 max-w-2xl mx-auto">
              Acesse informações acadêmicas da UNIFESP Campus São José dos Campos de forma rápida e inteligente
            </p>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <div
                key={index}
                className="
                  group relative p-8 rounded-3xl
                  bg-emerald-500/[0.02] border border-emerald-500/10
                  backdrop-blur-xl
                  hover:bg-emerald-500/[0.05] hover:border-emerald-500/30
                  transition-all duration-500
                  hover:-translate-y-2
                "
              >
                {/* Icon */}
                <div className={`
                  w-14 h-14 rounded-2xl mb-6
                  bg-gradient-to-br ${feature.gradient}
                  flex items-center justify-center
                  group-hover:scale-110 transition-transform duration-300
                  shadow-lg shadow-emerald-500/20
                `}>
                  <feature.icon className="w-7 h-7 text-white" />
                </div>

                {/* Content */}
                <h3 className="text-xl font-bold mb-3 text-white group-hover:text-emerald-50">
                  {feature.title}
                </h3>
                <p className="text-slate-400 leading-relaxed group-hover:text-slate-300">
                  {feature.description}
                </p>

                {/* Hover Glow */}
                <div className="
                  absolute inset-0 rounded-3xl opacity-0 group-hover:opacity-100
                  bg-emerald-500
                  blur-3xl -z-10 transition-opacity duration-500
                " style={{ opacity: 0.08 }} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA SECTION ===== */}
      <section className="relative py-32 px-6">
        <div className="max-w-4xl mx-auto text-center">
          {/* Decorative Element */}
          <div className="relative inline-block mb-10">
            <div className="absolute inset-0 bg-emerald-500 rounded-full blur-3xl opacity-30 animate-pulse" />
            <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center border border-emerald-400/30">
              <GraduationCap className="w-12 h-12 text-white" />
            </div>
          </div>

          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-8">
            <span className="bg-gradient-to-r from-white via-emerald-100 to-emerald-200 bg-clip-text text-transparent">
              Pronto para começar?
            </span>
          </h2>

          <p className="text-xl text-slate-400 mb-12 max-w-2xl mx-auto">
            Faça perguntas sobre disciplinas, docentes, regimentos e muito mais.
            Nossa IA está pronta para ajudar.
          </p>

          <button
            onClick={() => router.push('/chat')}
            className="
              group relative px-12 py-6 rounded-2xl
              bg-gradient-to-r from-emerald-400 to-emerald-500 text-white font-bold text-xl
              overflow-hidden
              transition-all duration-500
              hover:scale-105
              hover:shadow-[0_0_80px_rgba(16,185,129,0.5)]
              active:scale-95
              border border-emerald-300/30
            "
          >
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
            <span className="relative flex items-center gap-3">
              <Brain className="w-6 h-6" />
              Iniciar Conversa
              <ArrowRight className="w-6 h-6 group-hover:translate-x-2 transition-transform duration-300" />
            </span>
          </button>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="relative py-10 px-6 border-t border-emerald-500/10">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center">
              <GraduationCap className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg text-emerald-50">FESP-AI</span>
          </div>
          
          <p className="text-sm text-slate-500">
            UNIFESP Campus São José dos Campos • Assistente Acadêmico Inteligente
          </p>
        </div>
      </footer>
    </div>
  )
}
