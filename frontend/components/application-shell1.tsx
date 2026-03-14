"use client";

import { ModeToggle } from "@/components/mode-toggle";
import { useLogout, useUser } from "@/hooks/use-auth";
import {
  ChevronRight,
  ChevronsUpDown,
  CreditCard,
  HelpCircle,
  Home,
  Key,
  LogOut,
  Plug,
  Search,
  Settings,
  Terminal,
  User,
} from "lucide-react";
  import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────

type NavItem = {
  label: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  href: string;
  children?: NavItem[];
};

type NavGroup = {
  title: string;
  items: NavItem[];
  defaultOpen?: boolean;
};

type UserData = {
  name: string;
  email: string;
  avatar: string;
};

type SidebarData = {
  logo: {
    title: string;
    description: string;
  };
  navGroups: NavGroup[];
  footerGroup: NavGroup;
  user?: UserData;
};

// ── Navigation Data (PersonalAPI) ────────────────────────────────────────

const sidebarData: SidebarData = {
  logo: {
    title: "PersonalAPI",
    description: "Your AI knowledge layer",
  },
  navGroups: [
    {
      title: "Overview",
      defaultOpen: true,
      items: [
        { label: "Home", icon: Home, href: "/dashboard" },
        { label: "Search & Chat", icon: Search, href: "/dashboard/search" },
        {
          label: "Integrations",
          icon: Plug,
          href: "/dashboard/integrations",
        },
      ],
    },
    {
      title: "Settings",
      defaultOpen: true,
      items: [
        { label: "API & Tokens", icon: Key, href: "/dashboard/api-keys" },
        { label: "How to use MCP", icon: Terminal, href: "/dashboard/mcp" },
        {
          label: "Pricing & Plans",
          icon: CreditCard,
          href: "/dashboard/pricing",
        },
        { label: "Profile", icon: User, href: "/dashboard/settings" },
      ],
    },
  ],
  footerGroup: {
    title: "Support",
    items: [
      { label: "Help Center", icon: HelpCircle, href: "#" },
      { label: "Settings", icon: Settings, href: "/dashboard/settings" },
    ],
  },
  user: {
    name: "Aditee Jadhav",
    email: "aditee@example.com",
    avatar: "",
  },
};

// ── Helper: map pathname → breadcrumb label ──────────────────────────────

const breadcrumbMap: Record<string, { group: string; page: string }> = {
  "/dashboard": { group: "Overview", page: "Home" },
  "/dashboard/search": { group: "Overview", page: "Search & Chat" },
  "/dashboard/integrations": { group: "Overview", page: "Integrations" },
  "/dashboard/api-keys": { group: "Settings", page: "API & Tokens" },
  "/dashboard/mcp": { group: "Settings", page: "How to use MCP" },
  "/dashboard/pricing": { group: "Settings", page: "Pricing & Plans" },
  "/dashboard/settings": { group: "Settings", page: "Profile" },
};

// ── Sub-components ───────────────────────────────────────────────────────

const SidebarLogo = ({ logo }: { logo: SidebarData["logo"] }) => {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" render={<Link href="/" />} className="hover:bg-transparent hover:text-sidebar-foreground">
          <React.Fragment>
            <Image
              src="/PersonalApi.png"
              alt="PersonalAPI logo"
              width={32}
              height={32}
              className="size-8 rounded-sm object-contain"
              priority
            />
            <div className="flex flex-col gap-0.5 leading-none">
              <span className="font-medium">{logo.title}</span>
              <span className="text-xs text-muted-foreground">
                {logo.description}
              </span>
            </div>
          </React.Fragment>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
};

const NavMenuItem = ({
  item,
  pathname,
}: {
  item: NavItem;
  pathname: string;
}) => {
  const Icon = item.icon;
  const isActive = pathname === item.href;
  const hasChildren = item.children && item.children.length > 0;

  if (!hasChildren) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          isActive={isActive}
          tooltip={item.label}
          render={<Link href={item.href} />}
        >
          <Icon className="size-4" />
          <span>{item.label}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }

  return (
    <Collapsible
      defaultOpen
      className="group/collapsible"
      render={<SidebarMenuItem />}
    >
      <CollapsibleTrigger
        render={<SidebarMenuButton isActive={isActive} />}
      >
        <Icon className="size-4" />
        <span>{item.label}</span>
        <ChevronRight className="ml-auto size-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <SidebarMenuSub>
          {item.children!.map((child) => (
            <SidebarMenuSubItem key={child.label}>
              <SidebarMenuSubButton
                isActive={pathname === child.href}
                render={<Link href={child.href} />}
              >
                {child.label}
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          ))}
        </SidebarMenuSub>
      </CollapsibleContent>
    </Collapsible>
  );
};

const NavUser = () => {
  const { data: user } = useUser();
  const { mutate: logout } = useLogout();
  const router = useRouter();

  if (!user) return null;

  const initials = user.full_name
    ? user.full_name
        .split(" ")
        .map((n: string) => n[0])
        .join("")
        .toUpperCase()
    : "U";
  
  const handleAccountClick = () => {
    router.push("/dashboard/settings");
  };

  const handleLogoutClick = () => {
    logout();
  };

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground hover:bg-transparent hover:text-sidebar-foreground"
              />
            }
          >
            <Avatar className="size-8 rounded-lg">
              <AvatarImage src="" alt={user.full_name} />
              <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
            </Avatar>
            <div className="grid flex-1 text-left text-sm leading-tight">
              <span className="truncate font-medium">{user.full_name}</span>
              <span className="truncate text-xs text-muted-foreground">
                {user.email}
              </span>
            </div>
            <ChevronsUpDown className="ml-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side="bottom"
            align="end"
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                  <Avatar className="size-8 rounded-lg">
                    <AvatarImage src="" alt={user.full_name} />
                    <AvatarFallback className="rounded-lg">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">{user.full_name}</span>
                    <span className="truncate text-xs text-muted-foreground">
                      {user.email}
                    </span>
                  </div>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleAccountClick} className="cursor-pointer">
              <User className="mr-2 size-4" />
              Account
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogoutClick} className="cursor-pointer">
              <LogOut className="mr-2 size-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
};

const AppSidebar = ({
  pathname,
  ...props
}: React.ComponentProps<typeof Sidebar> & { pathname: string }) => {
  return (
    <Sidebar {...props}>
      <SidebarHeader>
        <SidebarLogo logo={sidebarData.logo} />
      </SidebarHeader>
      <SidebarContent className="overflow-hidden">
        <ScrollArea className="min-h-0 flex-1">
          {sidebarData.navGroups.map((group) => (
            <SidebarGroup key={group.title} className="px-3">
              <SidebarGroupLabel className="text-sidebar-foreground/40 text-[10px] uppercase tracking-widest px-1">{group.title}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu className="gap-0.5">
                  {group.items.map((item) => (
                    <NavMenuItem
                      key={item.label}
                      item={item}
                      pathname={pathname}
                    />
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
};

// ── Main Shell ───────────────────────────────────────────────────────────

interface ApplicationShell1Props {
  className?: string;
  children?: React.ReactNode;
}

export function ApplicationShell1({
  className,
  children,
}: ApplicationShell1Props) {
  const pathname = usePathname();
  const crumb = breadcrumbMap[pathname] ?? { group: "Dashboard", page: "" };

  return (
    <SidebarProvider className={cn(className)}>
      <AppSidebar pathname={pathname} />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator
            orientation="vertical"
            className="mr-2 hidden data-[orientation=vertical]:h-4 md:block"
          />
          <a href="/dashboard" className="flex items-center gap-2 md:hidden">
            <Image
              src="/PersonalApi.png"
              alt="PersonalAPI logo"
              width={32}
              height={32}
              className="size-8 rounded-sm object-contain"
              priority
            />
            <span className="font-semibold">{sidebarData.logo.title}</span>
          </a>
          <Breadcrumb className="hidden md:block">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink href="/dashboard">
                  {crumb.group}
                </BreadcrumbLink>
              </BreadcrumbItem>
              {crumb.page && (
                <>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>{crumb.page}</BreadcrumbPage>
                  </BreadcrumbItem>
                </>
              )}
            </BreadcrumbList>
          </Breadcrumb>
          <div className="ml-auto flex items-center space-x-4">
            <ModeToggle />
          </div>
        </header>
        <main className="flex flex-1 flex-col gap-4 p-6 overflow-auto">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
