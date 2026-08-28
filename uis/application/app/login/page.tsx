import LoginForm from "../../components/auth/login-form";

export default function LoginPage() {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-stone-950 px-4">
      {/* Fondo con patrón sutil tipo grid */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
          backgroundSize: "40px 40px",
        }}
      />
      {/* Gradiente decorativo */}
      <div className="absolute -top-40 left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-amber-500/10 blur-3xl" />

      <div className="relative w-full max-w-sm">
        {/* Logo y encabezado */}
        <div className="mb-10 text-center">
          <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-red-700 to-amber-500 font-extrabold text-white text-xl shadow-lg shadow-amber-500/20">
            B
          </span>
          <h1 className="mt-5 text-3xl font-black tracking-tight text-stone-100">
            Brasaland
          </h1>
          <p className="mt-1.5 text-sm text-stone-500">
            Directorio de Proveedores — Inicia sesión en tu cuenta
          </p>
        </div>

        {/* Tarjeta del formulario */}
        <div className="rounded-2xl border border-stone-800 bg-stone-900/80 p-8 shadow-2xl shadow-black/50 backdrop-blur-sm">
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