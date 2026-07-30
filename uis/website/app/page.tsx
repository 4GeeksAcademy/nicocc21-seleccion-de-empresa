const sedes = [
  { ciudad: "Bogotá", pais: "Colombia" },
  { ciudad: "Medellín", pais: "Colombia" },
  { ciudad: "Cali", pais: "Colombia" },
  { ciudad: "Barranquilla", pais: "Colombia" },
  { ciudad: "Cartagena", pais: "Colombia" },
  { ciudad: "Bucaramanga", pais: "Colombia" },
  { ciudad: "Pereira", pais: "Colombia" },
  { ciudad: "Miami", pais: "Estados Unidos" },
  { ciudad: "Orlando", pais: "Estados Unidos" },
  { ciudad: "Tampa", pais: "Estados Unidos" },
];

const beneficios = [
  {
    titulo: "Carnes seleccionadas",
    descripcion:
      "Trabajamos con los mejores cortes, marinados por horas y cocinados a la perfección sobre brasas de carbón natural.",
    icono: "🔥",
  },
  {
    titulo: "14 sedes",
    descripcion:
      "Desde Bogotá hasta Miami, Brasaland está presente en las principales ciudades de Colombia y Estados Unidos.",
    icono: "🌎",
  },
  {
    titulo: "Experiencia completa",
    descripcion:
      "No solo comes bien — vives una experiencia. Ambiente, servicio y sabor que te hacen volver.",
    icono: "⭐",
  },
];

const pasos = [
  { numero: "01", titulo: "Elige tu sede", descripcion: "Encuentra la Brasaland más cercana entre nuestras 14 ubicaciones." },
  { numero: "02", titulo: "Reserva tu mesa", descripcion: "Agenda por WhatsApp o desde nuestra web en segundos." },
  { numero: "03", titulo: "Disfruta", descripcion: "Disfruta de carnes a la brasa, bebidas artesanales y un ambiente inigualable." },
];

export default function Home() {
  return (
    <div className="bg-stone-100 text-zinc-900 antialiased">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-amber-200 bg-stone-50/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <a href="#inicio" className="flex items-center gap-3" aria-label="Inicio Brasaland">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-red-700 to-amber-500 font-extrabold text-white">
              B
            </span>
            <span className="text-xl font-black tracking-tight">Brasaland</span>
          </a>
          <nav aria-label="Navegación principal" className="hidden md:block">
            <ul className="items-center gap-6 text-sm font-semibold md:flex">
              <li><a className="transition hover:text-amber-700" href="#beneficios">Beneficios</a></li>
              <li><a className="transition hover:text-amber-700" href="#como-funciona">Cómo funciona</a></li>
              <li><a className="transition hover:text-amber-700" href="#sedes">Sedes</a></li>
              <li><a className="transition hover:text-amber-700" href="#reservas">Reservas</a></li>
            </ul>
          </nav>
        </div>
      </header>

      <main id="contenido">
        {/* Hero */}
        <section id="inicio" className="relative overflow-hidden bg-gradient-to-br from-stone-950 via-red-950 to-stone-900 py-24 text-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-400">Cadena de restaurantes</p>
            <h1 className="mt-4 text-4xl font-black leading-tight sm:text-6xl">
              Sabor a la brasa<br />en <span className="text-amber-400">14 sedes</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-stone-300">
              Brasaland combina carnes seleccionadas, cocción sobre brasas de carbón natural y una experiencia
              que te hace volver. Desde Bogotá hasta Miami.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <a href="#reservas" className="rounded-full bg-gradient-to-r from-red-700 to-amber-600 px-6 py-3 text-sm font-bold text-white shadow-lg transition hover:from-red-800 hover:to-amber-700">
                Reserva tu mesa
              </a>
              <a href="#sedes" className="rounded-full border border-stone-600 px-6 py-3 text-sm font-bold text-stone-200 transition hover:border-amber-400 hover:text-amber-300">
                Ver sedes
              </a>
            </div>
          </div>
        </section>

        {/* Beneficios */}
        <section id="beneficios" className="py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-black tracking-tight">¿Por qué Brasaland?</h2>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {beneficios.map((b) => (
                <article key={b.titulo} className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
                  <span className="text-4xl">{b.icono}</span>
                  <h3 className="mt-4 text-lg font-bold">{b.titulo}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-stone-600">{b.descripcion}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Cómo funciona */}
        <section id="como-funciona" className="bg-stone-950 py-20 text-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-black tracking-tight">Cómo funciona</h2>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {pasos.map((p) => (
                <article key={p.numero} className="rounded-2xl border border-stone-800 bg-stone-900 p-6">
                  <span className="text-5xl font-black text-amber-500/30">{p.numero}</span>
                  <h3 className="mt-4 text-lg font-bold">{p.titulo}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-stone-400">{p.descripcion}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Sedes */}
        <section id="sedes" className="py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-black tracking-tight">Nuestras 14 sedes</h2>
            <p className="mt-3 max-w-2xl text-stone-600">
              Brasaland está presente en las principales ciudades de Colombia y en el sur de Florida.
            </p>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
              {sedes.map((s, i) => (
                <div key={i} className="rounded-xl border border-stone-200 bg-white p-4 text-center shadow-sm transition hover:border-amber-400 hover:shadow-md">
                  <p className="text-sm font-bold">{s.ciudad}</p>
                  <p className="text-xs text-stone-500">{s.pais}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Reservas */}
        <section id="reservas" className="bg-gradient-to-br from-red-900 to-amber-800 py-20 text-white">
          <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
            <h2 className="text-3xl font-black tracking-tight">Reserva tu mesa</h2>
            <p className="mt-3 text-lg text-red-100">Disponible en todas nuestras 14 sedes.</p>
            <a
              href="#"
              className="mt-8 inline-block rounded-full bg-white px-8 py-3 text-sm font-bold text-red-900 shadow-lg transition hover:bg-stone-100"
            >
              Reservar ahora
            </a>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-stone-200 bg-stone-50 py-8 text-center text-xs text-stone-500">
        <p>© 2026 Brasaland. Todos los derechos reservados.</p>
      </footer>
    </div>
  );
}
