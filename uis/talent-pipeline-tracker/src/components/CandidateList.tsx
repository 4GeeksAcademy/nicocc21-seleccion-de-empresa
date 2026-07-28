// Client component for the candidate listing with filters and search

"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getCandidates } from "@/lib/api";
import { Candidate, CandidateStatus, CandidateStage, PaginatedResponse } from "@/lib/types";

const STATUS_OPTIONS: { value: CandidateStatus | ""; label: string }[] = [
  { value: "", label: "Todos los estados" },
  { value: "received", label: "Recibido" },
  { value: "in_progress", label: "En progreso" },
  { value: "selected", label: "Seleccionado" },
  { value: "discarded", label: "Descartado" },
];

const STAGE_OPTIONS: { value: CandidateStage | ""; label: string }[] = [
  { value: "", label: "Todas las etapas" },
  { value: "pending", label: "Pendiente" },
  { value: "review", label: "En revisión" },
  { value: "personal_interview", label: "Entrevista personal" },
  { value: "technical_interview", label: "Entrevista técnica" },
  { value: "offer_presented", label: "Oferta presentada" },
];

const STATUS_COLORS: Record<CandidateStatus, string> = {
  received: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  selected: "bg-green-100 text-green-800",
  discarded: "bg-red-100 text-red-800",
};

const STAGE_COLORS: Record<CandidateStage, string> = {
  pending: "bg-gray-100 text-gray-800",
  review: "bg-purple-100 text-purple-800",
  personal_interview: "bg-indigo-100 text-indigo-800",
  technical_interview: "bg-cyan-100 text-cyan-800",
  offer_presented: "bg-emerald-100 text-emerald-800",
};

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function StatusBadge({ status }: { status: CandidateStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[status]}`}>
      {STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status}
    </span>
  );
}

function StageBadge({ stage }: { stage: CandidateStage }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STAGE_COLORS[stage]}`}>
      {STAGE_OPTIONS.find((o) => o.value === stage)?.label ?? stage}
    </span>
  );
}

export default function CandidateList() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [pagination, setPagination] = useState({ total: 0, page: 1, limit: 20 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Read filters from URL
  const currentStatus = (searchParams.get("status") ?? "") as CandidateStatus | "";
  const currentStage = (searchParams.get("stage") ?? "") as CandidateStage | "";
  const currentSearch = searchParams.get("search") ?? "";
  const currentPage = Number(searchParams.get("page") ?? "1");

  const updateFilter = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      // Reset to page 1 when filters change (except when changing page)
      if (key !== "page") {
        params.delete("page");
      }
      router.push(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);

      try {
        const result = await getCandidates({
          status: currentStatus || undefined,
          stage: currentStage || undefined,
          search: currentSearch || undefined,
          page: currentPage,
          limit: 20,
        });

        if (!cancelled) {
          setCandidates(result.data);
          setPagination({ total: result.total, page: result.page, limit: result.limit });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Error al cargar los candidatos");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [currentStatus, currentStage, currentSearch, currentPage]);

  const totalPages = Math.ceil(pagination.total / pagination.limit);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🔥</span>
              <div>
                <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                  Brasaland — People &amp; Talent
                </h1>
                <p className="mt-1 text-sm text-gray-600">
                  Pipeline de selección · {pagination.total} candidatos
                </p>
              </div>
            </div>
            <Link
              href="/candidates/new"
              className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-500"
            >
              + Nueva candidatura
            </Link>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {/* Filters */}
        <div className="mb-6 rounded-lg bg-white p-4 shadow">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {/* Search */}
            <div>
              <label htmlFor="search" className="block text-sm font-medium text-gray-700">
                Buscar
              </label>
              <input
                type="text"
                id="search"
                placeholder="Nombre o email..."
                defaultValue={currentSearch}
                onChange={(e) => updateFilter("search", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Status filter */}
            <div>
              <label htmlFor="status" className="block text-sm font-medium text-gray-700">
                Estado
              </label>
              <select
                id="status"
                value={currentStatus}
                onChange={(e) => updateFilter("status", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Stage filter */}
            <div>
              <label htmlFor="stage" className="block text-sm font-medium text-gray-700">
                Etapa
              </label>
              <select
                id="stage"
                value={currentStage}
                onChange={(e) => updateFilter("stage", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {STAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
            <span className="ml-3 text-gray-600">Cargando candidatos...</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <div className="flex items-center">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="ml-3 text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Candidates list */}
        {!loading && !error && (
          <div className="overflow-hidden rounded-lg bg-white shadow">
            {candidates.length === 0 ? (
              <div className="py-12 text-center text-gray-500">
                No se encontraron candidatos con los filtros seleccionados.
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {candidates.map((candidate) => (
                  <li key={candidate.id}>
                    <Link
                      href={`/candidates/${candidate.id}`}
                      className="block hover:bg-gray-50 transition-colors"
                    >
                      <div className="px-4 py-4 sm:px-6">
                        <div className="flex items-center justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-blue-600">
                              {candidate.full_name}
                            </p>
                            <p className="mt-1 truncate text-sm text-gray-500">
                              {candidate.position}
                            </p>
                          </div>
                          <div className="ml-4 flex flex-shrink-0 items-center gap-2">
                            <StatusBadge status={candidate.status} />
                            <StageBadge stage={candidate.stage} />
                          </div>
                        </div>
                        <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                          <span>{candidate.email}</span>
                          <span>Aplicó: {formatDate(candidate.applied_at)}</span>
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6">
                <div className="flex flex-1 justify-between sm:hidden">
                  <button
                    onClick={() => updateFilter("page", String(Math.max(1, currentPage - 1)))}
                    disabled={currentPage <= 1}
                    className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => updateFilter("page", String(Math.min(totalPages, currentPage + 1)))}
                    disabled={currentPage >= totalPages}
                    className="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Siguiente
                  </button>
                </div>
                <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
                  <p className="text-sm text-gray-700">
                    Página <span className="font-medium">{currentPage}</span> de{" "}
                    <span className="font-medium">{totalPages}</span>
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => updateFilter("page", String(Math.max(1, currentPage - 1)))}
                      disabled={currentPage <= 1}
                      className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      ← Anterior
                    </button>
                    <button
                      onClick={() => updateFilter("page", String(Math.min(totalPages, currentPage + 1)))}
                      disabled={currentPage >= totalPages}
                      className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Siguiente →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
