import type { RuntimeDispatch } from "./useAgentRuntime";

export function requiresDispatchReview(dispatch: RuntimeDispatch) {
  return (
    dispatch.status === "failed" &&
    dispatch.error_code === "execution_interrupted_manual_review"
  );
}

export function dispatchSourceLabel(source: RuntimeDispatch["source_type"]) {
  if (source === "schedule") return "Agenda";
  if (source === "event") return "Evento";
  return "Repetição autorizada";
}
