"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useLogin, useSignup } from "@/hooks/use-auth";
import { apiClient } from '@/lib/api-client';
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

function GoogleIcon() {
  return (
    <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function PasswordStrength({ password }: { password: string }) {
  const getStrength = () => {
    if (!password) return 0;
    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    return Math.min(score, 4);
  };

  const strength = getStrength();
  const colors = [
    "bg-red-500",
    "bg-orange-500",
    "bg-yellow-500",
    "bg-green-400",
    "bg-green-500",
  ];

  if (!password) return null;

  return (
    <div className="flex gap-1 mt-1.5">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className={`h-1 flex-1 rounded-full transition-all ${i < strength ? colors[strength] : "bg-white/10"}`}
        />
      ))}
    </div>
  );
}

interface AuthModalProps {
  type: "login" | "signup";
  open: boolean;
  onOpenChange: (v: boolean) => void;
}

export function AuthModal({ type, open, onOpenChange }: AuthModalProps) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useLogin();
  const signupMutation = useSignup();

  const handleOpenChange = (v: boolean) => {
    if (!v) {
      router.replace("/");
      setError("");
      setPassword("");
    }
    onOpenChange(v);
  };

  const handleGoogleLogin = async () => {
    try {
      const { data } = await apiClient.get('/auth/google/connect');
      if (data?.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error?.response?.data?.detail || "Could not connect to Google");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const formData = new FormData(e.currentTarget as HTMLFormElement);
    const email = formData.get("email") as string;
    const name = formData.get("name") as string;
    // We already have password in state, but can get from formData too
    const pwd = formData.get("password") as string;

    try {
      if (isLogin) {
        await loginMutation.mutateAsync({ email, password: pwd });
      } else {
        await signupMutation.mutateAsync({ email, password: pwd, full_name: name });
      }
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error?.response?.data?.detail || "An error occurred");
    }
  };

  const isLogin = type === "login";
  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md border-border bg-background">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-foreground">
            {isLogin ? "Welcome back" : "Create your account"}
          </DialogTitle>
          <DialogDescription>
            {isLogin
              ? "Sign in to your PersonalAPI account"
              : "Start for free. No credit card required."}
          </DialogDescription>
        </DialogHeader>

        {/* Google button */}
        <Button
          variant="outline"
          className="w-full border-white/20 hover:bg-white/5 cursor-pointer"
          type="button"
          onClick={handleGoogleLogin}
          disabled={loginMutation.isPending || signupMutation.isPending}
        >
          <GoogleIcon />
          Continue with Google
        </Button>

        {/* Divider */}
        <div className="relative flex items-center my-1">
          <Separator className="flex-1 opacity-20" />
          <span className="px-3 text-xs text-muted-foreground">
            or continue with email
          </span>
          <Separator className="flex-1 opacity-20" />
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Name field (signup only) */}
          {!isLogin && (
            <div className="space-y-2">
              <Label htmlFor="name" className="text-foreground">
                Name
              </Label>
              <Input
                id="name"
                placeholder="Your name"
                required
                className="bg-white/5 border-white/10"
              />
            </div>
          )}

          {/* Email field */}
          <div className="space-y-2">
            <Label htmlFor="email" className="text-foreground">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              required
              className="bg-white/5 border-white/10"
            />
          </div>

          {/* Password field */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password" className="text-foreground">
                Password
              </Label>
              {isLogin && (
                <Link
                  href="#"
                  className="text-xs transition-colors hover:text-foreground text-primary"
                >
                  Forgot password?
                </Link>
              )}
            </div>
            <Input
              id="password"
              type="password"
              placeholder="••••••••"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-white/5 border-white/10"
            />
            {!isLogin && <PasswordStrength password={password} />}
          </div>

          {/* Error alert */}
          {error && (
            <Alert variant="destructive" className="text-sm">
              {error}
            </Alert>
          )}

          {/* Submit */}
          <Button
            type="submit"
            className="w-full bg-[oklch(0.62_0.22_275)] hover:bg-[oklch(0.55_0.18_290)] text-white cursor-pointer"
          >
            {isLogin ? "Sign In" : "Create Account"}
          </Button>
        </form>

        {/* Footer link */}
        <p className="text-center text-sm text-muted-foreground">
          {isLogin ? (
            <>
              Don&apos;t have an account?{" "}
              <Link
                href="/?auth=signup"
                className="font-medium hover:underline text-primary"
              >
                Sign up
              </Link>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <Link
                href="/?auth=login"
                className="font-medium hover:underline text-primary"
              >
                Log in
              </Link>
            </>
          )}
        </p>
      </DialogContent>
    </Dialog>
  );
}