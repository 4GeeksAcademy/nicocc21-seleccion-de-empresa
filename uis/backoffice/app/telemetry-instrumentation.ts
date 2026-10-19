import { track, isConfirmedEvent, type ConfirmedTelemetryEvent, type FrontendCapture, type SectionCode, type WorkflowType } from "./telemetry";

export function observeInventoryTelemetry(capture: (event: ConfirmedTelemetryEvent) => boolean = track): () => void {
  const originalFetch = globalThis.fetch;
  const observedFetch: typeof fetch = async (input, options) => {
    const response = await originalFetch(input, options);
    try {
      const request = input instanceof Request ? input : null;
      const url = new URL(request?.url ?? String(input), window.location.origin);
      const method = (options?.method ?? request?.method ?? "GET").toUpperCase();
      if (url.origin === window.location.origin && url.pathname.startsWith("/api/inventory/") && ["POST", "PATCH", "PUT"].includes(method)) {
        void response.clone().json().then((body: unknown) => {
          if (!body || typeof body !== "object") return;
          const payload = body as Record<string, unknown>;
          const detail = payload.detail && typeof payload.detail === "object" ? payload.detail as Record<string, unknown> : null;
          const events = payload.telemetry_events ?? detail?.telemetry_events;
          if (Array.isArray(events)) for (const event of events) {
            if (isConfirmedEvent(event)) capture(event);
          }
        }).catch(() => {});
      }
    } catch {
      return response;
    }
    return response;
  };
  globalThis.fetch = observedFetch;
  return () => {
    if (globalThis.fetch === observedFetch) globalThis.fetch = originalFetch;
  };
}

export function sectionForPath(pathname: string): SectionCode | null {
  if (pathname === "/") return "dashboard";
  const sections: [string, SectionCode][] = [
    ["/inventory/products", "inventory_products"],
    ["/inventory/orders", "inventory_orders"],
    ["/suppliers", "suppliers"],
    ["/incidencias", "incidents"],
    ["/account/profile", "profile"],
  ];
  return sections.find(([prefix]) => pathname === prefix || pathname.startsWith(`${prefix}/`))?.[1] ?? null;
}

export class NavigationTelemetry {
  private lastSection: SectionCode | null = null;
  private readonly errorTimes = new Map<string, number>();

  constructor(
    private readonly capture: FrontendCapture = track,
    private readonly releaseVersion = "0.1.0",
  ) {}

  visit(pathname: string): void {
    const section = sectionForPath(pathname);
    if (section === this.lastSection) return;
    this.lastSection = section;
    if (section) this.capture("section_viewed", { section_code: section });
  }

  reset(): void {
    this.lastSection = null;
  }

  error(code: "UNHANDLED_ERROR" | "UNHANDLED_REJECTION" | "API_CONNECTION_FAILED", pathname: string): void {
    const section = sectionForPath(pathname);
    if (!section) return;
    const signature = `${code}:${section}`;
    const last = this.errorTimes.get(signature);
    if (last !== undefined && Date.now() - last < 60000) return;
    if (this.capture("frontend_error_detected", {
      error_code: code, section_code: section, release_version: this.releaseVersion,
    })) this.errorTimes.set(signature, Date.now());
  }
}

export class WorkflowTelemetry {
  private workflowId: string | null = null;
  private requestId: string | null = null;

  constructor(
    private readonly workflowType: WorkflowType,
    private readonly capture: FrontendCapture = track,
  ) {}

  changed(): void {
    if (this.workflowId) return;
    try {
      this.workflowId = crypto.randomUUID();
      this.requestId = crypto.randomUUID();
      this.capture("workflow_started", {
        workflow_id: this.workflowId, workflow_type: this.workflowType,
      }, { requestId: this.requestId });
    } catch {
      this.finish();
    }
  }

  headers(): Record<string, string> {
    return this.workflowId && this.requestId
      ? { "X-Workflow-ID": this.workflowId, "X-Request-ID": this.requestId }
      : {};
  }

  cancel(): void {
    if (this.workflowId && this.requestId) this.capture("workflow_cancelled", {
      workflow_id: this.workflowId, workflow_type: this.workflowType, step_code: "form",
    }, { requestId: this.requestId });
    this.finish();
  }

  finish(): void {
    this.workflowId = null;
    this.requestId = null;
  }
}

export const navigationTelemetry = new NavigationTelemetry(
  track, process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0",
);