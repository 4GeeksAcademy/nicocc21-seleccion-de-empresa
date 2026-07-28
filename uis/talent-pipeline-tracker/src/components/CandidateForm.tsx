// Client component — reusable form for creating and editing candidates

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Candidate, CandidateStatus, CandidateStage } from "@/lib/types";
import { createCandidate, updateCandidate } from "@/lib/api";

const STATUS_OPTIONS: { value: CandidateStatus; label: string }[] = [
  { value: "received", label: "Recibido" },
  { value: "in_progress", label: "En progreso" },
  { value: "selected", label: "Seleccionado" },
  { value: "discarded", label: "Descartado" },
];

const STAGE_OPTIONS: { value: CandidateStage; label: string }[] = [
  { value: "pending", label: "Pendiente" },
  { value: "review", label: "En revisión" },
  { value: "personal_interview", label: "Entrevista personal" },
  { value: "technical_interview", label: "Entrevista técnica" },
  { value: "offer_presented", label: "Oferta presentada" },
];

type CandidateFormData = Omit<Candidate, "id" | "applied_at" | "updated_at" | "notes" | "notes_count">;

interface CandidateFormProps {
  mode: "create" | "edit";
  initialData?: Candidate;
}

export default function CandidateForm({ mode, initialData }: CandidateFormProps) {
  const router = useRouter();
  const isEdit = mode === "edit";

  const [formData, setFormData] = useState<CandidateFormData>({
    full_name: initialData?.full_name ?? "",
    email: initialData?.email ?? "",
    phone: initialData?.phone ?? "",
    position: initialData?.position ?? "",
    linkedin_url: initialData?.linkedin_url ?? "",
    cv_url: initialData?.cv_url ?? "",
    status: initialData?.status ?? "received",
    stage: initialData?.stage ?? "pending",
    experience_years: initialData?.experience_years ?? 0,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === "experience_years" ? Number(value) : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      if (isEdit && initialData) {
        await updateCandidate(initialData.id, formData);
        router.push(`/candidates/${initialData.id}`);
      } else {
        const created = await createCandidate(formData);
        router.push(`/candidates/${created.id}`);
      }
      router.refresh();
    } catch {
      setError(isEdit ? "Error al guardar los cambios" : "Error al crear la candidatura");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Nombre */}
      <div>
        <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
          Nombre completo *
        </label>
        <input
          type="text"
          id="full_name"
          name="full_name"
          required
          value={formData.full_name}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700">
          Email *
        </label>
        <input
          type="email"
          id="email"
          name="email"
          required
          value={formData.email}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Teléfono */}
      <div>
        <label htmlFor="phone" className="block text-sm font-medium text-gray-700">
          Teléfono
        </label>
        <input
          type="tel"
          id="phone"
          name="phone"
          value={formData.phone}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Posición */}
      <div>
        <label htmlFor="position" className="block text-sm font-medium text-gray-700">
          Posición *
        </label>
        <input
          type="text"
          id="position"
          name="position"
          required
          value={formData.position}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* LinkedIn */}
      <div>
        <label htmlFor="linkedin_url" className="block text-sm font-medium text-gray-700">
          URL de LinkedIn
        </label>
        <input
          type="url"
          id="linkedin_url"
          name="linkedin_url"
          value={formData.linkedin_url ?? ""}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* CV URL */}
      <div>
        <label htmlFor="cv_url" className="block text-sm font-medium text-gray-700">
          URL del CV
        </label>
        <input
          type="url"
          id="cv_url"
          name="cv_url"
          value={formData.cv_url ?? ""}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Años de experiencia */}
      <div>
        <label htmlFor="experience_years" className="block text-sm font-medium text-gray-700">
          Años de experiencia
        </label>
        <input
          type="number"
          id="experience_years"
          name="experience_years"
          min={0}
          value={formData.experience_years}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Estado */}
      <div>
        <label htmlFor="status" className="block text-sm font-medium text-gray-700">
          Estado
        </label>
        <select
          id="status"
          name="status"
          value={formData.status}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Etapa */}
      <div>
        <label htmlFor="stage" className="block text-sm font-medium text-gray-700">
          Etapa
        </label>
        <select
          id="stage"
          name="stage"
          value={formData.stage}
          onChange={handleChange}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {STAGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Botones */}
      <div className="flex items-center gap-4 pt-4">
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-500 disabled:opacity-50"
        >
          {isSubmitting
            ? isEdit ? "Guardando…" : "Creando…"
            : isEdit ? "Guardar cambios" : "Crear candidatura"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}
