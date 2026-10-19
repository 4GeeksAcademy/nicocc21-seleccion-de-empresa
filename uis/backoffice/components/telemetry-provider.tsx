"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { telemetryService } from "../app/telemetry";
import { navigationTelemetry, observeInventoryTelemetry, sectionForPath } from "../app/telemetry-instrumentation";

export function TelemetryNavigation() {
  const pathname = usePathname();
  useEffect(() => {
    if (pathname) navigationTelemetry.visit(pathname);
  }, [pathname]);
  return null;
}

export default function TelemetryProvider() {
  const pathname = usePathname();
  useEffect(() => {
    if (!pathname || sectionForPath(pathname) === null) navigationTelemetry.reset();
  }, [pathname]);

  useEffect(() => {
    telemetryService.start();
    const stopObserving = observeInventoryTelemetry();
    const flush = () => telemetryService.flushOnExit();
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") flush();
    };
    const onError = () => navigationTelemetry.error("UNHANDLED_ERROR", window.location.pathname);
    const onRejection = () => navigationTelemetry.error("UNHANDLED_REJECTION", window.location.pathname);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", flush);
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
      stopObserving();
      telemetryService.stop();
    };
  }, []);

  return null;
}