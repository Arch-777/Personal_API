import { ApplicationShell1 } from "@/components/application-shell1";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ApplicationShell1>{children}</ApplicationShell1>;
}
