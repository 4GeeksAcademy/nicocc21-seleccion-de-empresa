// Client component for the candidate detail view

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Candidate, CandidateStatus, CandidateStage, Note } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://playground.4geeks.com/tracker/api/v1";

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
    month: "long",
    year: "numeric",
  });
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface CandidateDetailProps {
  candidate: Candidate;
}

export default function CandidateDetail({ candidate: initialCandidate }: CandidateDetailProps) {
  const router = useRouter();
  const [candidate, setCandidate] = useState(initialCandidate);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [newNote, setNewNote] = useState("");
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [notes, setNotes] = useState<Note[]>(initialCandidate.notes ?? []);

  const updateStatus = async (newStatus: CandidateStatus) => {
    setIsUpdating(true);
    setUpdateMessage(null);

    try {
      const response = await fetch(`${API_URL}/records/${candidate.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) throw new Error("Error al actualizar estado");

      const updated = await response.json();
      setCandidate((prev) => ({ ...prev, ...updated }));
      setUpdateMessage("Estado actualizado correctamente");
    } catch {
      setUpdateMessage("Error al actualizar el estado");
    } finally {
      setIsUpdating(false);
    }
  };

  const updateStage = async (newStage: CandidateStage) => {
    setIsUpdating(true);
    setUpdateMessage(null);

    try {
      const response = await fetch(`${API_URL}/records/${candidate.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: newStage }),
      });

      if (!response.ok) throw new Error("Error al actualizar etapa");

      const updated = await response.json();
      setCandidate((prev) => ({ ...prev, ...updated }));
      setUpdateMessage("Etapa actualizada correctamente");
    } catch {
      setUpdateMessage("Error al actualizar la etapa");
    } finally {
      setIsUpdating(false);
    }
  };

  const addNote = async () => {
    if (!newNote.trim()) return;

    setIsAddingNote(true);

    try {
      const response = await fetch(`${API_URL}/records/${candidate.id}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: newNote }),
      });

      if (!response.ok) throw new Error("Error al agregar nota");

      const note: Note = await response.json();
      setNotes((prev) => [...prev, note]);
      setNewNote("");
      setCandidate((prev) => ({ ...prev, notes_count: prev.notes_count + 1 }));
    } catch {
      setUpdateMessage("Error al agregar la nota");
    } finally {
      setIsAddingNote(false);
    }
  };

  const deleteNote = async (noteId: string) => {
    try {
      const response = await fetch(`${API_URL}/records/${candidate.id}/notes/${noteId}`, {
        method: "DELETE",
      });

      if (!response.ok) throw new Error("Error al eliminar nota");

      setNotes((prev) => prev.filter((n) => n.id !== noteId));
      setCandidate((prev) => ({ ...prev, notes_count: prev.notes_count - 1 }));
    } catch {
      setUpdateMessage("Error al eliminar la nota");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="mx-auto max-w-4xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <Link
              href="/"
              className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
            >
              ← Volver al pipeline
            </Link>
            <Link
              href={`/candidates/${candidate.id}/edit`}
              className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
            >
              ✏️ Editar
            </Link>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xl">🔥</span>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{candidate.full_name}</h1>
              <p className="text-sm text-gray-600">{candidate.position} · Brasaland People &amp; Talent</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
        {/* Update message */}
        {updateMessage && (
          <div
            className={`mb-4 rounded-lg p-3 text-sm ${
              updateMessage.includes("Error")
                ? "bg-red-50 text-red-700"
                : "bg-green-50 text-green-700"
            }`}
          >
            {updateMessage}
          </div>
        )}

        {/* Candidate info */}
        <div className="mb-6 rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Información del candidato</h2>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-gray-500">Email</dt>
              <dd className="mt-1 text-sm text-gray-900">{candidate.email}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Teléfono</dt>
              <dd className="mt-1 text-sm text-gray-900">{candidate.phone}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Años de experiencia</dt>
              <dd className="mt-1 text-sm text-gray-900">{candidate.experience_years}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Fecha de aplicación</dt>
              <dd className="mt-1 text-sm text-gray-900">{formatDate(candidate.applied_at)}</dd>
            </div>
            {candidate.linkedin_url && (
              <div>
                <dt className="text-sm font-medium text-gray-500">LinkedIn</dt>
                <dd className="mt-1">
                  <a
                    href={candidate.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Ver perfil →
                  </a>
                </dd>
              </div>
            )}
            {candidate.cv_url && (
              <div>
                <dt className="text-sm font-medium text-gray-500">CV</dt>
                <dd className="mt-1">
                  <a
                    href={candidate.cv_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Ver CV →
                  </a>
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Status and Stage controls */}
        <div className="mb-6 rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Estado y etapa</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Status */}
            <div>
              <label htmlFor="status" className="block text-sm font-medium text-gray-700">
                Estado actual
              </label>
              <div className="mt-1 flex items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[candidate.status]}`}
                >
                  {STATUS_OPTIONS.find((o) => o.value === candidate.status)?.label}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {STATUS_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => updateStatus(option.value)}
                    disabled={isUpdating || candidate.status === option.value}
                    className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                      candidate.status === option.value
                        ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Stage */}
            <div>
              <label htmlFor="stage" className="block text-sm font-medium text-gray-700">
                Etapa actual
              </label>
              <div className="mt-1 flex items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STAGE_COLORS[candidate.stage]}`}
                >
                  {STAGE_OPTIONS.find((o) => o.value === candidate.stage)?.label}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {STAGE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => updateStage(option.value)}
                    disabled={isUpdating || candidate.stage === option.value}
                    className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                      candidate.stage === option.value
                        ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Notas internas ({notes.length})
          </h2>

          {/* Add note form */}
          <div className="mb-4">
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="Escribe una nota interna..."
              rows={3}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={addNote}
              disabled={isAddingNote || !newNote.trim()}
              className="mt-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isAddingNote ? "Agregando..." : "Agregar nota"}
            </button>
          </div>

          {/* Notes list */}
          {notes.length === 0 ? (
            <p className="text-sm text-gray-500">No hay notas aún.</p>
          ) : (
            <ul className="divide-y divide-gray-200">
              {notes.map((note) => (
                <li key={note.id} className="py-3">
                  <div className="flex items-start justify-between">
                    <p className="text-sm text-gray-700">{note.content}</p>
                    <button
                      onClick={() => deleteNote(note.id)}
                      className="ml-4 text-sm text-red-500 hover:text-red-700"
                    >
                      Eliminar
                    </button>
                  </div>
                  <p className="mt-1 text-xs text-gray-400">{formatDateTime(note.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
