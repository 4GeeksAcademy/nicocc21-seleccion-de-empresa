"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { removeToken } from "../../../../src/auth/auth-client";

export default function LogoutPage() {
  const router = useRouter();

  useEffect(() => {
    removeToken();
    router.replace("/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-950">
      <p className="text-stone-400">Cerrando sesión…</p>
    </div>
  );
}