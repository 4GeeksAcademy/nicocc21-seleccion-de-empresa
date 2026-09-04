import LoginForm from "../../components/auth/login-form";

export default function LoginPage() {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-stone-950 px-4">
      {/* Grid pattern de fondo */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
          backgroundSize: "32px 32px",
        }}
      />

      {/* Gradientes decorativos */}
      <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-amber-500/10 blur-3xl" />
      <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-red-600/10 blur-3xl" />
      <div className="absolute left-1/2 top-1/3 h-48 w-48 -translate-x-1/2 rounded-full bg-amber-400/5 blur-3xl" />

      <div className="relative w-full max-w-sm">
        {/* Logo y encabezado */}
        <div className="mb-8 text-center">
          <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-600 to-amber-400 font-extrabold text-stone-950 text-xl shadow-lg shadow-amber-500/25 ring-1 ring-amber-400/20">
            B
          </span>
          <h1 className="mt-6 text-3xl font-black tracking-tight text-white">
            Brasaland
          </h1>
          <p className="mt-1.5 text-sm text-stone-500">
            Directorio de Proveedores — Inicia sesión en tu cuenta
          </p>
        </div>

        {/* Tarjeta del formulario con efecto glassmorphism mejorado */}
        <div className="rounded-2xl border border-stone-800/80 bg-stone-900/60 p-8 shadow-2xl shadow-black/40 backdrop-blur-xl ring-1 ring-white/[0.02]">
          <LoginForm />
        </div>

        {/* Footer */}
        <p className="mt-8 text-center text-xs text-stone-600">
          &copy; {new Date().getFullYear()} Brasaland. Todos los derechos reservados.
        </p>
      </div>
    </div>
  );
}