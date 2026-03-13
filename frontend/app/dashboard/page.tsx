"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useUser } from "@/hooks/use-auth";
import { Clock, Database, Search } from "lucide-react";

const stats = [
  { label: "Total Documents", value: "1,248" },
  { label: "Connected Apps", value: "5" },
];

const recentActivities = [
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

export default function DashboardHome() {
  const { data: user, isLoading } = useUser();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-8 flex-1">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Good morning, {user?.full_name || "User"}</h1>
        <p className="text-muted-foreground mt-2">Here is a quick overview of your personal knowledge layer today.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Your latest searches and system synchronizations.</CardDescription>
        </CardHeader>
        <CardContent>
          <Accordion className="w-full">
            {recentActivities.map((item) => {
              const Icon = item.icon;
              return (
                <AccordionItem key={item.id} value={item.id}>
                  <AccordionTrigger className="w-full hover:no-underline hover:bg-muted/50 rounded-lg px-2">
                    <div className="flex items-center gap-3 text-left w-full">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                        <Icon className="size-4" />
                      </div>
                      <div className="grid gap-0.5 flex-1">
                        <p className="text-sm font-medium leading-none">{item.title}</p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                          <Clock className="size-3" />
                          {item.time}
                        </p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="text-sm text-muted-foreground pl-13 pr-4 py-2 leading-relaxed">
                      {item.response}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </CardContent>
      </Card>
    </div>
  );
}
