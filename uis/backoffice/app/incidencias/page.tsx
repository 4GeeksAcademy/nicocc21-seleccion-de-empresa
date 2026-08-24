"use client";

import { useCallback } from "react";
import IncidentForm from "./IncidentForm";
import IncidentList from "./IncidentList";
import IncidentsAnalyzer from "./IncidentsAnalyzer";
import Link from "next/link";

export default function IncidenciasPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-cyan-300/30 bg-gradient-to-br from-stone-900 to-cyan-950 p-8 shadow-2xl shadow-black/40">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-300">
            Postventa Brasaland
          </p>
          <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
            Gestión de incidencias
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
            Registra, filtra y da seguimiento a incidencias de los 14 locales Brasaland
            en Colombia y USA.
          </p>
        </header>

        <nav className="mt-6 flex flex-wrap gap-3 text-sm">
          <Link
            href="/"
            className="rounded-full border border-stone-700 px-4 py-2 text-stone-200 transition hover:border-cyan-300 hover:text-cyan-200"
          >
            Volver al panel principal
          </Link>
        </nav>

        {/* Nuevo: Formulario de creación */}
        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <IncidentForm onCreated={() => window.location.reload()} />
        </section>

        {/* Listado con filtros y resumen */}
        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <h2 className="mb-6 text-xl font-bold text-cyan-200">Incidencias registradas</h2>
          <IncidentList />
        </section>

        {/* Analizador CSV (existente) */}
        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <h2 className="mb-6 text-xl font-bold text-cyan-200">Analizador CSV</h2>
          <IncidentsAnalyzer />
        </section>
      </main>
    </div>
  );
}
