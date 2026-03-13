import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const integrations = [
  { name: "Notion", connected: true },
  { name: "Google Drive", connected: false },
  { name: "Slack", connected: false },
  { name: "Telegram", connected: true },
  { name: "Spotify", connected: false },
];

export default function IntegrationsPage() {
  return (
    <div className="space-y-8 max-w-5xl">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold font-serif text-zinc-900 tracking-tight">Integrations</h1>
        <p className="text-zinc-500 font-serif">Manage your data sources.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
        {integrations.map((c) => (
          <Card key={c.name} className="flex flex-col overflow-hidden border-zinc-200 shadow-sm rounded-xl hover:shadow-md transition-shadow bg-white">
            <CardHeader className="flex flex-col items-start gap-3 p-5 pb-5">
              <CardTitle className="text-2xl font-serif text-zinc-900 font-normal">{c.name}</CardTitle>
              <Badge 
                variant="outline"
                className={`rounded-full px-3 py-0.5 text-xs font-semibold shrink-0 border-0 ${
                  c.connected 
                    ? "bg-zinc-900 text-zinc-50" 
                    : "bg-zinc-100 text-zinc-500"
                }`}
              >
                {c.connected ? "Connected" : "Not Connected"}
              </Badge>
            </CardHeader>
            <div className="flex-1" />
            <div className="bg-zinc-50/80 p-4 border-t border-zinc-100">
              <Button
                variant={c.connected ? "outline" : "default"}
                className={`w-full h-10 rounded-lg font-medium transition-all duration-200 ${
                  c.connected 
                    ? "bg-white border-zinc-200 shadow-sm hover:bg-zinc-50 text-zinc-900" 
                    : "bg-[#18181b] text-zinc-50 hover:bg-[#27272a] shadow-sm"
                }`}
              >
                {c.connected ? "Manage" : "Connect"}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
