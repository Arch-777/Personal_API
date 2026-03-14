'use client'

import { useScrollReveal } from '@/hooks/use-scroll-reveal'
import { Check } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'

const meters = [
  'Tokens processed',
  'Search queries',
  'Connector sync jobs',
  'Storage GB',
]

export function PricingSection() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])
  
  const ref1 = useScrollReveal()
  if (!mounted) return null // Or a skeleton/placeholder to prevent hydration mismatch entirely

  return (
    <section id="pricing" className="relative py-24 sm:py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* ── Section header ── */}
        <div className="text-center mb-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] mb-3 text-primary">
            PRICING
          </p>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3 text-foreground">
            Pay-as-you-go metered billing
          </h2>
          <p className="text-lg text-muted-foreground">
            Bill only usage each month with no plan lock-in.
          </p>
        </div>

        <div ref={ref1} className="reveal max-w-3xl mx-auto">
          <div className="relative rounded-[24px] overflow-hidden border dark:border-[#222] border-gray-200 dark:bg-[#0a0a0a] bg-white p-8 sm:p-10 shadow-xl">
            <p className="text-xs font-bold uppercase tracking-[0.15em] dark:text-gray-500 text-gray-500 mb-4">
              Usage-based model
            </p>

            <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight dark:text-white text-gray-900 mb-3">
              Pay-as-you-go metered billing
            </h3>

            <p className="text-base sm:text-lg text-gray-600 dark:text-gray-300 mb-6">
              Bill only usage each month with no plan lock-in.
            </p>

            <div className="rounded-xl dark:bg-white/5 bg-gray-50 p-5 mb-6">
              <p className="text-sm font-semibold dark:text-white text-gray-900 mb-3">
                Meter on:
              </p>
              <ul className="space-y-2">
                {meters.map((meter) => (
                  <li key={meter} className="flex items-center gap-2.5 text-sm dark:text-gray-300 text-gray-700">
                    <span className="h-5 w-5 rounded-full dark:bg-white/15 bg-black/10 inline-flex items-center justify-center">
                      <Check size={12} strokeWidth={3} className="dark:text-white text-black" />
                    </span>
                    {meter}
                  </li>
                ))}
              </ul>
            </div>

            <p className="text-sm sm:text-base dark:text-gray-300 text-gray-700 mb-6">
              Why it fits: easiest &ldquo;fair pricing&rdquo; story vs competitors.
            </p>

            <Link href="/?auth=signup" className="inline-block">
              <button className="py-3 px-6 rounded-xl text-sm font-bold tracking-wide transition-all duration-200 hover:-translate-y-0.5 dark:bg-white bg-black dark:text-black text-white hover:opacity-90">
                Start With Usage Billing
              </button>
            </Link>
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-10">
          Metered usage includes SSL, automatic backups, and GDPR compliance.
        </p>
      </div>
    </section>
  )
}