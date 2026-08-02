import IncidentsAnalyzer from "./IncidentsAnalyzer";

export default function IncidenciasPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-cyan-300/30 bg-gradient-to-br from-stone-900 to-cyan-950 p-8 shadow-2xl shadow-black/40">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-300">
            Postventa Brasaland
          </p>
          <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
            Analizador interno de incidencias
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
            Sube el CSV de incidencias para validar registros, obtener métricas y
            exportar resultados sin exponer datos sensibles fuera de la empresa.
          </p>
        </header>

        <nav className="mt-6 flex flex-wrap gap-3 text-sm">
          <a
            href="/"
            className="rounded-full border border-stone-700 px-4 py-2 text-stone-200 transition hover:border-cyan-300 hover:text-cyan-200"
          >
            Volver al panel principal
          </a>
        </nav>

        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <IncidentsAnalyzer />
        </section>
      </main>
    </div>
  );
}
