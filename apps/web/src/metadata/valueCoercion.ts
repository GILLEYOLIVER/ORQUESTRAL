import type {
  MetadataDataType,
  MetadataValue,
} from "./useMetadata";

export function inputTypeForMetadataField(dataType: MetadataDataType) {
  const types: Partial<Record<MetadataDataType, string>> = {
    date: "date",
    datetime: "datetime-local",
    email: "email",
    integer: "number",
    decimal: "number",
    phone: "tel",
    url: "url",
  };
  return types[dataType] ?? "text";
}

export function coerceMetadataInput(
  dataType: MetadataDataType,
  rawValue: string | boolean,
): MetadataValue | undefined {
  if (dataType === "boolean") return Boolean(rawValue);
  const value = String(rawValue).trim();
  if (!value) return undefined;
  if (dataType === "integer") {
    const parsed = Number(value);
    return Number.isInteger(parsed) ? parsed : value;
  }
  if (dataType === "decimal") return value;
  if (dataType === "datetime" && !/(Z|[+-]\d{2}:\d{2})$/.test(value)) {
    return new Date(value).toISOString();
  }
  if (dataType === "json") return JSON.parse(value) as MetadataValue;
  return value;
}

export function displayMetadataValue(value: MetadataValue) {
  if (value === null) return "Vazio";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
