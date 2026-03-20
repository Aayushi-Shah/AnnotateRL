"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const _hasHydrated = useAuthStore((s) => s._hasHydrated);

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!accessToken || !user) {
      router.replace("/login");
    } else if (user.role === "annotator") {
      router.replace("/annotator/queue");
    } else {
      router.replace("/researcher/dashboard");
    }
  }, [_hasHydrated, accessToken, user, router]);

  return null;
}
