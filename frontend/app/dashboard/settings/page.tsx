import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";

export default function SettingsPage() {
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
          <Input id="fullName" type="text" defaultValue="User Name" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            defaultValue="user@example.com"
            disabled
          />
        </div>
      </div>

      {/* Preferences Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Preferences</h2>
          <Separator className="mt-2" />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor="darkMode">Dark Mode</Label>
          <Switch id="darkMode" defaultChecked />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor="emailNotifications">Email Notifications</Label>
          <Switch id="emailNotifications" defaultChecked />
        </div>
      </div>
    </div>
  );
}
