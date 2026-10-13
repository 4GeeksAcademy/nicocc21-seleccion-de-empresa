/**
 * AuthGate — wrapper cliente para proteger rutas.
 *
 * Versión compartida en packages/shared/ui/auth/.
 * Se usa en los layouts de apps protegidas.
 * Lee usePathname() para excluir /login y /register del chequeo de auth.
 */
"use client";

import { usePathname } from "next/navigation";
import { AuthGuard } from "./auth-guard";

const PUBLIC_PATHS = ["/login", "/register", "/forgot-password", "/reset-password"];

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (PUBLIC_PATHS.includes(pathname ?? "")) {
    return <>{children}</>;
  }

  return <AuthGuard>{children}</AuthGuard>;
}