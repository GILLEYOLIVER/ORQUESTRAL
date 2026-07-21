import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export type MetadataDataType =
  | "text"
  | "long_text"
  | "integer"
  | "decimal"
  | "boolean"
  | "date"
  | "datetime"
  | "email"
  | "phone"
  | "url"
  | "uuid"
  | "json";

export type MetadataValue =
  | string
  | number
  | boolean
  | null
  | MetadataValue[]
  | { [key: string]: MetadataValue };

export interface MetadataFieldInput {
  key: string;
  label: string;
  data_type: MetadataDataType;
  required: boolean;
  unique_values: boolean;
  searchable: boolean;
  default_value: MetadataValue;
  settings: Record<string, MetadataValue>;
  position: number;
}

export interface MetadataFieldResponse extends MetadataFieldInput {
  id: string;
}

export interface MetadataEntitySummary {
  id: string;
  key: string;
  label: string;
  plural_label: string;
  status: "draft" | "published" | "archived";
  current_version: number;
  published_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface MetadataEntityDetail extends MetadataEntitySummary {
  description: string | null;
  version: {
    id: string;
    version: number;
    status: "draft" | "validated" | "published" | "retired";
    schema_checksum: string;
    fields: MetadataFieldResponse[];
    published_at: string | null;
    created_at: string;
    updated_at: string;
  };
}

export type MetadataComparisonOperator =
  | "equals"
  | "not_equals"
  | "greater_than"
  | "less_than"
  | "contains"
  | "is_empty"
  | "is_not_empty";

export interface MetadataLayoutInput {
  key: string;
  label: string;
  sections: Array<{
    key: string;
    label: string;
    fields: string[];
    columns: number;
  }>;
  is_default: boolean;
}

export interface MetadataViewInput {
  key: string;
  label: string;
  columns: string[];
  filters: Array<{
    field_key: string;
    operator: MetadataComparisonOperator;
    value: MetadataValue;
  }>;
  sorting: Array<{ field_key: string; direction: "asc" | "desc" }>;
  is_default: boolean;
}

export interface MetadataValidationRuleInput {
  key: string;
  label: string;
  field_key: string;
  operator: MetadataComparisonOperator;
  comparison_value: MetadataValue;
  message: string;
  active: boolean;
}

export interface MetadataRelationshipInput {
  key: string;
  label: string;
  source_field_key: string;
  target_definition_id: string;
  relationship_type: "many_to_one" | "one_to_one";
  on_delete: "restrict";
}

export interface MetadataFormulaOperandInput {
  type: "field" | "literal";
  field_key: string | null;
  value: MetadataValue;
}

export interface MetadataFormulaInput {
  key: string;
  label: string;
  target_field_key: string;
  expression: {
    operator:
      "add" | "subtract" | "multiply" | "divide" | "concat" | "coalesce";
    operands: MetadataFormulaOperandInput[];
  };
  active: boolean;
}

export interface MetadataRecordTypeInput {
  key: string;
  label: string;
  description: string | null;
  layout_key: string;
  is_default: boolean;
  active: boolean;
}

export interface MetadataDesignResponse {
  layouts: MetadataLayoutInput[];
  views: MetadataViewInput[];
  validation_rules: MetadataValidationRuleInput[];
  relationships: MetadataRelationshipInput[];
  formulas: MetadataFormulaInput[];
  record_types: MetadataRecordTypeInput[];
  version: number;
  version_status: "draft" | "validated" | "published" | "retired";
  checksum: string;
}

export interface MetadataValidationResponse {
  entity_id: string;
  version: number;
  valid: boolean;
  errors: string[];
  schema_checksum: string;
}

export interface MetadataRecordResponse {
  id: string;
  definition_id: string;
  schema_version: number;
  record_type_key: string | null;
  values: Record<string, MetadataValue>;
  masked_fields: string[];
  record_version: number;
  created_at: string;
  updated_at: string;
}

export interface MetadataRecordPage {
  items: MetadataRecordResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export function useMetadataEntities() {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["metadata-entities", me?.current_company?.id],
    queryFn: () => request<MetadataEntitySummary[]>("/metadata/entities"),
    enabled:
      status === "authenticated" &&
      Boolean(me?.current_company) &&
      (me?.permissions.includes("metadata.view") ?? false),
  });
}

export function useMetadataEntity(definitionId: string | null) {
  return useQuery({
    queryKey: ["metadata-entity", definitionId],
    queryFn: () =>
      request<MetadataEntityDetail>(`/metadata/entities/${definitionId}`),
    enabled: Boolean(definitionId),
  });
}

export function useMetadataDesign(definitionId: string | null) {
  return useQuery({
    queryKey: ["metadata-design", definitionId],
    queryFn: () =>
      request<MetadataDesignResponse>(
        `/metadata/entities/${definitionId}/design`,
      ),
    enabled: Boolean(definitionId),
  });
}

export function useMetadataRecords(
  definitionId: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["metadata-records", definitionId],
    queryFn: () =>
      request<MetadataRecordPage>(
        `/metadata/entities/${definitionId}/records?page=1&page_size=100`,
      ),
    enabled: Boolean(definitionId) && enabled,
  });
}
