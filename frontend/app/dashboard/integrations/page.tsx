import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const connectors = [
  { name: "Notion", connected: true },
  { name: "Google Drive", connected: false },
  { name: "Slack", connected: false },
  { name: "Telegram", connected: true },
  { name: "Spotify", connected: false },
];

export default function IntegrationsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Connectors</h1>
      <p className="text-muted-foreground">Manage your data sources.</p>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {connectors.map((c) => (
          <Card key={c.name} className="flex flex-col justify-between">
            <CardHeader className="flex-row items-start justify-between">
              <CardTitle className="text-lg">{c.name}</CardTitle>
              <Badge variant={c.connected ? "default" : "secondary"}>
                {c.connected ? "Connected" : "Not Connected"}
              </Badge>
            </CardHeader>
            <CardContent className="flex-1" />
            <CardFooter>
              <Button
                variant={c.connected ? "secondary" : "default"}
                className="w-full"
              >
                {c.connected ? "Manage" : "Connect"}
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
