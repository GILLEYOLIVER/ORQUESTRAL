export function parseRuntimeToolArguments(
  value: string,
  allowedToolKeys: string[],
): Record<string, Record<string, unknown>> {
  const parsed: unknown = JSON.parse(value.trim() || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Os argumentos devem ser um objeto JSON.");
  }
  const allowed = new Set(allowedToolKeys);
  for (const [toolKey, argumentsValue] of Object.entries(parsed)) {
    if (!allowed.has(toolKey)) {
      throw new Error(`A ferramenta ${toolKey} não está na lista autorizada.`);
    }
    if (
      !argumentsValue ||
      typeof argumentsValue !== "object" ||
      Array.isArray(argumentsValue)
    ) {
      throw new Error(`Os argumentos de ${toolKey} devem ser um objeto JSON.`);
    }
  }
  return parsed as Record<string, Record<string, unknown>>;
}
