"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ModeToggle } from "@/components/mode-toggle";

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "Integrations", href: "#integrations" },
  { label: "Pricing", href: "#pricing" },
];

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="flex flex-col min-h-screen relative">
      <div className="noise-bg" />
      {/* Sticky navbar */}
      <header
        className={`sticky top-0 z-50 border-b border-border/40 backdrop-blur-md transition-all duration-300 ${
          scrolled
            ? "bg-background/90 shadow-lg shadow-black/5 dark:shadow-black/20"
            : "bg-background/60"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
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
            <span className="text-lg font-bold">PersonalAPI</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-sm font-medium transition-colors text-muted-foreground hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Desktop auth & theme */}
          <div className="hidden md:flex items-center gap-3">
            <ModeToggle />
            <Link href="/?auth=login">
              <Button
                variant="ghost"
                className="hover:bg-white/5 cursor-pointer"
              >
                Log In
              </Button>
            </Link>
            <Link href="/?auth=signup">
              <Button
                className="bg-foreground text-background hover:bg-foreground/90 cursor-pointer"
              >
                Get Started
              </Button>
            </Link>
          </div>

          {/* Mobile hamburger */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger className="md:hidden p-2 rounded-md hover:bg-white/5 transition-colors">
              <Menu className="h-5 w-5" />
            </SheetTrigger>
            <SheetContent side="right">
              <SheetHeader>
                <SheetTitle>
                  Menu
                </SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-4 p-4">
                {navLinks.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className="text-base font-medium py-2 transition-colors text-muted-foreground hover:text-foreground"
                  >
                    {link.label}
                  </a>
                ))}
                <div className="border-t border-border/40 pt-4 flex flex-col gap-3">
                  <div className="flex justify-between items-center py-2">
                    <span className="text-sm font-medium text-muted-foreground">Theme</span>
                    <ModeToggle />
                  </div>
                  <Link
                    href="/?auth=login"
                    onClick={() => setMobileOpen(false)}
                  >
                    <Button
                      variant="ghost"
                      className="w-full hover:bg-white/5 cursor-pointer"
                    >
                      Log In
                    </Button>
                  </Link>
                  <Link
                    href="/?auth=signup"
                    onClick={() => setMobileOpen(false)}
                  >
                    <Button className="w-full bg-foreground text-background hover:bg-foreground/90 cursor-pointer">
                      Get Started
                    </Button>
                  </Link>
                </div>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <main className="flex-1">{children}</main>
    </div>
  );
}
