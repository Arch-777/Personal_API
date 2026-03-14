"use client";

import { ChevronDown } from "lucide-react";
import Link from "next/link";

export function HeroSection() {
  return (
    <section className="relative min-h-[90vh] flex items-center overflow-hidden">
      {/* noise-bg and hero-glow are now rendered at the layout level */}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full py-24">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Text content */}
          <div className="flex flex-col gap-6 text-center lg:text-left">
            {/* Announcement Badge */}
            <div
              className="animate-slide-up opacity-0"
              style={{ animationDelay: "0ms" }}
            >
              <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-4 py-1.5 text-sm font-medium">
                <span className="animate-shimmer inline-block h-1.5 w-1.5 rounded-full bg-[oklch(0.62_0.22_275)]" />
                Now in Beta — Connect your digital world →
              </span>
            </div>

            {/* Headline */}
            <h1
              className="animate-slide-up opacity-0 text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1]"
              style={{ animationDelay: "100ms" }}
            >
              Your Personal
              <br />
              <span className="text-foreground">
                Digital Brain, Unified.
              </span>
            </h1>

            {/* Subheadline */}
            <p
              className="animate-slide-up opacity-0 text-lg sm:text-xl leading-relaxed max-w-xl mx-auto lg:mx-0 text-muted-foreground"
              style={{ animationDelay: "200ms" }}
            >
              Connect Notion, Slack, Telegram, and Google Drive into one
              searchable, AI-powered knowledge base.
            </p>

            {/* CTA Buttons */}
            <div
              className="animate-slide-up opacity-0 flex flex-wrap gap-4 justify-center lg:justify-start"
              style={{ animationDelay: "300ms" }}
            >
              <Link 
                href="/?auth=signup"
                className="inline-flex h-9 items-center justify-center rounded-lg px-8 py-5 text-sm font-medium transition-colors bg-foreground text-background hover:bg-foreground/90 shadow-lg shadow-foreground/10 cursor-pointer"
              >
                  Get Started
              </Link>
            </div>
          </div>

          {/* Visual Card — CSS-only terminal mock */}
          <div
            className="animate-slide-up opacity-0"
            style={{ animationDelay: "400ms" }}
          >
            <div
              className="animate-float relative rounded-xl border border-black/10 dark:border-white/10 bg-card p-6 max-w-md mx-auto lg:ml-auto"
              style={{
                boxShadow:
                  "0 0 60px oklch(0.62 0.22 275 / 0.15), 0 25px 50px -12px rgba(0, 0, 0, 0.5)",
              }}
            >
              {/* Terminal header */}
              <div className="flex items-center gap-2 mb-4">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
                <span
                  className="ml-3 text-xs font-mono text-muted-foreground"
                >
                  PersonalAPI — Search
                </span>
              </div>

              {/* Fake search input */}
              <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 mb-4 flex items-center gap-2">
                <svg
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
                <span
                  className="text-sm font-mono text-muted-foreground"
                >
                  What was discussed about the Q4 roadmap?
                </span>
              </div>

              {/* Fake result rows */}
              <div className="space-y-3">
                {[
                  {
                    source: "Notion",
                    label: "Q4 Planning — Product Roadmap",
                    color: "oklch(0.62 0.22 275)",
                  },
                  {
                    source: "Slack",
                    label: "#product — roadmap discussion thread",
                    color: "oklch(0.55 0.18 290)",
                  },
                  {
                    source: "Drive",
                    label: "Q4_Roadmap_Final.pdf",
                    color: "oklch(0.65 0.20 150)",
                  },
                  {
                    source: "Telegram",
                    label: "Team chat — roadmap priorities",
                    color: "oklch(0.70 0.15 60)",
                  },
                ].map((item) => (
                  <div
                    key={item.source}
                    className="flex items-center gap-3 rounded-lg bg-white/3 p-3 border-l-2"
                    style={{ borderLeftColor: item.color }}
                  >
                    <div>
                      <span
                        className="text-[10px] font-mono uppercase tracking-wider"
                        style={{ color: item.color }}
                      >
                        {item.source}
                      </span>
                      <p className="text-sm text-foreground/80 mt-0.5">
                        {item.label}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <div
          className="animate-slide-up opacity-0 flex justify-center mt-16"
          style={{ animationDelay: "800ms" }}
        >
          <ChevronDown
            className="animate-bounce-down h-6 w-6 text-muted-foreground"
          />
        </div>
      </div>
    </section>
  );
}
