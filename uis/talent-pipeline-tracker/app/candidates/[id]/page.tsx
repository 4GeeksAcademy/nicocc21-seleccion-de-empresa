// Candidate detail page - Server component that fetches data and passes to client

import { notFound } from "next/navigation";
import { getCandidateById } from "@/lib/api";
import CandidateDetail from "@/components/CandidateDetail";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function CandidatePage({ params }: PageProps) {
  const { id } = await params;

  let candidate;
  try {
    candidate = await getCandidateById(id);
  } catch {
    notFound();
  }

  return <CandidateDetail candidate={candidate} />;
}
