import ChangePasswordForm from "../../components/auth/change-password-form";

export default function ChangePasswordPage() {
  return (
    <div className="mx-auto max-w-lg px-4 py-12">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-black text-stone-100">Cambiar contraseña</h1>
        <p className="mt-1 text-sm text-stone-400">
          Ingresa tu contraseña actual y la nueva
        </p>
      </div>
      <div className="rounded-2xl border border-stone-700 bg-stone-900 p-6">
        <ChangePasswordForm />
      </div>
    </div>
  );
}