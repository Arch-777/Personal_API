"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { HeroSection } from "@/components/landing/hero-section";
import { FeaturesSection } from "@/components/landing/features-section";
import { PricingSection } from "@/components/landing/pricing-section";
import { Footer } from "@/components/landing/footer";
import { AuthModal } from "@/components/landing/auth-modal";
import { Separator } from "@/components/ui/separator";

function LandingPageContent() {
  const searchParams = useSearchParams();
  const authParam = searchParams.get("auth");
  const showLogin = authParam === "login";
  const showSignup = authParam === "signup";

  return (
    <>
      <HeroSection />
      <Separator className="opacity-10" />
      <FeaturesSection />
      <Separator className="opacity-10" />
      <PricingSection />
      <Footer />

      {/* Auth modals */}
      <AuthModal
        type="login"
        open={showLogin}
        onOpenChange={(v) => {
          if (!v) window.history.replaceState(null, "", "/");
        }}
      />
      <AuthModal
        type="signup"
        open={showSignup}
        onOpenChange={(v) => {
          if (!v) window.history.replaceState(null, "", "/");
        }}
      />
    </>
  );
}

export default function LandingPage() {
  return (
    <Suspense>
      <LandingPageContent />
    </Suspense>
  );
}
