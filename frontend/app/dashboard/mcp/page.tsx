"use client";

import { Card, CardContent } from "@/components/ui/card";

export default function McpDocsPage() {
  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold">
          How to Use MCP
        </h1>
        <p className="text-muted-foreground">
          Instructions for integrating the MCP endpoint with agents and automations.
        </p>
      </div>

      <div className="space-y-6">
        <Card>
          <CardContent className="p-6 space-y-6">
            <div>
              <h3 className="text-lg font-semibold mb-2">Integrating with Agents (OpenClaw, Claude Code, OpenCode)</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Provide your agents with the unified MCP endpoint. They can interact with the server by sending standard HTTP POST requests with your developer API key.
              </p>
              <div className="bg-muted p-4 rounded-md font-mono text-sm space-y-2">
                <p><span className="text-primary font-semibold">URL:</span> {`https://${process.env.NEXT_PUBLIC_API_URL || "YOUR_BACKEND_URL"}/mcp/endpoint`}</p>
                <p><span className="text-primary font-semibold">Header:</span> X-API-Key: YOUR_API_KEY</p>
                <p><span className="text-primary font-semibold">Header:</span> Content-Type: application/json</p>
              </div>
              <div className="mt-4 space-y-2">
                <p className="text-sm font-medium">To list available tools:</p>
                <pre className="bg-[#1e1e1e] text-orange-200 p-4 rounded-md text-sm overflow-x-auto whitespace-pre">
{`{\n  "action": "list_tools"\n}`}
                </pre>
                <p className="text-sm font-medium mt-4">To call a tool (e.g., search):</p>
                <pre className="bg-[#1e1e1e] text-blue-200 p-4 rounded-md text-sm overflow-x-auto whitespace-pre">
{`{\n  "action": "call_tool",\n  "tool": "search",\n  "arguments": {\n    "query": "latest invoices",\n    "top_k": 10,\n    "type_filter": null,\n    "source_filter": null\n  }\n}`}
                </pre>
              </div>
            </div>
            
            <div className="border-t pt-6">
              <h3 className="text-lg font-semibold mb-2">Using with n8n (HTTP Request Node)</h3>
              <p className="text-sm text-muted-foreground mb-4">
                To trigger MCP tools within n8n workflows, configure an HTTP Request Node with the following settings:
              </p>
              <ul className="list-disc list-inside text-sm space-y-2 text-muted-foreground ml-4 mb-4">
                <li><strong>Method:</strong> POST</li>
                <li><strong>URL:</strong> <code>{`https://${process.env.NEXT_PUBLIC_API_URL || "YOUR_BACKEND_URL"}/mcp/endpoint`}</code></li>
                <li><strong>Authentication:</strong> Generic Credential Type (Header Auth)</li>
                <li><strong>Header Details:</strong> Name: <code>X-API-Key</code>, Value: your API token</li>
                <li><strong>Send Data:</strong> Yes (or Send Body: Yes)</li>
                <li><strong>Body Type:</strong> JSON</li>
              </ul>
              <p className="text-sm font-medium mb-2 mt-4">
                Example JSON Body (Ask tool):
              </p>
              <pre className="bg-[#1e1e1e] text-green-200 p-4 rounded-md text-sm overflow-x-auto whitespace-pre">
{`{\n  "action": "call_tool",\n  "tool": "ask",\n  "arguments": {\n    "question": "Summarize my meetings for today",\n    "top_k": 8\n  }\n}`}
              </pre>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}