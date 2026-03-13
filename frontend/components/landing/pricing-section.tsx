"use client";

import { Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { useScrollReveal } from "@/hooks/use-scroll-reveal";
import Link from "next/link";

const plans = [
  {
    name: "Free",
    badge: "Free Forever",
    badgeVariant: "outline" as const,
    price: "$0",
    period: "/mo",
    features: [
      "2 integrations",
      "1,000 searches/mo",
      "Community support",
    ],
    cta: "Get Started",
    ctaVariant: "outline" as const,
    featured: false,
  },
  {
    name: "Pro",
    badge: "Most Popular",
    badgeVariant: "default" as const,
    price: "$12",
    period: "/mo",
    features: [
      "Unlimited integrations",
      "Unlimited searches",
      "RAG AI Chat",
      "Priority support",
    ],
    cta: "Get Started",
    ctaVariant: "default" as const,
    featured: true,
  },
  {
    name: "Enterprise",
    badge: "Enterprise",
    badgeVariant: "outline" as const,
    price: "Custom",
    period: "",
    features: [
      "Self-hosted deployment",
      "SSO",
      "SLA",
      "Dedicated support",
    ],
    cta: "Contact Us",
    ctaVariant: "outline" as const,
    featured: false,
  },
];

export function PricingSection() {
  const ref1 = useScrollReveal();
  const ref2 = useScrollReveal();
  const ref3 = useScrollReveal();
  const refs = [ref1, ref2, ref3];

  return (
    <section id="pricing" className="py-24 sm:py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-16">
          <p
            className="text-xs font-semibold uppercase tracking-[0.2em] mb-3 text-primary"
          >
            PRICING
          </p>
          <h2
            className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3 text-foreground"
          >
            Simple, transparent pricing
          </h2>
          <p className="text-lg text-muted-foreground">
            Start free. Scale when you&apos;re ready.
          </p>
        </div>

        {/* Pricing cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto items-start">
          {plans.map((plan, i) => (
            <div
              key={plan.name}
              ref={refs[i]}
              className="reveal"
              style={{ transitionDelay: `${i * 100}ms` }}
            >
              <Card
                className={`bg-transparent border-white/10 ${
                  plan.featured
                    ? "scale-[1.02] border-[oklch(0.62_0.22_275)]/50 relative"
                    : ""
                }`}
                style={
                  plan.featured
                    ? {
                        boxShadow:
                          "0 0 40px oklch(0.62 0.22 275 / 0.25)",
                      }
                    : undefined
                }
              >
                <CardHeader>
                  <div className="mb-2">
                    <Badge
                      variant={plan.badgeVariant}
                      className={
                        plan.featured
                          ? "bg-primary text-primary-foreground border-transparent"
                          : "text-muted-foreground"
                      }
                    >
                      {plan.badge}
                    </Badge>
                  </div>
                  <CardTitle>
                    <span
                      className="text-4xl font-extrabold tracking-tight text-foreground"
                    >
                      {plan.price}
                    </span>
                    {plan.period && (
                      <span
                        className="text-lg font-normal ml-1 text-muted-foreground"
                      >
                        {plan.period}
                      </span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-center gap-3">
                        <Check
                          className="h-4 w-4 shrink-0 text-primary"
                        />
                        <span className="text-muted-foreground">
                          {feature}
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter className="bg-transparent border-t-0 p-4">
                  <Link href={plan.name === "Enterprise" ? "#" : "/?auth=signup"} className="w-full">
                    <Button
                      variant={plan.ctaVariant}
                      className={`w-full cursor-pointer ${
                        plan.featured
                          ? "bg-[oklch(0.62_0.22_275)] hover:bg-[oklch(0.55_0.18_290)] text-white"
                          : "border-white/20 hover:bg-white/5"
                      }`}
                    >
                      {plan.cta}
                    </Button>
                  </Link>
                </CardFooter>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
