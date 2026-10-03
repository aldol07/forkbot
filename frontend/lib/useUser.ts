"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, User } from "./api";

/** Loads the current user; redirects to /login when `required` and signed out. */
export function useUser(required = true) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => { if (required) router.replace("/login"); })
      .finally(() => setLoading(false));
  }, [required, router]);
  return { user, loading };
}
