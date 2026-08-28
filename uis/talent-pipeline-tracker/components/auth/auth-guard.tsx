"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken, getMe } from "../../../../src/auth/auth-client";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    // Validar el token contra /auth/me en el backend
    getMe()
      .then(() => setChecked(true))
      .catch(() => {
        router.replace("/login");
      });
  }, [router]);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">Verificando sesión…</p>
      </div>
    );
  }

  return <>{children}</>;
}