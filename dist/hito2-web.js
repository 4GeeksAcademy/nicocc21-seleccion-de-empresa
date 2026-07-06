"use strict";
(() => {
  // src/hito2/collections.ts
  var filtrar = (items, criterio) => {
    return items.filter(criterio);
  };
  var agruparPor = (items, obtenerClave) => {
    return items.reduce((acc, item) => {
      const key = obtenerClave(item);
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    }, {});
  };

  // src/hito2/aggregations.ts
  var estaEnRango = (fecha, rango) => {
    if (rango.desde && fecha < rango.desde) return false;
    if (rango.hasta && fecha > rango.hasta) return false;
    return true;
  };
  var generarReporteFinancieroPorLocal = (movimientos2, locales2, rango = {}) => {
    const movimientosFiltrados = filtrar(movimientos2, (m) => estaEnRango(m.fecha, rango));
    const movimientosPorLocal = agruparPor(movimientosFiltrados, (m) => m.localId);
    return locales2.map((local) => {
      const items = movimientosPorLocal[local.id] ?? [];
      const entradas = items.filter((m) => m.tipo === "entrada").reduce((acc, m) => acc + m.monto, 0);
      const salidas = items.filter((m) => m.tipo === "salida").reduce((acc, m) => acc + m.monto, 0);
      return {
        localId: local.id,
        nombreLocal: local.nombre,
        entradas,
        salidas,
        balance: entradas - salidas
      };
    });
  };

  // src/hito2/inventory-alerts.ts
  var PRIORIDAD_PESO = {
    critica: 4,
    alta: 3,
    media: 2,
    informativa: 1
  };
  var tieneStockBajo = (insumo) => {
    return insumo.stockActual <= insumo.stockMinimo;
  };
  var calcularImpactoEnDemanda = (fechaActual, fechasEspeciales2) => {
    const vigente = fechasEspeciales2.find(
      (f) => fechaActual >= f.fechaInicio && fechaActual <= f.fechaFin
    );
    return vigente?.factorDemanda ?? 1;
  };
  var generarAlertasInventario = (insumos2, fechaActual, fechasEspeciales2, consumoPromedioPorDia2) => {
    const factorDemanda = calcularImpactoEnDemanda(fechaActual, fechasEspeciales2);
    const alertas = [];
    for (const insumo of insumos2) {
      const consumoBase = consumoPromedioPorDia2[insumo.id] ?? 0;
      const consumoAjustado = consumoBase * factorDemanda;
      if (consumoAjustado <= 0) continue;
      const diasCobertura = insumo.stockActual / consumoAjustado;
      if (tieneStockBajo(insumo) || diasCobertura < 3) {
        const prioridad = diasCobertura < 2 ? "critica" : "alta";
        alertas.push({
          insumoId: insumo.id,
          nombreInsumo: insumo.nombre,
          prioridad,
          tipo: "faltante",
          mensaje: `Cobertura aproximada ${diasCobertura.toFixed(1)} dias. Reponer urgente.`
        });
        continue;
      }
      if (diasCobertura > insumo.frecuenciaRotacionDias * 1.2) {
        alertas.push({
          insumoId: insumo.id,
          nombreInsumo: insumo.nombre,
          prioridad: "media",
          tipo: "exceso",
          mensaje: `Cobertura aproximada ${diasCobertura.toFixed(1)} dias supera el ciclo de rotacion (${insumo.frecuenciaRotacionDias} dias).`
        });
        continue;
      }
      if (diasCobertura > insumo.frecuenciaRotacionDias) {
        alertas.push({
          insumoId: insumo.id,
          nombreInsumo: insumo.nombre,
          prioridad: "informativa",
          tipo: "exceso",
          mensaje: `Cobertura en limite alto (${diasCobertura.toFixed(1)} dias). Revisar pedido siguiente.`
        });
      }
    }
    return alertas.sort((a, b) => PRIORIDAD_PESO[b.prioridad] - PRIORIDAD_PESO[a.prioridad]);
  };

  // src/hito2/sample-data.ts
  var ciudades = [
    "Bogota",
    "Medellin",
    "Cali",
    "Barranquilla",
    "Cartagena",
    "Bucaramanga",
    "Pereira",
    "Miami",
    "Orlando",
    "Tampa",
    "Bogota",
    "Medellin",
    "Cali",
    "Miami"
  ];
  var locales = Array.from({ length: 14 }, (_, i) => ({
    id: `L${String(i + 1).padStart(2, "0")}`,
    nombre: `Brasaland Sede ${i + 1}`,
    ciudad: ciudades[i]
  }));
  var departamentos = ["cocina", "barra", "administracion", "marketing", "mantenimiento"];
  var movimientos = locales.flatMap((local, localIndex) => {
    return Array.from({ length: 10 }, (_, i) => {
      const dia = i % 28 + 1;
      const esEntrada = i % 2 === 0;
      const base = 1e6 + localIndex * 5e4 + i * 2e4;
      return {
        id: `M-${local.id}-${i + 1}`,
        localId: local.id,
        fecha: new Date(2026, 6, dia),
        tipo: esEntrada ? "entrada" : "salida",
        monto: esEntrada ? base * 1.8 : base,
        departamento: departamentos[i % departamentos.length],
        descripcion: esEntrada ? "Ventas del dia" : "Gasto operativo"
      };
    });
  });
  var insumos = [
    {
      id: "I-001",
      nombre: "Carne premium",
      categoria: "comida",
      stockActual: 120,
      stockMinimo: 150,
      perecedero: true,
      diasVidaUtil: 7,
      frecuenciaRotacionDias: 7
    },
    {
      id: "I-002",
      nombre: "Queso mozzarella",
      categoria: "comida",
      stockActual: 180,
      stockMinimo: 120,
      perecedero: true,
      diasVidaUtil: 10,
      frecuenciaRotacionDias: 7
    },
    {
      id: "I-003",
      nombre: "Cerveza artesanal",
      categoria: "bebida",
      stockActual: 420,
      stockMinimo: 180,
      perecedero: false,
      diasVidaUtil: 180,
      frecuenciaRotacionDias: 15
    },
    {
      id: "I-004",
      nombre: "Vino tinto",
      categoria: "bebida",
      stockActual: 90,
      stockMinimo: 100,
      perecedero: false,
      diasVidaUtil: 365,
      frecuenciaRotacionDias: 15
    },
    {
      id: "I-005",
      nombre: "Empaques takeout",
      categoria: "empaque",
      stockActual: 950,
      stockMinimo: 400,
      perecedero: false,
      diasVidaUtil: 365,
      frecuenciaRotacionDias: 15
    }
  ];
  var fechasEspeciales = [
    {
      nombre: "San Valentin",
      fechaInicio: new Date(2026, 1, 10),
      fechaFin: new Date(2026, 1, 16),
      factorDemanda: 1.6
    },
    {
      nombre: "Navidad",
      fechaInicio: new Date(2026, 11, 20),
      fechaFin: new Date(2026, 11, 31),
      factorDemanda: 2
    },
    {
      nombre: "Ano Nuevo",
      fechaInicio: new Date(2026, 0, 1),
      fechaFin: new Date(2026, 0, 7),
      factorDemanda: 1.7
    }
  ];
  var consumoPromedioPorDia = {
    "I-001": 55,
    "I-002": 18,
    "I-003": 22,
    "I-004": 20,
    "I-005": 40
  };

  // src/hito2/web.ts
  var moneda = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  });
  var formatearFecha = (fecha) => {
    return fecha.toLocaleDateString("es-CO", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    });
  };
  var clasePrioridad = (prioridad) => {
    if (prioridad === "critica") return "border-red-500/40 bg-red-900/30";
    if (prioridad === "alta") return "border-orange-500/40 bg-orange-900/20";
    if (prioridad === "media") return "border-amber-500/40 bg-amber-900/20";
    return "border-stone-600 bg-stone-800/40";
  };
  var toInputDate = (fecha) => {
    const year = fecha.getFullYear();
    const month = String(fecha.getMonth() + 1).padStart(2, "0");
    const day = String(fecha.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };
  var parseInputDate = (raw) => {
    const [year, month, day] = raw.split("-").map(Number);
    if (!year || !month || !day) return null;
    return new Date(year, month - 1, day);
  };
  var render = (desde, hasta, fechaAnalisis) => {
    const tablaReportesBody = document.getElementById("tablaReportesBody");
    const listaAlertas = document.getElementById("listaAlertas");
    const rangoReporte = document.getElementById("rangoReporte");
    const contextoAlertas = document.getElementById("contextoAlertas");
    if (!tablaReportesBody || !listaAlertas || !rangoReporte || !contextoAlertas) return;
    const reportes = generarReporteFinancieroPorLocal(movimientos, locales, { desde, hasta }).sort(
      (a, b) => b.balance - a.balance
    );
    tablaReportesBody.innerHTML = reportes.map(
      (reporte) => `
      <tr class="border-b border-stone-800/80">
        <td class="px-3 py-2 font-semibold">${reporte.nombreLocal}</td>
        <td class="px-3 py-2 text-emerald-300">${moneda.format(reporte.entradas)}</td>
        <td class="px-3 py-2 text-rose-300">${moneda.format(reporte.salidas)}</td>
        <td class="px-3 py-2 font-bold ${reporte.balance >= 0 ? "text-amber-200" : "text-red-300"}">${moneda.format(reporte.balance)}</td>
      </tr>
    `
    ).join("");
    rangoReporte.textContent = `Rango: ${formatearFecha(desde)} - ${formatearFecha(hasta)}`;
    const alertas = generarAlertasInventario(insumos, fechaAnalisis, fechasEspeciales, consumoPromedioPorDia);
    contextoAlertas.textContent = `Fecha de analisis: ${formatearFecha(fechaAnalisis)} (con fechas especiales activas)`;
    listaAlertas.innerHTML = alertas.map(
      (alerta) => `
      <li class="rounded-xl border px-4 py-3 ${clasePrioridad(alerta.prioridad)}">
        <p class="text-xs font-bold uppercase tracking-wide text-stone-300">${alerta.prioridad}</p>
        <p class="mt-1 text-sm font-semibold text-stone-100">${alerta.nombreInsumo}</p>
        <p class="mt-1 text-sm text-stone-300">${alerta.mensaje}</p>
      </li>
    `
    ).join("");
  };
  var iniciarFiltros = () => {
    const inputDesde = document.getElementById("filtroDesde");
    const inputHasta = document.getElementById("filtroHasta");
    const inputAnalisis = document.getElementById("filtroAnalisis");
    const resetFiltros = document.getElementById("resetFiltros");
    const filtrosError = document.getElementById("filtrosError");
    if (!inputDesde || !inputHasta || !inputAnalisis || !resetFiltros || !filtrosError) return;
    const defaults = {
      desde: new Date(2026, 6, 1),
      hasta: new Date(2026, 6, 31),
      analisis: new Date(2026, 1, 14)
    };
    const aplicarDefaults = () => {
      inputDesde.value = toInputDate(defaults.desde);
      inputHasta.value = toInputDate(defaults.hasta);
      inputAnalisis.value = toInputDate(defaults.analisis);
    };
    const recalcular = () => {
      const desde = parseInputDate(inputDesde.value);
      const hasta = parseInputDate(inputHasta.value);
      const analisis = parseInputDate(inputAnalisis.value);
      if (!desde || !hasta || !analisis) {
        filtrosError.textContent = "Completa todas las fechas para recalcular.";
        return;
      }
      if (desde > hasta) {
        filtrosError.textContent = "El rango es invalido: 'desde' no puede ser mayor que 'hasta'.";
        return;
      }
      filtrosError.textContent = "";
      render(desde, hasta, analisis);
    };
    aplicarDefaults();
    recalcular();
    inputDesde.addEventListener("input", recalcular);
    inputHasta.addEventListener("input", recalcular);
    inputAnalisis.addEventListener("input", recalcular);
    resetFiltros.addEventListener("click", () => {
      aplicarDefaults();
      recalcular();
    });
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarFiltros);
  } else {
    iniciarFiltros();
  }
})();
