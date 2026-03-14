"use client";

import Link from "next/link";
import { Github, Twitter, Linkedin, Mail } from "lucide-react";
import { useTheme } from "next-themes";
import { useState, useEffect } from "react";
import Image from 'next/image'


const footerLinks = {
  PRODUCT: [
    { label: "Features", href: "#features" },
    { label: "Integrations", href: "#integrations" },
    { label: "Pricing", href: "#pricing" },
    { label: "Changelog", href: "#" },
  ],
  COMPANY: [
    { label: "About Us", href: "#" },
    { label: "Blog", href: "#" },
    { label: "Careers", href: "#" },
    { label: "Contact", href: "#" },
  ],
  RESOURCES: [
    {
      label: "Documentation",
      href: "https://github.com/Arch-777/MEGAHACK-2026_Const_Coders/blob/main/README.md",
      external: true,
    },
    { label: "GitHub", href: "https://github.com", external: true },
    { label: "Security & Privacy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
  ],
};

const socialLinks = [
  { icon: Github, href: "https://github.com", label: "GitHub" },
  { icon: Twitter, href: "https://twitter.com", label: "Twitter" },
  { icon: Linkedin, href: "https://linkedin.com", label: "LinkedIn" },
  { icon: Mail, href: "mailto:hello@personalapi.tech", label: "Email" },
];

export function Footer() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted ? resolvedTheme === "dark" : true;

  // Light mode color fallback variables
  const mutedColor = isDark ? "rgba(255,255,255,0.28)" : "rgba(0,0,0,0.35)";
  const subtleColor = isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.50)";
  const hoverColor = isDark ? "rgba(255,255,255,0.85)" : "rgba(0,0,0,0.85)";
  const borderColor = isDark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.08)";
  const iconBg = isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)";
  const iconHoverBg = isDark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.08)";
  const dividerColor = isDark
    ? "linear-gradient(to right, transparent, rgba(255,255,255,0.10), transparent)"
    : "linear-gradient(to right, transparent, rgba(0,0,0,0.10), transparent)";

  if (!mounted) return null;

  return (
    <footer className="relative pt-16 pb-10">
      {/* Top separator */}
      <div className="max-w-6xl mx-auto px-6 mb-14">
        <div className="h-px" style={{ background: dividerColor }} />
      </div>

      {/* Main grid */}
      <div className="max-w-6xl mx-auto px-6 mb-14">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10 md:gap-6">
          {/* ── Col 1: Brand ── */}
          <div className="col-span-2 md:col-span-1">
            {/* Logo */}
            <div className="flex items-center gap-2 mb-3">
              <svg
                className="h-6 w-6 shrink-0"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                style={{ color: "oklch(0.62 0.22 275)" }}
              >
                <path d="M12 2a7 7 0 0 0-7 7c0 3 2 5.5 4 7l3 3 3-3c2-1.5 4-4 4-7a7 7 0 0 0-7-7z" />
                <circle cx="12" cy="9" r="2" />
              </svg>
              <span className="text-base font-bold text-foreground">
                PersonalAPI
              </span>
            </div>

            {/* Italic tagline — matches "Bridge of your digital world" style */}
            <p
              className="text-sm italic mb-3 leading-snug"
              style={{ color: subtleColor }}
            >
              Your Personal
              <br />
              Digital Brain.
            </p>

            {/* Short description */}
            <p
              className="text-xs leading-relaxed max-w-[190px]"
              style={{ color: mutedColor }}
            >
              Connect Notion, Slack, Drive &amp; Telegram into one searchable,
              AI-powered knowledge base.
            </p>
          </div>

          {/* ── Cols 2–4: Link columns ── */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h4
                className="text-[10px] font-semibold uppercase mb-5"
                style={{
                  letterSpacing: "0.15em",
                  color: mutedColor,
                }}
              >
                {category}
              </h4>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      target={
                        "external" in link && link.external
                          ? "_blank"
                          : undefined
                      }
                      rel={
                        "external" in link && link.external
                          ? "noopener noreferrer"
                          : undefined
                      }
                      className="text-sm transition-colors duration-150"
                      style={{ color: subtleColor }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.color = hoverColor)
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.color = subtleColor)
                      }
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* ── Col 5: Send Feedback (no heading) ── */}
          <div className="flex flex-col">
            <div className="mt-0 md:mt-[28px]">
              {/* Spacer to align with link columns that have a heading */}
              <Link
                href="mailto:feedback@personalapi.dev"
                className="text-sm transition-colors duration-150"
                style={{ color: subtleColor }}
                onMouseEnter={(e) => (e.currentTarget.style.color = hoverColor)}
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = subtleColor)
                }
              >
                Send Feedback
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom separator */}
      <div className="max-w-6xl mx-auto px-6 mb-8">
        <div className="h-px" style={{ background: dividerColor }} />
      </div>

      {/* Bottom bar: copyright | social icons | legal */}
      <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-5">
        {/* Copyright */}
        <p className="text-xs order-2 sm:order-1" style={{ color: mutedColor }}>
          © 2026 PersonalAPI, Inc. All rights reserved.
        </p>

        {/* Social icon buttons — center */}
        <div className="flex items-center gap-2 order-1 sm:order-2">
          {socialLinks.map(({ icon: Icon, href, label }) => (
            <Link
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              className="flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-150"
              style={{
                border: `1px solid ${borderColor}`,
                background: iconBg,
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLElement;
                el.style.background = iconHoverBg;
                el.style.borderColor = isDark
                  ? "rgba(255,255,255,0.18)"
                  : "rgba(0,0,0,0.18)";
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLElement;
                el.style.background = iconBg;
                el.style.borderColor = borderColor;
              }}
            >
              <Icon size={14} style={{ color: subtleColor }} />
            </Link>
          ))}
        </div>

        {/* Legal links */}
        <div className="flex items-center gap-5 order-3">
          {["Privacy Policy", "Terms of Service"].map((label) => (
            <Link
              key={label}
              href="#"
              className="text-xs transition-colors duration-150"
              style={{ color: mutedColor }}
              onMouseEnter={(e) => (e.currentTarget.style.color = subtleColor)}
              onMouseLeave={(e) => (e.currentTarget.style.color = mutedColor)}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </footer>
  );
}
