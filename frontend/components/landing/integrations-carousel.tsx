'use client'

import { useTheme } from 'next-themes'
import { useScrollReveal } from '@/hooks/use-scroll-reveal'

// Plain names — NO emoji prefix, NO ✦
const tickerItems = [
  'NOTION', 'SLACK', 'GMAIL', 'GOOGLE DRIVE', 'GITHUB',
  'TELEGRAM', 'DISCORD', 'SPOTIFY', 'GOOGLE DOCS',
  'GOOGLE CALENDAR', 'GOOGLE SHEETS', 'LINEAR',
]

export function IntegrationsCarousel() {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === 'dark'

  return (
    <>
      {/* ── Single solid ticker band ── */}
      <div
        className="w-full overflow-hidden"
        style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          // Pure near-black — matches Image 2 exactly
          background: '#0c0c0f',
        }}
      >
        <div
          className="flex w-max py-[14px] animate-marquee"
        >
          {/* 3× copies for seamless -33.333% loop */}
          {[...tickerItems, ...tickerItems, ...tickerItems].map((item, i) => (
            <span key={i} className="flex items-center">
              <span
                className="text-[13px] font-bold uppercase whitespace-nowrap"
                style={{
                  letterSpacing: '0.14em',
                  color: 'rgba(255,255,255,0.95)',
                  padding: '0 28px',
                }}
              >
                {item}
              </span>
              <span
                style={{
                  color: 'rgba(255,255,255,0.50)',
                  fontSize: '14px',
                  lineHeight: 1,
                }}
              >
                ★
              </span>
            </span>
          ))}
        </div>
      </div>
    </>
  )
}
