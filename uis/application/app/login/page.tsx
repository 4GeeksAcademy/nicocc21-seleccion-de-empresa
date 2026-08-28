import LoginForm from "../../components/auth/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-red-700 to-amber-500 font-extrabold text-white text-lg">
            B
          </span>
          <h1 className="mt-4 text-2xl font-black text-stone-100">Brasaland</h1>
          <p className="mt-1 text-sm text-stone-400">
            Directorio de Proveedores — Inicia sesión
          </p>
        </div>
        <div className="rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <LoginForm />
        </div>
      </div>
    </div>
  );
}