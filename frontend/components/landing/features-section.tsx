"use client";

import { Search, MessageSquare, ShieldCheck, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useScrollReveal } from "@/hooks/use-scroll-reveal";
import { useTheme } from "next-themes";
import { IntegrationsCarousel } from "./integrations-carousel";

const features = [
  {
    icon: Search,
    badge: "Search",
    title: "Semantic Search",
    tagline: "Ask in plain English. Find everything.",
    description:
      "Stop hunting through tabs. Query all your connected apps at once using natural language — results are ranked by relevance, not recency.",
    bullets: [
      "Search Notion, Slack, Drive & Telegram simultaneously",
      "Results ranked by semantic relevance",
      "Filters by source, date, and data type",
    ],
    stat: { value: "10×", label: "faster than manual search" },
    accentColor: "99,102,241", // indigo
    preview: [
      { source: "NOTION", text: "Q4 Planning — Product Roadmap" },
      { source: "SLACK", text: "#product — roadmap discussion" },
      { source: "DRIVE", text: "Q4_Roadmap_Final.pdf" },
    ],
  },
  {
    icon: MessageSquare,
    badge: "AI Chat",
    title: "RAG AI Chat",
    tagline: "Your data. Your AI. Your answers.",
    description:
      "Chat with an AI that actually knows your context. Every answer is grounded in your real documents, messages, and notes — not hallucinations.",
    bullets: [
      "Cites sources for every answer",
      "Understands context across apps",
      "Ask follow-ups without repeating yourself",
    ],
    stat: { value: "100%", label: "grounded in your data" },
    accentColor: "139,92,246", // violet
    preview: [
      {
        role: "user",
        text: "What did we decide in last week's standup?",
      },
      {
        role: "assistant",
        text: "Based on your Slack #dev channel: deploy on Friday, Alex owns the PR review.",
      },
    ],
  },
  {
    icon: ShieldCheck,
    badge: "Privacy",
    title: "Private & Secure",
    tagline: "Your data never leaves your hands.",
    description:
      "Self-hosted by default. No SaaS middleman reads your Notion pages or Slack messages. You own the keys, the infra, and the data.",
    bullets: [
      "Self-hosted — runs on your own server",
      "End-to-end encrypted API calls",
      "Zero telemetry, zero data retention",
    ],
    stat: { value: "0", label: "data sent to third parties" },
    accentColor: "34,197,94", // green
    preview: [
      { label: "SHA-256 encryption", done: true },
      { label: "OAuth 2.0 auth", done: true },
      { label: "Local LLM support", done: true },
      { label: "Audit logs", done: true },
    ],
  },
];

export function FeaturesSection() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const ref1 = useScrollReveal();
  const ref2 = useScrollReveal();
  const ref3 = useScrollReveal();
  const calloutRef = useScrollReveal();

  const refs = [ref1, ref2, ref3];

  return (
    <section
      id="features"
      className="py-24 sm:py-32 relative"
      style={{
        background: isDark
          ? "transparent"
          : "linear-gradient(135deg, rgba(99,102,241,0.04) 0%, rgba(168,85,247,0.04) 100%)",
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] mb-3 text-primary">
            CAPABILITIES
          </p>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3 text-foreground">
            Everything in one place
          </h2>
          <p className="text-lg text-muted-foreground">
            One brain to rule them all.
          </p>
        </div>

        {/* Feature cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {features.map((feature, i) => (
            <div
              key={feature.title}
              ref={refs[i]}
              className="reveal relative overflow-hidden rounded-[20px] transition-all duration-300 hover:scale-[1.01] hover:-translate-y-1 group flex flex-col dark:bg-[#0a0a0a] bg-white border dark:border-[#222] border-gray-200"
              style={{ transitionDelay: `${i * 120}ms` }}
            >
              {/* ── HEADER (like the reference's small uppercase label) ── */}
              <div className="p-6 pb-4">
                <div className="text-[11px] font-bold uppercase tracking-[0.15em] dark:text-gray-500 text-gray-400 mb-6 font-mono">
                  {feature.badge}
                </div>

                <div className="flex items-center gap-3 mb-2">
                  <feature.icon className="h-5 w-5 dark:text-gray-200 text-gray-800" />
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                    {feature.title}
                  </h3>
                </div>

                <p className="text-sm font-medium dark:text-gray-300 text-gray-700 mb-3">
                  {feature.tagline}
                </p>
                <p className="text-[13px] leading-relaxed text-gray-600 dark:text-gray-500 mb-4">
                  {feature.description}
                </p>

                {/* ── BULLET POINTS ── */}
                <div className="flex flex-col gap-2.5">
                  {feature.bullets.map((bullet) => (
                    <div key={bullet} className="flex items-start gap-2.5">
                      <div className="mt-1.5 h-1.5 w-1.5 rounded-full dark:bg-[#555] bg-gray-300 shrink-0" />
                      <span className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                        {bullet}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── MINI PREVIEW ── styled like the reference UI ── */}
              <div className="feature-preview px-6 pb-4 flex-1 flex flex-col justify-end mt-2">
                {/* Card 0 — Search results (looks like Integrations list in ref) */}
                {i === 0 && (
                  <div className="flex flex-col gap-2.5">
                    {(feature.preview as { source: string; text: string }[]).map((row) => (
                      <div
                        key={row.source}
                        className="flex items-center justify-between p-3.5 rounded-xl dark:bg-[#141414] bg-gray-50 border dark:border-[#222] border-gray-200 transition-colors hover:dark:bg-[#1a1a1a]"
                      >
                        <div className="flex items-center gap-3 overflow-hidden">
                          <span className="text-[9px] font-bold tracking-widest px-2 py-1 rounded dark:bg-[#2a2a2a] bg-gray-200 dark:text-gray-300 text-gray-700 shrink-0">
                            {row.source}
                          </span>
                          <span className="text-[13px] font-medium dark:text-gray-300 text-gray-800 truncate">
                            {row.text}
                          </span>
                        </div>
                        <ChevronRight className="w-4 h-4 dark:text-gray-600 text-gray-400 shrink-0 ml-2" />
                      </div>
                    ))}
                  </div>
                )}

                {/* Card 1 — Chat bubbles */}
                {i === 1 && (
                  <div className="flex flex-col gap-3">
                    {(feature.preview as { role: string; text: string }[]).map((msg, mi) => (
                      <div
                        key={mi}
                        className={`text-[12px] leading-relaxed rounded-xl px-4 py-3 max-w-[90%] ${msg.role === "user"
                            ? "self-end dark:bg-[#1e1e1e] bg-gray-100 dark:text-gray-200 text-gray-800 border dark:border-[#2a2a2a] border-gray-200"
                            : "self-start dark:bg-[#141414] bg-gray-50 dark:text-gray-400 text-gray-600 border dark:border-[#222] border-gray-200"
                          }`}
                      >
                        {msg.text}
                      </div>
                    ))}
                  </div>
                )}

                {/* Card 2 — Security checklist (styled with lime green icon like the Approve button in ref) */}
                {i === 2 && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-auto">
                    {(feature.preview as { label: string; done: boolean }[]).map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center gap-2.5 p-3 rounded-xl dark:bg-[#141414] bg-gray-50 border dark:border-[#222] border-gray-200"
                      >
                        <div className="flex items-center justify-center w-5 h-5 rounded-md bg-lime-400 shrink-0">
                          <svg
                            className="w-3.5 h-3.5 text-black"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={3}
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                        <span className="text-[11px] font-medium dark:text-gray-300 text-gray-800 truncate">
                          {item.label}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* ── FOOTER STAT ── */}
              <div className="pb-6 pt-5 mt-auto flex items-baseline justify-between gap-2 border-t dark:border-[#222] border-gray-200 mx-6">
                <span className="text-[11px] uppercase tracking-widest dark:text-gray-500 text-gray-400 font-bold whitespace-nowrap">
                  {feature.stat.label}
                </span>
                <span className="text-2xl font-light tracking-tight dark:text-white text-gray-900">
                  {feature.stat.value}
                </span>
              </div>
            </div>
          ))}
        </div>

      </div>

      {/* Seamless Integrations Ticker */}
      <div className="w-full mt-16 sm:mt-24">
        <IntegrationsCarousel />
      </div>
    </section>
  );
}
