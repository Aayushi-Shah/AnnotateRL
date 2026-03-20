"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart2, Database, LayoutDashboard, ListTodo, LogOut } from "lucide-react";
import { useAuthStore } from "@/lib/auth";
import { authApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navItems = [
  { href: "/researcher/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/researcher/tasks", label: "Tasks", icon: ListTodo },
  { href: "/researcher/datasets", label: "Datasets", icon: Database },
];

export function ResearcherNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, refreshToken, logout } = useAuthStore();

  async function handleLogout() {
    if (refreshToken) await authApi.logout(refreshToken).catch(() => {});
    logout();
    router.replace("/login");
  }

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card h-screen flex flex-col">
      <div className="p-4 border-b border-border">
        <span className="font-bold text-lg">AnnotateRL</span>
        <span className="ml-2 text-xs bg-blue-100 text-blue-800 rounded-full px-2 py-0.5">
          Researcher
        </span>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
              pathname.startsWith(href)
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-3 border-t border-border">
        <div className="px-3 py-1 text-xs text-muted-foreground truncate">{user?.name}</div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-3 text-muted-foreground mt-1"
          onClick={handleLogout}
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
