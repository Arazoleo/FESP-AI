'use client'

import { useEffect } from 'react'

/**
 * ScrollFX — orquestra os efeitos de scroll da landing sem converter a página
 * em client component. Tudo é ligado por data-attributes:
 *
 *   [data-reveal]          fade + translateY ao entrar no viewport (stagger via --fxd)
 *   [data-graph]           SVG do grafo: redesenha arestas / acende nós ao re-entrar
 *   [data-parallax="0.05"] translateY lento proporcional ao scroll
 *   [data-nav]             nav ganha fundo blur + borda ao rolar
 *
 * Com prefers-reduced-motion tudo permanece estático (o efeito nem é armado:
 * sem a classe `fx-ready` no <html>, o CSS não esconde nada).
 */
export default function ScrollFX() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const root = document.documentElement
    root.classList.add('fx-ready')

    // ── Reveal on scroll ──────────────────────────────────────────────
    const revealEls = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'))
    const revealObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('fx-in')
            revealObserver.unobserve(entry.target)
          }
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -48px 0px' }
    )
    revealEls.forEach((el) => revealObserver.observe(el))

    // ── Grafo: redesenho das arestas ao re-entrar no viewport ─────────
    const graph = document.querySelector<HTMLElement>('[data-graph]')
    let graphObserver: IntersectionObserver | undefined
    if (graph) {
      graphObserver = new IntersectionObserver(
        ([entry]) => {
          graph.classList.toggle('graph-live', entry.isIntersecting)
        },
        { threshold: 0.3 }
      )
      graphObserver.observe(graph)
    }

    // ── Scroll: barra de progresso, nav, parallax ─────────────────────
    const bar = document.querySelector<HTMLElement>('[data-scroll-progress]')
    const nav = document.querySelector<HTMLElement>('[data-nav]')
    const parallaxEls = Array.from(document.querySelectorAll<HTMLElement>('[data-parallax]'))
    let ticking = false

    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        ticking = false
        const y = window.scrollY
        const max = root.scrollHeight - window.innerHeight
        if (bar) bar.style.transform = `scaleX(${max > 0 ? Math.min(y / max, 1) : 0})`
        if (nav) nav.classList.toggle('nav-scrolled', y > 8)
        for (const el of parallaxEls) {
          const speed = parseFloat(el.dataset.parallax || '0.05')
          el.style.transform = `translateY(${(-y * speed).toFixed(1)}px)`
        }
      })
    }

    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })

    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      revealObserver.disconnect()
      graphObserver?.disconnect()
      root.classList.remove('fx-ready')
    }
  }, [])

  return <div data-scroll-progress className="scroll-progress" aria-hidden />
}
