"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiClient } from "@/lib/api-client";
import { AlertTriangleIcon, CheckIcon, CopyIcon, KeyIcon, Loader2Icon, PlusIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ApiKeyListItem {
  id: string;
  name: string | null;
  key_prefix: string;
  allowed_channels: string[];
  agent_type: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
}

interface ApiKeyCreateResponse extends ApiKeyListItem {
  api_key: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const EXPIRATION_OPTIONS = [
  { label: "1 month", value: "1 month", days: 30 },
  { label: "3 months", value: "3 months", days: 90 },
  { label: "6 months", value: "6 months", days: 180 },
  { label: "1 year", value: "1 year", days: 365 },
];

const getExpirationDateString = (days: number) => {
  return new Date(Date.now() + days * 24 * 60 * 60 * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

const getDaysLeftText = (expiresAt: string | null) => {
  if (!expiresAt) return "Never";
  const msLeft = new Date(expiresAt).getTime() - Date.now();
  const daysLeft = Math.ceil(msLeft / (1000 * 60 * 60 * 24));
  if (daysLeft < 0) return "Expired";
  if (daysLeft >= 364) return "1 year left";
  if (daysLeft >= 179 && daysLeft <= 181) return "6 months left";
  if (daysLeft >= 89 && daysLeft <= 91) return "3 months left";
  if (daysLeft >= 29 && daysLeft <= 31) return "1 month left";
  return `${daysLeft} days left`;
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create‑dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [channels, setChannels] = useState<string[]>([]);
  const [agentType, setAgentType] = useState("");
  const [expiresIn, setExpiresIn] = useState("1 year");
  const [creating, setCreating] = useState(false);

  // One‑time key display
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Revoke loading tracker
  const [revokingId, setRevokingId] = useState<string | null>(null);

  /* ---- Fetch keys ---- */
  const fetchKeys = useCallback(async () => {
    try {
      setError(null);
      const { data } = await apiClient.get<ApiKeyListItem[]>("/v1/developer/api-keys");
      setKeys(data.filter((k) => !k.revoked_at));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setError("session_expired");
      } else {
        const msg = err?.response?.data?.detail || "Failed to load API keys";
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  /* ---- Create key ---- */
  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error("Please enter a key name");
      return;
    }
    setCreating(true);
    try {
      const { data } = await apiClient.post<ApiKeyCreateResponse>("/v1/developer/api-keys", {
        name: name.trim(),
        allowed_channels: channels,
        agent_type: agentType.trim() || null,
        expires_in_days: EXPIRATION_OPTIONS.find((o) => o.value === expiresIn)?.days || 365,
      });
      setNewKey(data.api_key);
      toast.success("API key created successfully");
      fetchKeys();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to create API key";
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  };

  /* ---- Revoke key ---- */
  const handleRevoke = async (id: string) => {
    setRevokingId(id);
    try {
      await apiClient.post(`/v1/developer/api-keys/${id}/revoke`);
      toast.success("API key revoked");
      setKeys((prev) => prev.filter((k) => k.id !== id));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to revoke API key";
      toast.error(msg);
    } finally {
      setRevokingId(null);
    }
  };

  /* ---- Copy helper ---- */
  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /* ---- Reset dialog state ---- */
  const resetDialog = () => {
    setName("");
    setChannels([]);
    setAgentType("");
    setExpiresIn("1 year");
    setNewKey(null);
    setCopied(false);
  };

  /* ---- Format date ---- */
  const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold">
          API &amp; Tokens
        </h1>
        <p className="text-muted-foreground">
          Generate keys for agent and automation access to this API.
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex justify-end">
        <Dialog
          open={dialogOpen}
          onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) resetDialog();
          }}
        >
          <DialogTrigger
            render={
              <Button>
                <PlusIcon className="mr-2 h-4 w-4" />
                Create New Token
              </Button>
            }
          />

          <DialogContent className="sm:max-w-md">
            {/* ── After creation: show one‑time key ── */}
            {newKey ? (
              <>
                <DialogHeader>
                  <DialogTitle>Your new API key</DialogTitle>
                  <DialogDescription>
                    Copy this key now — it won&apos;t be shown again.
                  </DialogDescription>
                </DialogHeader>

                <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <AlertTriangleIcon className="h-4 w-4 shrink-0 text-amber-600" />
                  <span className="text-xs text-amber-800">
                    Store this key securely. It cannot be retrieved after you close this dialog.
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={newKey}
                    className="font-mono text-sm"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => copyToClipboard(newKey)}
                  >
                    {copied ? (
                      <CheckIcon className="h-4 w-4 text-green-600" />
                    ) : (
                      <CopyIcon className="h-4 w-4" />
                    )}
                  </Button>
                </div>

                <DialogFooter>
                  <Button onClick={() => { setDialogOpen(false); resetDialog(); }}>
                    Done
                  </Button>
                </DialogFooter>
              </>
            ) : (
              /* ── Create form ── */
              <>
                <DialogHeader>
                  <DialogTitle>Create API Key</DialogTitle>
                  <DialogDescription>
                    Generate a new developer key for agent or automation access.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                  {/* Name */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium" htmlFor="key-name">
                      Key Name
                    </label>
                    <Input
                      id="key-name"
                      placeholder="e.g. My MCP Agent Key"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>

                  {/* Agent Type */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium" htmlFor="agent-type">
                      Agent Type{" "}
                      <span className="text-muted-foreground font-normal">
                        (optional)
                      </span>
                    </label>
                    <Input
                      id="agent-type"
                      placeholder="e.g. mcp"
                      value={agentType}
                      onChange={(e) => setAgentType(e.target.value)}
                    />
                  </div>

                  {/* Expires In */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium" htmlFor="expires-in">
                      Expires In
                    </label>
                    <Select value={expiresIn} onValueChange={(v) => { if (v) setExpiresIn(v); }}>
                      <SelectTrigger id="expires-in">
                        <SelectValue placeholder="Select expiration">{expiresIn}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {EXPIRATION_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label} ({getExpirationDateString(opt.days)})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <DialogFooter>
                  <Button onClick={handleCreate} disabled={creating}>
                    {creating && (
                      <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Create Key
                  </Button>
                </DialogFooter>
              </>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Description Text */}
      <div className="text-sm text-muted-foreground bg-muted/30 p-4 rounded-lg border border-border/50">
        <p>Use these keys to authenticate your automations. Keys can be used for OpenClaw, Claude Code, MCP Servers, n8n workflows, and custom scripts.</p>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2Icon className="h-5 w-5 animate-spin" />
              <span>Loading keys…</span>
            </div>
          ) : error === "session_expired" ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
              <AlertTriangleIcon className="h-6 w-6 text-amber-500" />
              <p className="text-sm font-medium text-foreground">Session expired</p>
              <p className="text-xs text-muted-foreground">Please log in again to manage your API keys.</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (typeof window !== "undefined") {
                    localStorage.removeItem("access_token");
                  }
                  window.location.href = "/";
                }}
              >
                Log in again
              </Button>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
              <AlertTriangleIcon className="h-6 w-6 text-red-400" />
              <span className="text-sm text-red-500">{error}</span>
              <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchKeys(); }}>
                Retry
              </Button>
            </div>
          ) : keys.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
              <KeyIcon className="h-8 w-8" />
              <p className="text-sm">No API keys yet</p>
              <p className="text-xs">Create your first key to get started.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Key Prefix</TableHead>
                  <TableHead>Agent Type</TableHead>
                  <TableHead>Expires In</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((key) => {
                  const isRevoked = !!key.revoked_at;
                  return (
                    <TableRow
                      key={key.id}
                      className={isRevoked ? "opacity-50" : ""}
                    >
                      <TableCell className="font-medium">
                        {key.name || "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {key.key_prefix}
                      </TableCell>
                      <TableCell className="text-sm">
                        {key.agent_type || "—"}
                      </TableCell>
                      <TableCell className="text-sm min-w-[120px]">
                        {key.expires_at ? (
                          <div className="flex flex-col">
                            <span>{getDaysLeftText(key.expires_at)}</span>
                            <span className="text-xs text-muted-foreground">{fmt(key.expires_at)}</span>
                          </div>
                        ) : (
                          "Never"
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {fmt(key.created_at)}
                      </TableCell>
                      <TableCell>
                        {isRevoked ? (
                          <Badge
                            variant="outline"
                            className="border-red-200 bg-red-50 text-red-700 text-xs"
                          >
                            Revoked {fmt(key.revoked_at!)}
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="border-green-200 bg-green-50 text-green-700 text-xs"
                          >
                            Active
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={isRevoked || revokingId === key.id}
                          onClick={() => handleRevoke(key.id)}
                        >
                          {revokingId === key.id && (
                            <Loader2Icon className="mr-1 h-3 w-3 animate-spin" />
                          )}
                          Revoke
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
