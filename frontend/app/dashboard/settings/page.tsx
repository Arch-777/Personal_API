"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useUser } from "@/hooks/use-auth";

export default function SettingsPage() {
  const { data: user, isLoading } = useUser();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Profile Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Profile</h2>
          <Separator className="mt-2" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="fullName">Full Name</Label>
          <Input 
            id="fullName" 
            type="text" 
            defaultValue={user?.full_name || "User Name"} 
            disabled 
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            defaultValue={user?.email || "user@example.com"}
            disabled
          />
        </div>
      </div>
    </div>
  );
}
