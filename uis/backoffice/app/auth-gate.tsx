/**
 * AuthGate — wrapper cliente para proteger rutas.
 *
 * Se usa en el layout.tsx de apps protegidas.
 * Lee usePathname() para excluir /login y /register del chequeo de auth.
 */
"use client";

import { usePathname } from "next/navigation";
import AuthGuard from "../components/auth/auth-guard";

const PUBLIC_PATHS = ["/login", "/register"];

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (PUBLIC_PATHS.includes(pathname ?? "")) {
    return <>{children}</>;
  }

  return <AuthGuard>{children}</AuthGuard>;
}