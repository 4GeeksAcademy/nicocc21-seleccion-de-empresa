"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { register, loginAfterRegister, setToken } from "../../../../src/auth/auth-client";

export default function RegisterForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setLoading(true);

    try {
      await register({ email, password, name, phone, address });
      const data = await loginAfterRegister(email, password);
      setToken(data.access_token);
      router.push("/");
    } catch (err: unknown) {
      if (err instanceof Response) {
        const body = await err.json().catch(() => ({ detail: "Error de conexión" }));
        if (body.detail && Array.isArray(body.detail)) {
          const fieldErrors: Record<string, string> = {};
          for (const e of body.detail) {
            fieldErrors[e.loc?.join(".") ?? "form"] = e.msg;
          }
          setErrors(fieldErrors);
        } else {
          setErrors({ form: body.detail ?? "Error al registrarse" });
        }
      } else if (err instanceof Error) {
        setErrors({ form: err.message });
      } else {
        setErrors({ form: "Error al registrarse" });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {errors.form && (
        <div className="rounded-lg border border-red-500/40 bg-red-950 p-3 text-sm text-red-200">
          {errors.form}
        </div>
      )}

      <div>
        <label htmlFor="name" className="block text-sm font-medium text-stone-300">
          Nombre completo
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Tu nombre"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
        {errors.name && <p className="mt-1 text-xs text-red-400">{errors.name}</p>}
      </div>

      <div>
        <label htmlFor="email" className="block text-sm font-medium text-stone-300">
          Correo electrónico
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="usuario@brasaland.com"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
        {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email}</p>}
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-stone-300">
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mín. 8 caracteres"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
        {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password}</p>}
      </div>

      <div>
        <label htmlFor="phone" className="block text-sm font-medium text-stone-300">
          Teléfono
        </label>
        <input
          id="phone"
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+57 300 123 4567"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      </div>

      <div>
        <label htmlFor="address" className="block text-sm font-medium text-stone-300">
          Dirección
        </label>
        <input
          id="address"
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Calle 123 # 45-67"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 px-4 py-2 text-sm font-bold text-stone-950 shadow transition hover:from-amber-500 hover:to-amber-400 disabled:opacity-50"
      >
        {loading ? "Creando cuenta…" : "Crear cuenta"}
      </button>

      <p className="text-center text-xs text-stone-500">
        ¿Ya tienes cuenta?{" "}
        <a href="/login" className="text-amber-400 underline hover:text-amber-300">
          Inicia sesión
        </a>
      </p>
    </form>
  );
}