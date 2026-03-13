import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function SearchPage() {
  return (
    <div className="flex flex-col h-full space-y-4">
      <h1 className="text-2xl font-bold">Semantic Search &amp; Chat</h1>

      <div className="flex gap-2">
        <Input
          type="text"
          placeholder="Ask anything about your data..."
          className="flex-1 h-10"
        />
        <Button className="h-10 px-6">Search</Button>
      </div>

      <Card className="flex-1">
        <CardContent className="flex h-full flex-col items-center justify-center text-muted-foreground">
          <p>Enter a query to start searching your connected knowledge base.</p>
        </CardContent>
      </Card>
    </div>
  );
}
