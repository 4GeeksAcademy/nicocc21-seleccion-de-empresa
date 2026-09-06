import { beforeEach, describe, expect, it, jest } from "@jest/globals";

import {
  createCandidate,
  getCandidateById,
  getCandidates,
  updateCandidate,
} from "../src/lib/api";
import type { Candidate, PaginatedResponse } from "../src/lib/types";

const candidate: Candidate = {
  id: "candidate-1",
  full_name: "Ana Torres",
  email: "ana@example.com",
  phone: "3001234567",
  position: "Frontend Developer",
  linkedin_url: null,
  cv_url: null,
  status: "received",
  stage: "pending",
  experience_years: 3,
  notes_count: 0,
  applied_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-01T10:00:00Z",
};

const candidateInput = {
  full_name: candidate.full_name,
  email: candidate.email,
  phone: candidate.phone,
  position: candidate.position,
  linkedin_url: candidate.linkedin_url,
  cv_url: candidate.cv_url,
  status: candidate.status,
  stage: candidate.stage,
  experience_years: candidate.experience_years,
};

function mockFetch(responseFactory: () => Response): void {
  const fetchMock = jest.fn<typeof fetch>();
  fetchMock.mockImplementation(async () => responseFactory());
  globalThis.fetch = fetchMock;
}

beforeEach(() => {
  jest.restoreAllMocks();
});

describe("getCandidates", () => {
  it("devuelve la lista paginada de candidatos", async () => {
    const result: PaginatedResponse<Candidate> = {
      total: 1,
      page: 1,
      limit: 20,
      data: [candidate],
    };
    mockFetch(() => new Response(JSON.stringify(result), { status: 200 }));

    await expect(getCandidates({ status: "received" })).resolves.toEqual(result);
  });

  it("propaga el detalle cuando la API rechaza la consulta", async () => {
    mockFetch(
      () => new Response(JSON.stringify({ detail: "Filtros inválidos" }), { status: 400 })
    );

    await expect(getCandidates()).rejects.toThrow("Filtros inválidos");
  });
});

describe("getCandidateById", () => {
  it("devuelve un candidato existente", async () => {
    mockFetch(() => new Response(JSON.stringify(candidate), { status: 200 }));

    await expect(getCandidateById(candidate.id)).resolves.toEqual(candidate);
  });

  it("convierte un fallo de conexión en un error útil", async () => {
    mockFetch(() => {
      throw new Error("Servicio no disponible");
    });

    await expect(getCandidateById(candidate.id)).rejects.toThrow("Servicio no disponible");
  });
});

describe("createCandidate", () => {
  it("devuelve el candidato creado", async () => {
    mockFetch(() => new Response(JSON.stringify(candidate), { status: 201 }));

    await expect(createCandidate(candidateInput)).resolves.toEqual(candidate);
  });

  it("rechaza una respuesta de API con formato inválido", async () => {
    mockFetch(() => new Response("respuesta ilegible", { status: 200 }));

    await expect(createCandidate(candidateInput)).rejects.toThrow(
      "La respuesta de la API no tiene un formato valido."
    );
  });
});

describe("updateCandidate", () => {
  it("devuelve el candidato actualizado", async () => {
    const updatedCandidate = { ...candidate, status: "in_progress" as const };
    mockFetch(() => new Response(JSON.stringify(updatedCandidate), { status: 200 }));

    await expect(
      updateCandidate(candidate.id, { status: "in_progress" })
    ).resolves.toEqual(updatedCandidate);
  });

  it("extrae el primer mensaje cuando la API devuelve errores de validación", async () => {
    mockFetch(
      () =>
        new Response(
          JSON.stringify({ detail: [{ msg: "El estado no es válido" }] }),
          { status: 422 }
        )
    );

    await expect(updateCandidate(candidate.id, { status: "received" })).rejects.toThrow(
      "El estado no es válido"
    );
  });
});
