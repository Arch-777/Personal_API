"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useConnectors, useGetConnectUrl, useSyncConnector } from "@/hooks/use-integrations";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

const SUPPORTED_INTEGRATIONS = [
  { name: "Notion", platform: "notion" },
  { name: "Google Calendar", platform: "gcal" },
  { name: "Google Drive", platform: "drive" },
  { name: "Slack", platform: "slack" },
  { name: "Gmail", platform: "gmail" },
  { name: "Spotify", platform: "spotify" },
];

export default function IntegrationsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const { data: connectors, isLoading } = useConnectors();
  const getConnectUrl = useGetConnectUrl();
  const syncConnector = useSyncConnector();

  useEffect(() => {
    const integration = searchParams.get("integration");
    const status = searchParams.get("status");
    const message = searchParams.get("message");

    if (!integration || !status) {
      return;
    }

    const normalized = integration.trim();
    const fallbackMessage =
      status === "success"
        ? `${normalized} connected successfully`
        : `${normalized} connection failed`;
    const toastMessage = (message || fallbackMessage).trim();

    if (status === "success") {
      toast.success(toastMessage);
    } else {
      toast.error(toastMessage);
    }

    router.replace("/dashboard/integrations", { scroll: false });
  }, [router, searchParams]);

  const handleConnect = async (platform: string) => {
    try {
      const url = await getConnectUrl.mutateAsync(platform);
      window.location.assign(url);
    } catch (err) {
      console.error(err);
      toast.error("Failed to initiate connection");
    }
  };

  const handleSync = async (platform: string) => {
    toast.promise(syncConnector.mutateAsync(platform), {
      loading: "Initiating sync...",
      success: "Sync queued successfully",
      error: "Failed to queue sync",
    });
  };

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold font-serif text-zinc-900 tracking-tight">
          Integrations
        </h1>
        <p className="text-zinc-500 font-serif">Manage your data sources.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
        {SUPPORTED_INTEGRATIONS.map((c) => {
          const connector = connectors?.find((conn) => conn.platform === c.platform);
          const isConnected = !!connector && connector.status !== "disconnected";
          const isSyncing = connector?.status === "syncing";
          const isConnecting = getConnectUrl.isPending && getConnectUrl.variables === c.platform;

          return (
            <Card
              key={c.name}
              className="flex flex-col overflow-hidden border-zinc-200 shadow-sm rounded-xl hover:shadow-md transition-shadow bg-white"
            >
              <CardHeader className="flex flex-col items-start gap-3 p-5 pb-5">
                <CardTitle className="text-2xl font-serif text-zinc-900 font-normal">
                  {c.name}
                </CardTitle>
                {connector?.platform_email && (
                  <p className="text-xs text-zinc-500 font-medium truncate w-full">
                    {connector.platform_email}
                  </p>
                )}
                <Badge
                  variant="outline"
                  className={`rounded-full px-3 py-0.5 text-xs font-semibold shrink-0 border-0 ${
                    isConnected
                      ? isSyncing
                        ? "bg-blue-100 text-blue-700"
                        : connector.status === "error"
                        ? "bg-red-100 text-red-700"
                        : "bg-zinc-900 text-zinc-50"
                      : "bg-zinc-100 text-zinc-500"
                  }`}
                >
                  {isConnected
                    ? isSyncing
                      ? "Syncing"
                      : connector.status === "error"
                      ? "Error"
                      : "Connected"
                    : "Not Connected"}
                </Badge>
              </CardHeader>
              <div className="flex-1" />
              <div className="flex gap-2 bg-zinc-50/80 p-4 border-t border-zinc-100">
                {!isConnected ? (
                  <Button
                    onClick={() => handleConnect(c.platform)}
                    disabled={isConnecting}
                    className="w-full h-10 rounded-lg font-medium transition-all duration-200 bg-[#18181b] text-zinc-50 hover:bg-[#27272a] shadow-sm"
                  >
                    {isConnecting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : null}
                    Connect
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => handleSync(c.platform)}
                      disabled={isSyncing || syncConnector.isPending}
                      className="flex-1 h-10 rounded-lg font-medium transition-all duration-200 bg-white border-zinc-200 shadow-sm hover:bg-zinc-50 text-zinc-900"
                    >
                      {isSyncing || (syncConnector.isPending && syncConnector.variables === c.platform) ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : null}
                      {isSyncing ? "Syncing..." : "Sync"}
                    </Button>
                  </>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
