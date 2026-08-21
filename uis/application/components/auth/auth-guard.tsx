"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "../../../../src/auth/auth-client";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [router]);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-950">
        <p className="text-stone-400">Verificando sesión…</p>
      </div>
    );
  }

  return <>{children}</>;
}