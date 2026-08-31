// API Client for the Talent Tracker API

import { Candidate, CandidateFilters, PaginatedResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://playground.4geeks.com/tracker/api/v1";

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${endpoint}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch (err: unknown) {
    throw new Error(
      err instanceof Error ? err.message : "No se pudo conectar con la API de talento."
    );
  }

  if (!response.ok) {
    let detail = `Error ${response.status}: ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail) && body.detail.length > 0 && body.detail[0]?.msg) {
        detail = body.detail[0].msg;
      }
    } catch {
      // ignore JSON parse errors, use default detail
    }
    throw new Error(detail);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("La respuesta de la API no tiene un formato valido.");
  }
}

export async function getCandidates(
  filters: CandidateFilters = {}
): Promise<PaginatedResponse<Candidate>> {
  const params = new URLSearchParams();

  if (filters.status) params.set("status", filters.status);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.search) params.set("search", filters.search);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.limit) params.set("limit", String(filters.limit));

  const queryString = params.toString();
  const endpoint = `/records${queryString ? `?${queryString}` : ""}`;

  return fetchAPI<PaginatedResponse<Candidate>>(endpoint);
}

export async function getCandidateById(id: string): Promise<Candidate> {
  return fetchAPI<Candidate>(`/records/${id}`);
}

export async function createCandidate(
  data: Omit<Candidate, "id" | "applied_at" | "updated_at" | "notes" | "notes_count">
): Promise<Candidate> {
  return fetchAPI<Candidate>("/records", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCandidate(
  id: string,
  data: Partial<Omit<Candidate, "id" | "applied_at" | "updated_at" | "notes" | "notes_count">>
): Promise<Candidate> {
  return fetchAPI<Candidate>(`/records/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
