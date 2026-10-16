"use client";

import { useState } from "react";
import { WorkflowTelemetry } from "../app/telemetry-instrumentation";
import type { WorkflowType } from "../app/telemetry";

export function useWorkflowTelemetry(workflowType: WorkflowType): WorkflowTelemetry {
  const [workflow] = useState(() => new WorkflowTelemetry(workflowType));
  return workflow;
}