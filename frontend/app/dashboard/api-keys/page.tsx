import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const tokens = [
  { name: "OpenClaw Agent", prefix: "sk-live...492a", created: "Mar 10, 2026" },
  { name: "n8n Workflow", prefix: "sk-live...b291", created: "Feb 28, 2026" },
];

export default function ApiKeysPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">API &amp; Tokens</h1>
      <p className="text-muted-foreground">
        Manage API keys for OpenClaw agents and n8n workflows.
      </p>

      <div className="flex justify-end">
        <Button>Create New Token</Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Key Prefix</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tokens.map((token) => (
                <TableRow key={token.prefix}>
                  <TableCell>{token.name}</TableCell>
                  <TableCell className="font-mono">{token.prefix}</TableCell>
                  <TableCell>{token.created}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="destructive" size="sm">
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
