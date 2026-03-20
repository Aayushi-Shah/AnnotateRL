"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth";
import { ResearcherNav } from "@/components/layout/ResearcherNav";

export default function ResearcherLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { accessToken, user, _hasHydrated } = useAuthStore();

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!accessToken || !user) {
      router.replace("/login");
    } else if (user.role === "annotator") {
      router.replace("/annotator/queue");
    }
  }, [_hasHydrated, accessToken, user, router]);

  if (!_hasHydrated || !accessToken || !user) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <ResearcherNav />
      <main className="flex-1 overflow-y-auto bg-background p-6">{children}</main>
    </div>
  );
}
