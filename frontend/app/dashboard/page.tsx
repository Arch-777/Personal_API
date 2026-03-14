"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useUser } from "@/hooks/use-auth";
import { useConnectors } from "@/hooks/use-integrations";
import { useChatHistory } from "@/hooks/use-chat";
import { Clock, Database, Search, MessageSquare } from "lucide-react";

export default function DashboardHome() {
  const { data: user, isLoading: userLoading } = useUser();
  const { data: connectors, isLoading: connectorsLoading } = useConnectors();   
  const { data: chatHistory } = useChatHistory(null);

  if (userLoading || connectorsLoading) {
    return <div>Loading...</div>;
  }

  const connectedAppsCount = connectors?.filter((c: { status?: string; connected?: boolean }) => c.status === 'connected' || c.connected).length || 0;          
  const stats = [
    { label: "Connected Apps", value: connectedAppsCount.toString() },
  ];

  let recentActivities = [
    {
      id: "act-1",
      type: "search",
      title: 'Search query "Project Alpha timeline"',
      icon: Search,
      time: "12 mins ago",
      response: "Found 14 documents related to Project Alpha timeline. The most relevant document is 'Q3 Alpha Roadmap.pdf' which outlines the major milestones starting next month.",
    },
    {
      id: "act-2",
      type: "sync",
      title: "Synced 42 new files from Google Drive",
      icon: Database,
      time: "1 hour ago",
      response: "Successfully indexed 42 files from the 'Marketing Assets' shared drive. Embeddings generated and stored in the vector database.",
    },
    {
      id: "act-3",
      type: "search",
      title: 'Search query "Q4 Revenue Projections"',
      icon: Search,
      time: "3 hours ago",
      response: "Q4 revenue is projected to hit $1.2M based on the latest spreadsheet data from the Finance folder. This is a 15% increase compared to Q3.",
    }
  ];

  if (chatHistory && Array.isArray(chatHistory) && chatHistory.length > 0) {
     const historyToActivity = chatHistory
        .filter(msg => msg.role === 'user')
        .map((msg, idx) => ({
          id: `chat-${msg.id || idx}`,
          type: "chat",
          title: `Asked AI: "${msg.content.slice(0, 40)}${msg.content.length > 40 ? '...' : ''}"`,
          icon: MessageSquare,
          time: msg.created_at ? new Date(msg.created_at).toLocaleString() : 'Recently',
          response: (() => {
            const userIndex = chatHistory.findIndex(m => m.id === msg.id);
            for (let i = userIndex - 1; i >= 0; i--) {
              if (chatHistory[i].role === 'assistant') {
                return chatHistory[i].content;
              }
            }
            return "Exploring data...";
          })(),
        }))
        .slice(0, 5);
     
     if (historyToActivity.length > 0) {
         recentActivities = historyToActivity;
     }
  }

  return (
    <div className="space-y-8 flex-1">
      <div>
        <h1 className="text-3xl font-bold font-serif tracking-tight">Good morning, {user?.full_name || "User"}</h1>
        <p className="text-muted-foreground mt-2">Here is a quick overview of your personal knowledge layer today.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2">
        {stats.map((stat, i) => (
          <div key={i} className="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
            <p className="text-sm text-balance text-muted-foreground">{stat.label}</p>
            <div className="mt-4 text-3xl font-bold font-serif">{stat.value}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border bg-card text-card-foreground shadow-sm mt-8">
        <div className="p-6">
          <h3 className="text-lg font-serif font-medium">Recent Activity</h3>
          <p className="text-sm text-muted-foreground mt-1">Your latest searches and system synchronizations.</p>
        </div>
        <div className="px-6 pb-6 pt-0">
          <Accordion className="w-full">
            {recentActivities.map((item) => {
              const Icon = item.icon;
              return (
                <AccordionItem key={item.id} value={item.id} className="border-t-0 border-b py-2 first:pt-0 last:border-b-0">
                  <AccordionTrigger className="w-full hover:no-underline rounded-lg py-3 px-2">
                    <div className="flex items-center gap-4 text-left w-full">
                      <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-secondary/50 text-secondary-foreground">
                        <Icon className="size-4" />
                      </div>
                      <div className="grid gap-1 flex-1">
                        <p className="text-sm font-medium leading-none">{item.title}</p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="size-3" />
                          {item.time}
                        </p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="text-sm text-muted-foreground pl-16 pr-4 py-2 leading-relaxed whitespace-pre-wrap">
                      {item.response}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </div>
      </div>
    </div>
  );
}
