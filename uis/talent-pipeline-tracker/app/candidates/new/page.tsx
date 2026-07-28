// New candidate page — server component wrapper

import CandidateForm from "@/components/CandidateForm";

export const metadata = {
  title: "Nueva Candidatura — Brasaland",
};

export default function NewCandidatePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="mx-auto max-w-2xl px-4 py-4 sm:px-6 lg:px-8">
          <a
            href="/"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
          >
            ← Volver al pipeline
          </a>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xl">🔥</span>
            <h1 className="text-2xl font-bold text-gray-900">Nueva candidatura</h1>
          </div>
          <p className="text-sm text-gray-600">Registrar nuevo candidato en Brasaland People &amp; Talent</p>
        </div>
      </header>

      {/* Form */}
      <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-lg bg-white p-6 shadow">
          <CandidateForm mode="create" />
        </div>
      </main>
    </div>
  );
}
