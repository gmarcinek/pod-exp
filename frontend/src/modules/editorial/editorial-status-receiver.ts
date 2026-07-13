export type EditorialStatusEvent = {
  id: string;
  timestamp: string;
  role: string;
  phase: string;
  status: string;
  message: string;
  lineStart: number | null;
  lineEnd: number | null;
  purpose: string;
};

export function receiveEditorialStatus(
  event: Record<string, unknown>,
): EditorialStatusEvent | null {
  if (event.type !== "editorial_status" || typeof event.message !== "string") {
    return null;
  }
  return {
    id: typeof event.id === "string" ? event.id : "",
    timestamp: typeof event.timestamp === "string" ? event.timestamp : "",
    role: typeof event.role === "string" ? event.role : "Workflow",
    phase: typeof event.phase === "string" ? event.phase : "unknown",
    status: typeof event.status === "string" ? event.status : "unknown",
    message: event.message,
    lineStart: typeof event.line_start === "number" ? event.line_start : null,
    lineEnd: typeof event.line_end === "number" ? event.line_end : null,
    purpose: typeof event.purpose === "string" ? event.purpose : "",
  };
}
