"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [scrolled, setScrolled] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="relative flex flex-col min-h-screen">
      {/* ─── Animated vertical light beams ─── */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        {/* Left beam — starts immediately */}
        <div className="animated-line" style={{ left: '15%', animationDelay: '0s' }} />
        {/* Center beam — starts after 4s */}
        <div className="animated-line" style={{ left: '45%', animationDelay: '4s' }} />
        {/* Right beam — starts after 8s */}
        <div className="animated-line" style={{ left: '75%', animationDelay: '8s' }} />
      </div>

      {/* Noise dots + glow — limited to hero/navbar region only */}
      <div
        className="absolute top-0 left-0 right-0 pointer-events-none"
        style={{
          height: "100vh",
          maskImage: "linear-gradient(to bottom, black 70%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to bottom, black 70%, transparent 100%)",
        }}
      >
        <div className="noise-bg" />
        <div className="hero-glow absolute inset-0" />
      </div>
      {/* Fixed header — full width invisible wrapper */}
      <header className="fixed top-0 left-0 right-0 z-50 flex justify-center items-start pt-4 px-4 pointer-events-none">
        {/* The pill — always visible, intensifies on scroll */}
        <nav
          className="pointer-events-auto w-full max-w-[820px] flex items-center justify-between px-5 py-3 transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
          style={{
            borderRadius: "9999px",
            background: !isDark
              ? scrolled
                ? "rgba(255, 255, 255, 0.82)"
                : "rgba(255, 255, 255, 0.55)"
              : scrolled
                ? "rgba(12, 12, 20, 0.82)"
                : "rgba(12, 12, 20, 0.45)",
            backdropFilter: scrolled
              ? "blur(24px) saturate(200%)"
              : "blur(12px) saturate(160%)",
            WebkitBackdropFilter: scrolled
              ? "blur(24px) saturate(200%)"
              : "blur(12px) saturate(160%)",
            border: !isDark
              ? scrolled
                ? "1px solid rgba(0, 0, 0, 0.10)"
                : "1px solid rgba(0, 0, 0, 0.06)"
              : scrolled
                ? "1px solid rgba(255, 255, 255, 0.12)"
                : "1px solid rgba(255, 255, 255, 0.07)",
            boxShadow: !isDark
              ? scrolled
                ? "0 8px 40px rgba(0, 0, 0, 0.12), 0 1px 0 rgba(255,255,255,0.9) inset"
                : "0 4px 20px rgba(0, 0, 0, 0.06), 0 1px 0 rgba(255,255,255,0.7) inset"
              : scrolled
                ? "0 8px 40px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(255,255,255,0.05) inset"
                : "0 4px 20px rgba(0, 0, 0, 0.3), 0 1px 0 rgba(255,255,255,0.04) inset",
          }}
        >
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2 font-bold text-base text-gray-900 dark:text-white"
          >
            <svg
              className="h-7 w-7"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              style={{ color: "oklch(0.62 0.22 275)" }}
            >
              <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5.5 4 7l3 3 3-3c2-1.5 4-4 4-7a7 7 0 0 0-7-7z" />
              <circle cx="12" cy="9" r="2" />
            </svg>
            <span>PersonalAPI</span>
          </Link>

          {/* Nav links — center */}
          <div className="hidden md:flex items-center gap-7">
            {["Features", "Integrations", "Pricing"].map((label) => (
              <a
                key={label}
                href={`#${label.toLowerCase()}`}
                className="text-sm font-medium text-gray-700 dark:text-white/75 hover:text-gray-950 dark:hover:text-white transition-colors duration-200"
              >
                {label}
              </a>
            ))}
          </div>

          {/* Right: theme toggle + auth */}
          <div className="flex items-center gap-2">
            {/* Theme toggle — single click, spin swap animation */}
            <button
              onClick={() => setTheme(isDark ? "light" : "dark")}
              className="p-2 rounded-full text-gray-600 dark:text-white/70 hover:text-gray-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/10 transition-all duration-200"
              aria-label="Toggle theme"
            >
              <span className="relative flex h-[18px] w-[18px] items-center justify-center">
                <Sun
                  size={16}
                  className="absolute transition-all duration-300 ease-in-out"
                  style={{
                    opacity: mounted && isDark ? 0 : 1,
                    transform:
                      mounted && isDark
                        ? "rotate(90deg) scale(0)"
                        : "rotate(0deg) scale(1)",
                  }}
                />
                <Moon
                  size={16}
                  className="absolute transition-all duration-300 ease-in-out"
                  style={{
                    opacity: mounted && isDark ? 1 : 0,
                    transform:
                      mounted && isDark
                        ? "rotate(0deg) scale(1)"
                        : "rotate(-90deg) scale(0)",
                  }}
                />
              </span>
            </button>

            {/* Log In */}
            <Link href="/?auth=login">
              <Button
                variant="ghost"
                size="sm"
                className="text-sm font-medium text-gray-700 dark:text-white/75 hover:text-gray-950 dark:hover:text-white rounded-full px-4"
              >
                Log In
              </Button>
            </Link>

            {/* Get Started */}
            <Link href="/?auth=signup">
              <Button
                size="sm"
                className="text-sm font-semibold rounded-full px-4 bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-white/90 transition-all duration-200"
              >
                Get Started
              </Button>
            </Link>
          </div>
        </nav>
      </header>

      {/* pt-24 accounts for pill height (60px) + top offset (16px) + breathing room */}
      <main className="flex-1 pt-24">{children}</main>

      <footer className="py-6 text-center border-t border-black/5 dark:border-white/5 text-sm text-muted-foreground">
        © 2026 PersonalAPI. All rights reserved.
      </footer>
    </div>
  );
}
