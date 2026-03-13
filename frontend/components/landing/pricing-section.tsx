'use client'

import { Check, X, Infinity as InfinityIcon, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useScrollReveal } from '@/hooks/use-scroll-reveal'
import { useTheme } from 'next-themes'
import Link from 'next/link'
import { useState, useEffect } from 'react'

const plans = [
  {
    name: 'Free',
    badge: 'Free Forever',
    badgeVariant: 'outline' as const,
    price: '$0',
    period: '/mo',
    tagline: 'Perfect for personal use',
    accentColor: '148,163,184',        // slate
    featured: false,
    cta: 'Get Started Free',
    ctaHref: '/?auth=signup',

    // What's included
    features: [
      { text: '2 integrations (Notion + 1 more)',   available: true },
      { text: '1,000 semantic searches / month',    available: true },
      { text: 'Basic RAG AI Chat (10 msgs/day)',    available: true },
      { text: 'Community Discord support',          available: true },
      { text: '7-day search history',               available: true },
      { text: 'Priority processing',                available: false },
      { text: 'Self-hosted deployment',             available: false },
    ],

    // Usage stats shown as mini meter bars
    stats: [
      { label: 'Integrations',  used: 2,    max: 2,    unit: '' },
      { label: 'Searches',      used: 1000, max: 1000, unit: '/mo' },
    ],
  },
  {
    name: 'Pro',
    badge: 'Most Popular',
    badgeVariant: 'default' as const,
    price: '$12',
    period: '/mo',
    tagline: 'For power users & small teams',
    accentColor: '99,102,241',         // indigo
    featured: true,
    cta: 'Start Pro Free',
    ctaHref: '/?auth=signup',

    features: [
      { text: 'Unlimited integrations',             available: true },
      { text: 'Unlimited semantic searches',        available: true },
      { text: 'Unlimited RAG AI Chat',              available: true },
      { text: 'Priority email support',             available: true },
      { text: 'Full search history',                available: true },
      { text: 'Priority processing',                available: true },
      { text: 'API access (1,000 calls/mo)',        available: true },
    ],

    stats: [
      { label: 'Integrations', used: Infinity, max: Infinity, unit: '' },
      { label: 'Searches',     used: Infinity, max: Infinity, unit: '/mo' },
    ],

    highlight: '14-day free trial · No credit card needed',
  },
  {
    name: 'Enterprise',
    badge: 'Self-Hosted',
    badgeVariant: 'outline' as const,
    price: 'Custom',
    period: '',
    tagline: 'Full control for your organisation',
    accentColor: '34,197,94',          // green
    featured: false,
    cta: 'Talk to Sales',
    ctaHref: 'mailto:hello@personalapi.dev',

    features: [
      { text: 'Self-hosted on your infra',          available: true },
      { text: 'Unlimited everything',               available: true },
      { text: 'Local LLM support (Ollama / vLLM)',  available: true },
      { text: 'SSO / SAML 2.0',                     available: true },
      { text: 'Audit logs & compliance',            available: true },
      { text: 'Dedicated Slack channel',            available: true },
      { text: 'Custom SLA & uptime guarantee',      available: true },
    ],

    stats: [],

    highlight: 'Starting at $299 / month',
  },
]

export function PricingSection() {
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  
  useEffect(() => {
    setMounted(true)
  }, [])
  
  const isDark = mounted ? resolvedTheme === 'dark' : true // Default to dark on server
  
  const ref1 = useScrollReveal()
  const ref2 = useScrollReveal()
  const ref3 = useScrollReveal()
  const refs = [ref1, ref2, ref3]

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
            Simple, transparent pricing
          </h2>
          <p className="text-lg text-muted-foreground">
            Start free. Scale when you're ready.
          </p>
        </div>

        {/* ── Cards grid ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-5xl mx-auto items-stretch">
          {plans.map((plan, i) => (
            <div
              key={plan.name}
              ref={refs[i]}
              className="reveal flex flex-col"
              style={{ transitionDelay: `${i * 120}ms` }}
            >
              <div
                className={`relative flex flex-col h-full rounded-[20px] overflow-hidden transition-all duration-300 hover:scale-[1.01] hover:-translate-y-1 group dark:bg-[#0a0a0a] bg-white border dark:border-[#222] border-gray-200 ${plan.featured ? 'ring-1 dark:ring-white/20 ring-black/20 z-10 shadow-xl' : ''}`}
              >

                {/* ── Card Header ── */}
                <div className="relative p-6 pb-4">

                  {/* Badge row */}
                  <div className="flex items-center justify-between mb-5">
                    <span className="text-[11px] font-bold uppercase tracking-[0.15em] dark:text-gray-500 text-gray-400 font-mono">
                      {plan.badge}
                    </span>
                    {plan.featured && (
                      <span className="flex items-center gap-1 text-[10px] font-semibold dark:text-gray-300 text-gray-600">
                        <Zap size={10} fill="currentColor" />
                        RECOMMENDED
                      </span>
                    )}
                  </div>

                  {/* Plan name */}
                  <p className="text-sm font-semibold text-gray-500 dark:text-white/40 mb-1">
                    {plan.name}
                  </p>

                  {/* Price */}
                  <div className="flex items-end gap-1 mb-1">
                    <span className="text-5xl font-black tracking-tight dark:text-white text-gray-900">
                      {plan.price}
                    </span>
                    {plan.period && (
                      <span className="text-sm text-gray-400 dark:text-white/35 mb-2">
                        {plan.period}
                      </span>
                    )}
                  </div>

                  {/* Tagline */}
                  <p className="text-xs text-gray-500 dark:text-white/40 mb-4">
                    {plan.tagline}
                  </p>

                  {/* Highlight text (Pro trial / Enterprise starting price) */}
                  {'highlight' in plan && plan.highlight && (
                    <div className="text-[11px] font-semibold px-3 py-1.5 rounded-lg mb-2 text-center dark:bg-white/10 bg-black/5 dark:text-gray-300 text-gray-700">
                      {plan.highlight}
                    </div>
                  )}

                  {/* Divider */}
                  <div className="h-px mt-4 dark:bg-[#222] bg-gray-200" />
                </div>

                {/* ── Feature list ── */}
                <div className="relative px-6 pb-4 flex-1">
                  <ul className="space-y-2.5">
                    {plan.features.map((f) => (
                      <li key={f.text} className="flex items-start gap-3">
                        {f.available ? (
                          <div className="mt-0.5 h-4 w-4 rounded-full flex items-center justify-center shrink-0 dark:bg-white/15 bg-black/10">
                            <Check
                              size={10}
                              strokeWidth={3}
                              className="dark:text-white text-black"
                            />
                          </div>
                        ) : (
                          <div className="mt-0.5 h-4 w-4 rounded-full flex items-center justify-center shrink-0 bg-black/5 dark:bg-white/5">
                            <X size={10} strokeWidth={3} className="text-gray-400 dark:text-white/20" />
                          </div>
                        )}
                        <span
                          className={`text-[13px] leading-snug ${
                            f.available
                              ? 'text-gray-700 dark:text-white/70'
                              : 'text-gray-400 dark:text-white/25 line-through'
                          }`}
                        >
                          {f.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* ── CTA Button ── */}
                <div className="relative p-6 pt-4">
                  {/* Divider above CTA */}
                  <div className="h-px mb-4 dark:bg-[#222] bg-gray-200" />

                  <Link href={plan.ctaHref} className="block w-full">
                    <button
                      className={`w-full py-3 px-4 rounded-xl text-sm font-bold tracking-wide transition-all duration-200 hover:-translate-y-0.5 ${
                        plan.featured 
                          ? 'dark:bg-white bg-black dark:text-black text-white hover:opacity-90' 
                          : 'dark:bg-[#141414] bg-gray-50 dark:text-gray-300 text-gray-700 border dark:border-[#222] border-gray-200 hover:dark:bg-[#1a1a1a]'
                      }`}
                    >
                      {plan.cta}
                    </button>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* ── Bottom trust line ── */}
        <p className="text-center text-xs text-muted-foreground mt-10">
          All plans include SSL, automatic backups, and GDPR compliance.
        </p>
      </div>
    </section>
  )
}
