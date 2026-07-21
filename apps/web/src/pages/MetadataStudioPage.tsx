import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Braces,
  CheckCircle2,
  CirclePlus,
  Database,
  FileCheck2,
  LayoutTemplate,
  Layers3,
  ListChecks,
  Calculator,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Network,
  Tags,
  Pencil,
  Plus,
  Rocket,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import {
  type MetadataDataType,
  type MetadataComparisonOperator,
  type MetadataDesignResponse,
  type MetadataEntityDetail,
  type MetadataEntityPackage,
  type MetadataEntitySummary,
  type MetadataFieldInput,
  type MetadataRecordResponse,
  type MetadataFormulaInput,
  type MetadataRecordTypeInput,
  type MetadataRelationshipInput,
  type MetadataValidationResponse,
  type MetadataValidationRuleInput,
  type MetadataValue,
  type MetadataViewInput,
  useMetadataEntities,
  useMetadataEntity,
  useMetadataDesign,
  useMetadataRecords,
} from "../metadata/useMetadata";
import {
  coerceMetadataInput,
  displayMetadataValue,
  inputTypeForMetadataField,
} from "../metadata/valueCoercion";
import { useSession } from "../session/context";
import "../metadata/metadata-studio.css";

const FIELD_TYPES: Array<{ value: MetadataDataType; label: string }> = [
  { value: "text", label: "Texto curto" },
  { value: "long_text", label: "Texto longo" },
  { value: "integer", label: "Número inteiro" },
  { value: "decimal", label: "Número decimal" },
  { value: "boolean", label: "Sim ou não" },
  { value: "date", label: "Data" },
  { value: "datetime", label: "Data e hora" },
  { value: "email", label: "E-mail" },
  { value: "phone", label: "Telefone" },
  { value: "url", label: "Endereço web" },
  { value: "uuid", label: "Identificador UUID" },
  { value: "json", label: "Objeto estruturado" },
];

const RULE_OPERATORS: Array<{
  value: MetadataComparisonOperator;
  label: string;
}> = [
  { value: "equals", label: "É igual a" },
  { value: "not_equals", label: "É diferente de" },
  { value: "greater_than", label: "É maior que" },
  { value: "less_than", label: "É menor que" },
  { value: "contains", label: "Contém" },
  { value: "is_empty", label: "Está vazio" },
  { value: "is_not_empty", label: "Não está vazio" },
];

const RECORD_PAGE_SIZE = 20;

function blankField(position: number): MetadataFieldInput {
  return {
    key: "",
    label: "",
    data_type: "text",
    required: false,
    unique_values: false,
    searchable: false,
    default_value: null,
    settings: {},
    position,
  };
}

function blankRule(
  index: number,
  fieldKey: string,
): MetadataValidationRuleInput {
  return {
    key: `rule_${Date.now()}_${index}`,
    label: "",
    field_key: fieldKey,
    operator: "is_not_empty",
    comparison_value: null,
    message: "",
    active: true,
  };
}

function blankRelationship(
  index: number,
  fieldKey: string,
  targetId: string,
): MetadataRelationshipInput {
  return {
    key: `relationship_${Date.now()}_${index}`,
    label: "",
    source_field_key: fieldKey,
    target_definition_id: targetId,
    relationship_type: "many_to_one",
    on_delete: "restrict",
  };
}

function blankFormula(index: number, fieldKey: string): MetadataFormulaInput {
  return {
    key: `formula_${Date.now()}_${index}`,
    label: "",
    target_field_key: fieldKey,
    expression: {
      operator: "add",
      operands: [
        { type: "field", field_key: fieldKey, value: null },
        { type: "literal", field_key: null, value: 0 },
      ],
    },
    active: true,
  };
}

function blankRecordType(index: number): MetadataRecordTypeInput {
  const key = `tipo_${Date.now()}_${index}`;
  return {
    key,
    label: "",
    description: null,
    layout_key: `layout_${key}`,
    is_default: false,
    active: true,
  };
}

function blankView(index: number, fieldKey: string): MetadataViewInput {
  return {
    key: `view_${Date.now()}_${index}`,
    label: "Nova visualização",
    columns: fieldKey ? [fieldKey] : [],
    filters: [],
    sorting: [],
    is_default: false,
  };
}

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a operação no Studio.";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "Rascunho",
    validated: "Validado",
    published: "Publicado",
    retired: "Substituído",
  };
  return labels[status] ?? status;
}

export function MetadataStudioPage() {
  const queryClient = useQueryClient();
  const { me } = useSession();
  const entities = useMetadataEntities();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedQuery = useMetadataEntity(selectedId);
  const selected = selectedQuery.data;
  const design = useMetadataDesign(selectedId);
  const [activeViewKey, setActiveViewKey] = useState<string | null>(null);
  const [recordPage, setRecordPage] = useState(1);
  const records = useMetadataRecords(
    selectedId,
    Boolean(selected?.published_version),
    selected?.version.status === "published" ? activeViewKey : null,
    recordPage,
    RECORD_PAGE_SIZE,
  );
  const canConfigure = me?.permissions.includes("metadata.configure") ?? false;
  const canPublish = me?.permissions.includes("metadata.publish") ?? false;
  const canCreateRecords =
    me?.permissions.includes("metadata.records.create") ?? false;
  const canUpdateRecords =
    me?.permissions.includes("metadata.records.update") ?? false;
  const canDeleteRecords =
    me?.permissions.includes("metadata.records.delete") ?? false;

  const [schemaOpen, setSchemaOpen] = useState(false);
  const [editingSchema, setEditingSchema] = useState(false);
  const [entityKey, setEntityKey] = useState("");
  const [label, setLabel] = useState("");
  const [pluralLabel, setPluralLabel] = useState("");
  const [description, setDescription] = useState("");
  const [fields, setFields] = useState<MetadataFieldInput[]>([blankField(0)]);
  const [recordValues, setRecordValues] = useState<
    Record<string, string | boolean>
  >({});
  const [editingRecord, setEditingRecord] =
    useState<MetadataRecordResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [designOpen, setDesignOpen] = useState(false);
  const [layoutLabel, setLayoutLabel] = useState("Formulário principal");
  const [sectionLabel, setSectionLabel] = useState("Informações principais");
  const [layoutFieldKeys, setLayoutFieldKeys] = useState<string[]>([]);
  const [views, setViews] = useState<MetadataViewInput[]>([]);
  const [editingViewKey, setEditingViewKey] = useState<string | null>(null);
  const [validationRules, setValidationRules] = useState<
    MetadataValidationRuleInput[]
  >([]);
  const [relationships, setRelationships] = useState<
    MetadataRelationshipInput[]
  >([]);
  const [formulas, setFormulas] = useState<MetadataFormulaInput[]>([]);
  const [recordTypes, setRecordTypes] = useState<MetadataRecordTypeInput[]>([]);
  const [recordTypeFields, setRecordTypeFields] = useState<
    Record<string, string[]>
  >({});
  const [recordTypeKey, setRecordTypeKey] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && entities.data?.length) {
      setSelectedId(entities.data[0].id);
    }
  }, [entities.data, selectedId]);

  useEffect(() => {
    if (!design.data) return;
    const defaultLayout =
      design.data.layouts.find((item) => item.is_default) ??
      design.data.layouts[0];
    const defaultView =
      design.data.views.find((item) => item.is_default) ?? design.data.views[0];
    setLayoutLabel(defaultLayout?.label ?? "Formulário principal");
    setSectionLabel(
      defaultLayout?.sections[0]?.label ?? "Informações principais",
    );
    setLayoutFieldKeys(
      defaultLayout?.sections.flatMap((section) => section.fields) ?? [],
    );
    setViews(design.data.views);
    setEditingViewKey(defaultView?.key ?? null);
    setActiveViewKey((current) =>
      design.data?.views.some((item) => item.key === current)
        ? current
        : (defaultView?.key ?? null),
    );
    setRecordPage(1);
    setValidationRules(design.data.validation_rules);
    setRelationships(design.data.relationships);
    setFormulas(design.data.formulas);
    setRecordTypes(design.data.record_types);
    setRecordTypeFields(
      Object.fromEntries(
        design.data.record_types.map((recordType) => {
          const layout = design.data.layouts.find(
            (item) => item.key === recordType.layout_key,
          );
          return [
            recordType.key,
            layout?.sections.flatMap((section) => section.fields) ?? [],
          ];
        }),
      ),
    );
    setRecordTypeKey(
      design.data.record_types.find((item) => item.is_default)?.key ?? null,
    );
  }, [design.data]);

  const refresh = (definitionId = selectedId) => {
    void queryClient.invalidateQueries({ queryKey: ["metadata-entities"] });
    void queryClient.invalidateQueries({
      queryKey: ["metadata-entity", definitionId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["metadata-records", definitionId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["metadata-design", definitionId],
    });
  };

  const resetSchema = () => {
    setSchemaOpen(false);
    setEditingSchema(false);
    setEntityKey("");
    setLabel("");
    setPluralLabel("");
    setDescription("");
    setFields([blankField(0)]);
  };

  const loadSchema = (entity: MetadataEntityDetail) => {
    setEditingSchema(true);
    setSchemaOpen(true);
    setEntityKey(entity.key);
    setLabel(entity.label);
    setPluralLabel(entity.plural_label);
    setDescription(entity.description ?? "");
    setFields(
      entity.version.fields.map((field) => ({
        key: field.key,
        label: field.label,
        data_type: field.data_type,
        required: field.required,
        unique_values: field.unique_values,
        searchable: field.searchable,
        default_value: field.default_value,
        settings: field.settings,
        position: field.position,
      })),
    );
  };

  const saveSchema = useMutation({
    mutationFn: () => {
      const body = {
        label,
        plural_label: pluralLabel,
        description: description || null,
        fields: fields.map((field, position) => ({ ...field, position })),
      };
      return editingSchema && selectedId
        ? request<MetadataEntityDetail>(
            `/metadata/entities/${selectedId}/draft`,
            { method: "PUT", body },
          )
        : request<MetadataEntityDetail>("/metadata/entities", {
            method: "POST",
            body: { ...body, key: entityKey },
          });
    },
    onSuccess: (entity) => {
      queryClient.setQueriesData<MetadataEntitySummary[]>(
        { queryKey: ["metadata-entities"] },
        (current) => [
          entity,
          ...(current ?? []).filter((item) => item.id !== entity.id),
        ],
      );
      setSelectedId(entity.id);
      resetSchema();
      refresh(entity.id);
    },
  });

  const validateSchema = useMutation({
    mutationFn: () =>
      request<MetadataValidationResponse>(
        `/metadata/entities/${selectedId}/validate`,
        { method: "POST" },
      ),
    onSuccess: () => refresh(),
  });

  const publishSchema = useMutation({
    mutationFn: () =>
      request<MetadataEntityDetail>(
        `/metadata/entities/${selectedId}/publish`,
        { method: "POST" },
      ),
    onSuccess: () => refresh(),
  });

  const createVersion = useMutation({
    mutationFn: () =>
      request<MetadataEntityDetail>(
        `/metadata/entities/${selectedId}/versions`,
        { method: "POST" },
      ),
    onSuccess: (entity) => {
      refresh(entity.id);
      loadSchema(entity);
    },
  });

  const saveDesign = useMutation({
    mutationFn: () => {
      const layouts = recordTypes.map((recordType) => ({
        key: recordType.layout_key,
        label: recordType.is_default
          ? layoutLabel
          : `Formulario - ${recordType.label}`,
        is_default: recordType.is_default,
        sections: [
          {
            key: "main_section",
            label: recordType.is_default
              ? sectionLabel
              : `Dados de ${recordType.label}`,
            fields: recordType.is_default
              ? layoutFieldKeys
              : (recordTypeFields[recordType.key] ?? layoutFieldKeys),
            columns: 2,
          },
        ],
      }));
      const normalizedViews = views.map((view) => ({
        ...view,
        filters: view.filters.map((filter) => {
          if (filter.operator.startsWith("is_")) {
            return { ...filter, value: null };
          }
          const field = (selected?.version.fields ?? []).find(
            (candidate) => candidate.key === filter.field_key,
          );
          if (!field) return filter;
          const raw =
            typeof filter.value === "boolean"
              ? filter.value
              : String(filter.value ?? "");
          return {
            ...filter,
            value: coerceMetadataInput(field.data_type, raw) ?? null,
          };
        }),
      }));
      return request<MetadataDesignResponse>(
        `/metadata/entities/${selectedId}/design`,
        {
          method: "PUT",
          body: {
            layouts,
            views: normalizedViews,
            validation_rules: validationRules,
            relationships,
            formulas,
            record_types: recordTypes,
          },
        },
      );
    },
    onSuccess: () => {
      setDesignOpen(false);
      refresh();
    },
  });

  const exportPackage = useMutation({
    mutationFn: () =>
      request<MetadataEntityPackage>(
        `/metadata/entities/${selectedId}/package`,
      ),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${data.definition.key}.orkestral.json`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  const importPackage = useMutation({
    mutationFn: (packageData: MetadataEntityPackage) =>
      request<MetadataEntityDetail>("/metadata/packages/import", {
        method: "POST",
        body: { package: packageData },
      }),
    onSuccess: (entity) => {
      setSelectedId(entity.id);
      refresh(entity.id);
    },
  });

  const createRecord = useMutation({
    mutationFn: (values: Record<string, MetadataValue>) =>
      request<MetadataRecordResponse>(
        `/metadata/entities/${selectedId}/records`,
        {
          method: "POST",
          body: {
            values,
            record_type_key: recordTypeKey,
            idempotency_key: crypto.randomUUID(),
          },
        },
      ),
    onSuccess: () => {
      setRecordValues({});
      refresh();
    },
  });

  const updateRecord = useMutation({
    mutationFn: ({
      record,
      values,
    }: {
      record: MetadataRecordResponse;
      values: Record<string, MetadataValue>;
    }) =>
      request<MetadataRecordResponse>(
        `/metadata/entities/${selectedId}/records/${record.id}`,
        {
          method: "PUT",
          body: {
            values,
            record_type_key: recordTypeKey,
            expected_version: record.record_version,
          },
        },
      ),
    onSuccess: () => {
      setEditingRecord(null);
      setRecordValues({});
      refresh();
    },
  });

  const deleteRecord = useMutation({
    mutationFn: (record: MetadataRecordResponse) =>
      request<void>(
        `/metadata/entities/${selectedId}/records/${record.id}?expected_version=${record.record_version}`,
        { method: "DELETE" },
      ),
    onSuccess: () => refresh(),
  });

  const mutationError =
    saveSchema.error ??
    validateSchema.error ??
    publishSchema.error ??
    createVersion.error ??
    saveDesign.error ??
    createRecord.error ??
    updateRecord.error ??
    deleteRecord.error;
  const operationError =
    mutationError ?? exportPackage.error ?? importPackage.error;

  const selectedFields = useMemo(
    () => selected?.version.fields ?? [],
    [selected],
  );
  const formulaTargetKeys = useMemo(
    () =>
      new Set(
        formulas
          .filter((item) => item.active)
          .map((item) => item.target_field_key),
      ),
    [formulas],
  );
  const activeRecordType = useMemo(
    () =>
      design.data?.record_types.find((item) => item.key === recordTypeKey) ??
      design.data?.record_types.find((item) => item.is_default),
    [design.data, recordTypeKey],
  );
  const activeLayoutFieldKeys = useMemo(() => {
    const layout = design.data?.layouts.find(
      (item) => item.key === activeRecordType?.layout_key,
    );
    return (
      layout?.sections.flatMap((section) => section.fields) ?? layoutFieldKeys
    );
  }, [activeRecordType, design.data, layoutFieldKeys]);
  const runtimeFields = useMemo(() => {
    const order = new Map(
      activeLayoutFieldKeys.map((key, index) => [key, index]),
    );
    return [...selectedFields].sort(
      (left, right) =>
        (order.get(left.key) ?? Number.MAX_SAFE_INTEGER) -
        (order.get(right.key) ?? Number.MAX_SAFE_INTEGER),
    );
  }, [activeLayoutFieldKeys, selectedFields]);
  const visibleFields = useMemo(() => {
    const activeView =
      design.data?.views.find((item) => item.key === activeViewKey) ??
      design.data?.views.find((item) => item.is_default);
    const allowed = new Set(activeView?.columns ?? []);
    const configured = runtimeFields.filter((field) => allowed.has(field.key));
    return configured.length ? configured : runtimeFields;
  }, [activeViewKey, design.data, runtimeFields]);
  const primaryField = useMemo(
    () => visibleFields.find((field) => field.required) ?? visibleFields[0],
    [visibleFields],
  );
  const editingView = useMemo(
    () => views.find((item) => item.key === editingViewKey) ?? views[0],
    [editingViewKey, views],
  );

  const submitSchema = (event: FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    if (fields.some((field) => !field.key.trim() || !field.label.trim())) {
      setLocalError("Preencha a chave e o nome de todos os campos.");
      return;
    }
    saveSchema.mutate();
  };

  const submitRecord = (event: FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    try {
      const values = Object.fromEntries(
        runtimeFields
          .filter((field) => !formulaTargetKeys.has(field.key))
          .flatMap((field) => {
            const raw = recordValues[field.key] ?? "";
            const value = coerceMetadataInput(field.data_type, raw);
            return value === undefined ? [] : [[field.key, value]];
          }),
      ) as Record<string, MetadataValue>;
      if (editingRecord) {
        updateRecord.mutate({ record: editingRecord, values });
      } else {
        createRecord.mutate(values);
      }
    } catch {
      setLocalError(
        "Revise os campos estruturados. O JSON informado não é válido.",
      );
    }
  };

  const submitDesign = (event: FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    if (
      !layoutFieldKeys.length ||
      !views.length ||
      views.some((view) => !view.label.trim() || !view.columns.length)
    ) {
      setLocalError(
        "Escolha pelo menos um campo para o formulário e para a lista.",
      );
      return;
    }
    if (
      validationRules.some((rule) => !rule.label.trim() || !rule.message.trim())
    ) {
      setLocalError("Informe o nome e a mensagem de todas as regras.");
      return;
    }
    if (
      relationships.some((item) => !item.label.trim()) ||
      formulas.some((item) => !item.label.trim()) ||
      recordTypes.some((item) => !item.label.trim())
    ) {
      setLocalError("Preencha os nomes das configuracoes avancadas.");
      return;
    }
    saveDesign.mutate();
  };

  const updateEditingView = (
    updater: (view: MetadataViewInput) => MetadataViewInput,
  ) => {
    if (!editingView) return;
    setViews((current) =>
      current.map((item) =>
        item.key === editingView.key ? updater(item) : item,
      ),
    );
  };

  const handlePackageFile = async (file: File | undefined) => {
    if (!file) return;
    setLocalError(null);
    try {
      const packageData = JSON.parse(
        await file.text(),
      ) as MetadataEntityPackage;
      importPackage.mutate(packageData);
    } catch {
      setLocalError("O arquivo selecionado não contém um pacote válido.");
    }
  };

  const editRecord = (record: MetadataRecordResponse) => {
    setEditingRecord(record);
    setRecordTypeKey(record.record_type_key);
    setRecordValues(
      Object.fromEntries(
        Object.entries(record.values).map(([key, value]) => [
          key,
          typeof value === "boolean"
            ? value
            : typeof value === "object"
              ? JSON.stringify(value)
              : String(value ?? ""),
        ]),
      ),
    );
  };

  return (
    <div className="management-page metadata-studio">
      <header className="metadata-studio__hero">
        <div>
          <span className="eyebrow">Plataforma orientada por metadados</span>
          <h1>Orkestral Studio</h1>
          <p>
            Modele processos próprios, publique contratos seguros e opere os
            registros sem alterar o núcleo da plataforma.
          </p>
        </div>
        <PermissionGuard all={["metadata.configure"]}>
          <div className="metadata-hero-actions">
            {selectedId ? (
              <Button
                loading={exportPackage.isPending}
                onClick={() => exportPackage.mutate()}
                variant="ghost"
              >
                <Download size={17} /> Exportar pacote
              </Button>
            ) : null}
            <label className="metadata-import-button">
              <Upload size={17} /> Importar pacote
              <input
                accept="application/json,.json"
                onChange={(event) => {
                  void handlePackageFile(event.target.files?.[0]);
                  event.target.value = "";
                }}
                type="file"
              />
            </label>
            <Button
              onClick={() => {
                resetSchema();
                setSchemaOpen(true);
              }}
            >
              <CirclePlus size={18} /> Nova entidade
            </Button>
          </div>
        </PermissionGuard>
      </header>

      {entities.isError || selectedQuery.isError || records.isError ? (
        <Alert variant="error">
          Não foi possível carregar todas as informações do Studio.
        </Alert>
      ) : null}
      {operationError || localError ? (
        <Alert variant="error">
          {localError || errorMessage(operationError)}
        </Alert>
      ) : null}

      {schemaOpen ? (
        <Card className="metadata-schema-builder">
          <div className="metadata-card-heading">
            <div>
              <span className="eyebrow">
                {editingSchema ? "Editar rascunho" : "Novo contrato"}
              </span>
              <h2>Defina os dados sem escrever código</h2>
            </div>
            <button
              aria-label="Fechar construtor"
              className="metadata-icon-button"
              onClick={resetSchema}
              type="button"
            >
              <X size={18} />
            </button>
          </div>
          <form onSubmit={submitSchema}>
            <div className="metadata-schema-main-fields">
              <label>
                <span>Chave técnica</span>
                <input
                  disabled={editingSchema}
                  onChange={(event) => setEntityKey(event.target.value)}
                  pattern="[a-z][a-z0-9_]*"
                  placeholder="contrato_servico"
                  required
                  value={entityKey}
                />
              </label>
              <label>
                <span>Nome no singular</span>
                <input
                  onChange={(event) => setLabel(event.target.value)}
                  placeholder="Contrato de serviço"
                  required
                  value={label}
                />
              </label>
              <label>
                <span>Nome no plural</span>
                <input
                  onChange={(event) => setPluralLabel(event.target.value)}
                  placeholder="Contratos de serviço"
                  required
                  value={pluralLabel}
                />
              </label>
              <label className="metadata-wide-field">
                <span>Descrição para a equipe</span>
                <textarea
                  onChange={(event) => setDescription(event.target.value)}
                  rows={2}
                  value={description}
                />
              </label>
            </div>
            <div className="metadata-fields-heading">
              <div>
                <strong>Campos do registro</strong>
                <small>Tipos e regras serão validados também pela API.</small>
              </div>
              <Button
                onClick={() =>
                  setFields((current) => [
                    ...current,
                    blankField(current.length),
                  ])
                }
                type="button"
                variant="ghost"
              >
                <Plus size={16} /> Adicionar campo
              </Button>
            </div>
            <div className="metadata-field-stack">
              {fields.map((field, index) => (
                <div
                  className="metadata-field-row"
                  key={`${field.key}-${index}`}
                >
                  <span className="metadata-field-index">{index + 1}</span>
                  <label>
                    <span>Chave</span>
                    <input
                      onChange={(event) =>
                        setFields((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, key: event.target.value }
                              : item,
                          ),
                        )
                      }
                      pattern="[a-z][a-z0-9_]*"
                      required
                      value={field.key}
                    />
                  </label>
                  <label>
                    <span>Nome</span>
                    <input
                      onChange={(event) =>
                        setFields((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, label: event.target.value }
                              : item,
                          ),
                        )
                      }
                      required
                      value={field.label}
                    />
                  </label>
                  <label>
                    <span>Tipo</span>
                    <select
                      onChange={(event) =>
                        setFields((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? {
                                  ...item,
                                  data_type: event.target
                                    .value as MetadataDataType,
                                }
                              : item,
                          ),
                        )
                      }
                      value={field.data_type}
                    >
                      {FIELD_TYPES.map((type) => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="metadata-field-flags">
                    <label>
                      <input
                        checked={field.required}
                        onChange={(event) =>
                          setFields((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, required: event.target.checked }
                                : item,
                            ),
                          )
                        }
                        type="checkbox"
                      />
                      Obrigatório
                    </label>
                    <label>
                      <input
                        checked={field.unique_values}
                        onChange={(event) =>
                          setFields((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? {
                                    ...item,
                                    unique_values: event.target.checked,
                                  }
                                : item,
                            ),
                          )
                        }
                        type="checkbox"
                      />
                      Valor único
                    </label>
                  </div>
                  <button
                    aria-label={`Remover campo ${index + 1}`}
                    className="metadata-remove-field"
                    disabled={fields.length === 1}
                    onClick={() =>
                      setFields((current) =>
                        current.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                    type="button"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="metadata-form-actions">
              <Button loading={saveSchema.isPending} type="submit">
                <Braces size={17} /> Salvar rascunho
              </Button>
              <Button onClick={resetSchema} type="button" variant="ghost">
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <div className="metadata-studio__workspace">
        <aside className="metadata-entity-rail">
          <div className="metadata-rail-heading">
            <span>Entidades</span>
            <strong>{entities.data?.length ?? 0}</strong>
          </div>
          {entities.isLoading ? <p>Carregando modelos…</p> : null}
          {entities.data?.length === 0 ? (
            <div className="metadata-empty-rail">
              <Database size={24} />
              <strong>Nenhum modelo ainda</strong>
              <span>Crie a primeira entidade da empresa.</span>
            </div>
          ) : null}
          {entities.data?.map((entity) => (
            <button
              className={`metadata-entity-button ${entity.id === selectedId ? "is-active" : ""}`}
              key={entity.id}
              onClick={() => {
                setSelectedId(entity.id);
                setEditingRecord(null);
                setRecordValues({});
              }}
              type="button"
            >
              <span className="metadata-entity-icon">
                <Database size={17} />
              </span>
              <span>
                <strong>{entity.label}</strong>
                <small>
                  {entity.key} · v{entity.current_version}
                </small>
              </span>
              <span
                className={`metadata-status metadata-status--${entity.status}`}
              >
                {statusLabel(entity.status)}
              </span>
            </button>
          ))}
        </aside>

        <section className="metadata-workbench">
          {!selected ? (
            <div className="metadata-workbench-empty">
              <Layers3 size={34} />
              <h2>Selecione ou crie uma entidade</h2>
              <p>O contrato, as versões e os registros aparecerão aqui.</p>
            </div>
          ) : (
            <>
              <Card className="metadata-definition-card">
                <div className="metadata-card-heading">
                  <div>
                    <span className="eyebrow">{selected.key}</span>
                    <h2>{selected.plural_label}</h2>
                    <p>{selected.description || "Sem descrição cadastrada."}</p>
                  </div>
                  <div className="metadata-version-stamp">
                    <span>Versão atual</span>
                    <strong>{selected.version.version}</strong>
                    <small>{statusLabel(selected.version.status)}</small>
                  </div>
                </div>
                <div className="metadata-contract-strip">
                  <span>
                    <ShieldCheck size={16} /> {selected.version.fields.length}{" "}
                    campos
                  </span>
                  <span>
                    <FileCheck2 size={16} /> checksum{" "}
                    {selected.version.schema_checksum.slice(0, 10)}
                  </span>
                  <span>
                    <Layers3 size={16} /> publicada v
                    {selected.published_version ?? "—"}
                  </span>
                </div>
                <div className="metadata-field-catalog">
                  {selected.version.fields.map((field) => (
                    <div key={field.id}>
                      <span className="metadata-field-type">
                        {field.data_type}
                      </span>
                      <strong>{field.label}</strong>
                      <small>{field.key}</small>
                      <span>{field.required ? "Obrigatório" : "Opcional"}</span>
                    </div>
                  ))}
                </div>
                <div className="metadata-lifecycle-actions">
                  {selected.version.status === "draft" && canConfigure ? (
                    <>
                      <Button
                        onClick={() => loadSchema(selected)}
                        variant="ghost"
                      >
                        <Pencil size={16} /> Editar schema
                      </Button>
                      <Button
                        disabled={designOpen || saveDesign.isPending}
                        loading={validateSchema.isPending}
                        onClick={() => validateSchema.mutate()}
                      >
                        <CheckCircle2 size={16} /> Validar versão
                      </Button>
                    </>
                  ) : null}
                  {selected.version.status === "validated" && canPublish ? (
                    <Button
                      loading={publishSchema.isPending}
                      onClick={() => publishSchema.mutate()}
                    >
                      <Rocket size={16} /> Publicar versão
                    </Button>
                  ) : null}
                  {selected.version.status === "published" && canConfigure ? (
                    <Button
                      loading={createVersion.isPending}
                      onClick={() => createVersion.mutate()}
                    >
                      <Layers3 size={16} /> Criar nova versão
                    </Button>
                  ) : null}
                </div>
              </Card>

              <Card className="metadata-design-card">
                <div className="metadata-card-heading">
                  <div>
                    <span className="eyebrow">Experiência configurável</span>
                    <h2>Layout, lista e regras</h2>
                    <p>
                      A mesma versão orienta o formulário, a visualização e as
                      validações executadas pela API.
                    </p>
                  </div>
                  {selected.version.status === "draft" && canConfigure ? (
                    <Button
                      onClick={() => setDesignOpen((current) => !current)}
                      variant="ghost"
                    >
                      <LayoutTemplate size={16} /> Configurar experiência
                    </Button>
                  ) : null}
                </div>
                <div className="metadata-design-summary">
                  <span>
                    <LayoutTemplate size={16} />
                    {design.data?.layouts.find((item) => item.is_default)
                      ?.label ?? "Formulário principal"}
                  </span>
                  <span>
                    <ListChecks size={16} />
                    {design.data?.views.find((item) => item.is_default)
                      ?.label ?? "Lista principal"}
                  </span>
                  <span>
                    <ShieldCheck size={16} />
                    {design.data?.validation_rules.length ?? 0} regras ativas
                  </span>
                  <span>
                    <Network size={16} />
                    {design.data?.relationships.length ?? 0} relacionamentos
                  </span>
                  <span>
                    <Calculator size={16} />
                    {design.data?.formulas.length ?? 0} formulas
                  </span>
                  <span>
                    <Tags size={16} />
                    {design.data?.record_types.length ?? 0} tipos
                  </span>
                </div>
                {designOpen ? (
                  <form
                    className="metadata-design-form"
                    onSubmit={submitDesign}
                  >
                    <div className="metadata-design-names">
                      <label>
                        <span>Nome do formulário</span>
                        <input
                          onChange={(event) =>
                            setLayoutLabel(event.target.value)
                          }
                          required
                          value={layoutLabel}
                        />
                      </label>
                      <label>
                        <span>Título da seção</span>
                        <input
                          onChange={(event) =>
                            setSectionLabel(event.target.value)
                          }
                          required
                          value={sectionLabel}
                        />
                      </label>
                    </div>
                    <section className="metadata-view-builder">
                      <div className="metadata-rule-heading">
                        <div>
                          <strong>Visualizações da lista</strong>
                          <small>
                            Colunas, filtros e ordenação são persistidos na
                            versão.
                          </small>
                        </div>
                        <Button
                          onClick={() => {
                            const next = blankView(
                              views.length,
                              selectedFields[0]?.key ?? "",
                            );
                            setViews((current) => [...current, next]);
                            setEditingViewKey(next.key);
                          }}
                          type="button"
                          variant="ghost"
                        >
                          <Plus size={16} /> Nova visualização
                        </Button>
                      </div>
                      {editingView ? (
                        <>
                          <div className="metadata-view-toolbar">
                            <label>
                              <span>Editar visualização</span>
                              <select
                                onChange={(event) =>
                                  setEditingViewKey(event.target.value)
                                }
                                value={editingView.key}
                              >
                                {views.map((view) => (
                                  <option key={view.key} value={view.key}>
                                    {view.label}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              <span>Nome da visualização</span>
                              <input
                                onChange={(event) =>
                                  updateEditingView((view) => ({
                                    ...view,
                                    label: event.target.value,
                                  }))
                                }
                                required
                                value={editingView.label}
                              />
                            </label>
                            <label className="metadata-inline-check">
                              <input
                                checked={editingView.is_default}
                                onChange={() =>
                                  setViews((current) =>
                                    current.map((view) => ({
                                      ...view,
                                      is_default: view.key === editingView.key,
                                    })),
                                  )
                                }
                                type="checkbox"
                              />
                              Visualização padrão
                            </label>
                            <button
                              aria-label="Excluir visualização"
                              className="metadata-icon-button"
                              disabled={
                                editingView.is_default || views.length === 1
                              }
                              onClick={() => {
                                const remaining = views.filter(
                                  (view) => view.key !== editingView.key,
                                );
                                setViews(remaining);
                                setEditingViewKey(remaining[0]?.key ?? null);
                              }}
                              type="button"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                          <fieldset className="metadata-view-columns">
                            <legend>Colunas visíveis</legend>
                            {selectedFields.map((field) => (
                              <label
                                key={`view-${editingView.key}-${field.id}`}
                              >
                                <input
                                  checked={editingView.columns.includes(
                                    field.key,
                                  )}
                                  onChange={(event) =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      columns: event.target.checked
                                        ? [...view.columns, field.key]
                                        : view.columns.filter(
                                            (key) => key !== field.key,
                                          ),
                                    }))
                                  }
                                  type="checkbox"
                                />
                                {field.label}
                              </label>
                            ))}
                          </fieldset>
                          <div className="metadata-view-section-heading">
                            <strong>
                              <Filter size={15} /> Filtros persistentes
                            </strong>
                            <button
                              onClick={() =>
                                updateEditingView((view) => ({
                                  ...view,
                                  filters: [
                                    ...view.filters,
                                    {
                                      field_key: selectedFields[0]?.key ?? "",
                                      operator: "is_not_empty",
                                      value: null,
                                    },
                                  ],
                                }))
                              }
                              type="button"
                            >
                              <Plus size={14} /> Adicionar filtro
                            </button>
                          </div>
                          <div className="metadata-view-rules">
                            {editingView.filters.map((filter, index) => (
                              <div
                                className="metadata-view-rule"
                                key={`${filter.field_key}-${index}`}
                              >
                                <select
                                  aria-label={`Campo do filtro ${index + 1}`}
                                  onChange={(event) =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      filters: view.filters.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                field_key: event.target.value,
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  value={filter.field_key}
                                >
                                  {selectedFields.map((field) => (
                                    <option key={field.id} value={field.key}>
                                      {field.label}
                                    </option>
                                  ))}
                                </select>
                                <select
                                  aria-label={`Operador do filtro ${index + 1}`}
                                  onChange={(event) =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      filters: view.filters.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                operator: event.target
                                                  .value as MetadataComparisonOperator,
                                                value:
                                                  event.target.value.startsWith(
                                                    "is_",
                                                  )
                                                    ? null
                                                    : item.value,
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  value={filter.operator}
                                >
                                  {RULE_OPERATORS.map((operator) => (
                                    <option
                                      key={operator.value}
                                      value={operator.value}
                                    >
                                      {operator.label}
                                    </option>
                                  ))}
                                </select>
                                <input
                                  aria-label={`Valor do filtro ${index + 1}`}
                                  disabled={filter.operator.startsWith("is_")}
                                  onChange={(event) =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      filters: view.filters.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                value: event.target.value,
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  placeholder="Valor"
                                  value={String(filter.value ?? "")}
                                />
                                <button
                                  aria-label={`Excluir filtro ${index + 1}`}
                                  onClick={() =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      filters: view.filters.filter(
                                        (_, itemIndex) => itemIndex !== index,
                                      ),
                                    }))
                                  }
                                  type="button"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            ))}
                          </div>
                          <div className="metadata-view-section-heading">
                            <strong>Ordenação</strong>
                            <button
                              disabled={editingView.sorting.length >= 5}
                              onClick={() =>
                                updateEditingView((view) => ({
                                  ...view,
                                  sorting: [
                                    ...view.sorting,
                                    {
                                      field_key: selectedFields[0]?.key ?? "",
                                      direction: "asc",
                                    },
                                  ],
                                }))
                              }
                              type="button"
                            >
                              <Plus size={14} /> Adicionar ordem
                            </button>
                          </div>
                          <div className="metadata-view-rules">
                            {editingView.sorting.map((sorting, index) => (
                              <div
                                className="metadata-view-rule metadata-view-rule--sort"
                                key={`${sorting.field_key}-${index}`}
                              >
                                <select
                                  aria-label={`Campo da ordenação ${index + 1}`}
                                  onChange={(event) =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      sorting: view.sorting.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                field_key: event.target.value,
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  value={sorting.field_key}
                                >
                                  {selectedFields.map((field) => (
                                    <option key={field.id} value={field.key}>
                                      {field.label}
                                    </option>
                                  ))}
                                </select>
                                <select
                                  aria-label={`Direção da ordenação ${index + 1}`}
                                  onChange={(event) =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      sorting: view.sorting.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                direction: event.target
                                                  .value as "asc" | "desc",
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  value={sorting.direction}
                                >
                                  <option value="asc">Crescente</option>
                                  <option value="desc">Decrescente</option>
                                </select>
                                <button
                                  aria-label={`Excluir ordenação ${index + 1}`}
                                  onClick={() =>
                                    updateEditingView((view) => ({
                                      ...view,
                                      sorting: view.sorting.filter(
                                        (_, itemIndex) => itemIndex !== index,
                                      ),
                                    }))
                                  }
                                  type="button"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : null}
                    </section>
                    <div className="metadata-field-selection">
                      <fieldset>
                        <legend>Campos e ordem do formulário</legend>
                        {selectedFields.map((field) => (
                          <label key={`layout-${field.id}`}>
                            <input
                              checked={layoutFieldKeys.includes(field.key)}
                              onChange={(event) =>
                                setLayoutFieldKeys((current) =>
                                  event.target.checked
                                    ? [...current, field.key]
                                    : current.filter(
                                        (key) => key !== field.key,
                                      ),
                                )
                              }
                              type="checkbox"
                            />
                            {field.label}
                          </label>
                        ))}
                      </fieldset>
                    </div>
                    <div className="metadata-rule-heading">
                      <div>
                        <strong>Regras de validação</strong>
                        <small>
                          Operadores seguros, sem código executável.
                        </small>
                      </div>
                      <Button
                        onClick={() =>
                          setValidationRules((current) => [
                            ...current,
                            blankRule(
                              current.length,
                              selectedFields[0]?.key ?? "",
                            ),
                          ])
                        }
                        type="button"
                        variant="ghost"
                      >
                        <Plus size={16} /> Adicionar regra
                      </Button>
                    </div>
                    <div className="metadata-rule-stack">
                      {validationRules.map((rule, index) => (
                        <div className="metadata-rule-row" key={rule.key}>
                          <label>
                            <span>Nome da regra</span>
                            <input
                              onChange={(event) =>
                                setValidationRules((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, label: event.target.value }
                                      : item,
                                  ),
                                )
                              }
                              required
                              value={rule.label}
                            />
                          </label>
                          <label>
                            <span>Campo</span>
                            <select
                              onChange={(event) =>
                                setValidationRules((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? {
                                          ...item,
                                          field_key: event.target.value,
                                        }
                                      : item,
                                  ),
                                )
                              }
                              value={rule.field_key}
                            >
                              {selectedFields.map((field) => (
                                <option key={field.id} value={field.key}>
                                  {field.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>Condição</span>
                            <select
                              onChange={(event) =>
                                setValidationRules((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? {
                                          ...item,
                                          operator: event.target
                                            .value as MetadataComparisonOperator,
                                        }
                                      : item,
                                  ),
                                )
                              }
                              value={rule.operator}
                            >
                              {RULE_OPERATORS.map((operator) => (
                                <option
                                  key={operator.value}
                                  value={operator.value}
                                >
                                  {operator.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>Valor de comparação</span>
                            <input
                              disabled={rule.operator.startsWith("is_")}
                              onChange={(event) =>
                                setValidationRules((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? {
                                          ...item,
                                          comparison_value: event.target.value,
                                        }
                                      : item,
                                  ),
                                )
                              }
                              value={String(rule.comparison_value ?? "")}
                            />
                          </label>
                          <label className="metadata-rule-message">
                            <span>Mensagem mostrada ao usuário</span>
                            <input
                              onChange={(event) =>
                                setValidationRules((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, message: event.target.value }
                                      : item,
                                  ),
                                )
                              }
                              required
                              value={rule.message}
                            />
                          </label>
                          <button
                            aria-label={`Remover regra ${index + 1}`}
                            className="metadata-remove-field"
                            onClick={() =>
                              setValidationRules((current) =>
                                current.filter(
                                  (_, itemIndex) => itemIndex !== index,
                                ),
                              )
                            }
                            type="button"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      ))}
                    </div>
                    <div className="metadata-advanced-grid">
                      <section className="metadata-advanced-card">
                        <div className="metadata-rule-heading">
                          <div>
                            <strong>Tipos de registro</strong>
                            <small>Cada tipo usa seu proprio layout.</small>
                          </div>
                          <Button
                            onClick={() => {
                              const item = blankRecordType(recordTypes.length);
                              setRecordTypes((current) => [...current, item]);
                              setRecordTypeFields((current) => ({
                                ...current,
                                [item.key]: [...layoutFieldKeys],
                              }));
                            }}
                            type="button"
                            variant="ghost"
                          >
                            <Plus size={16} /> Adicionar tipo
                          </Button>
                        </div>
                        {recordTypes.map((recordType, index) => (
                          <div
                            className="metadata-advanced-row"
                            key={recordType.key}
                          >
                            <label>
                              <span>Nome do tipo</span>
                              <input
                                onChange={(event) =>
                                  setRecordTypes((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, label: event.target.value }
                                        : item,
                                    ),
                                  )
                                }
                                required
                                value={recordType.label}
                              />
                            </label>
                            <fieldset>
                              <legend>Campos deste layout</legend>
                              {selectedFields.map((field) => (
                                <label key={`${recordType.key}-${field.key}`}>
                                  <input
                                    checked={(recordType.is_default
                                      ? layoutFieldKeys
                                      : (recordTypeFields[recordType.key] ?? [])
                                    ).includes(field.key)}
                                    onChange={(event) => {
                                      if (recordType.is_default) {
                                        setLayoutFieldKeys((current) =>
                                          event.target.checked
                                            ? [...current, field.key]
                                            : current.filter(
                                                (key) => key !== field.key,
                                              ),
                                        );
                                      } else {
                                        setRecordTypeFields((current) => {
                                          const fieldsForType =
                                            current[recordType.key] ?? [];
                                          return {
                                            ...current,
                                            [recordType.key]: event.target
                                              .checked
                                              ? [...fieldsForType, field.key]
                                              : fieldsForType.filter(
                                                  (key) => key !== field.key,
                                                ),
                                          };
                                        });
                                      }
                                    }}
                                    type="checkbox"
                                  />
                                  {field.label}
                                </label>
                              ))}
                            </fieldset>
                            {!recordType.is_default ? (
                              <button
                                aria-label={`Remover tipo ${recordType.label || index + 1}`}
                                className="metadata-remove-field"
                                onClick={() =>
                                  setRecordTypes((current) =>
                                    current.filter(
                                      (_, itemIndex) => itemIndex !== index,
                                    ),
                                  )
                                }
                                type="button"
                              >
                                <Trash2 size={16} />
                              </button>
                            ) : null}
                          </div>
                        ))}
                      </section>

                      <section className="metadata-advanced-card">
                        <div className="metadata-rule-heading">
                          <div>
                            <strong>Relacionamentos</strong>
                            <small>
                              Referencias UUID validadas na mesma empresa.
                            </small>
                          </div>
                          <Button
                            onClick={() =>
                              setRelationships((current) => [
                                ...current,
                                blankRelationship(
                                  current.length,
                                  selectedFields.find(
                                    (field) => field.data_type === "uuid",
                                  )?.key ?? "",
                                  entities.data?.find(
                                    (item) => item.id !== selectedId,
                                  )?.id ??
                                    selectedId ??
                                    "",
                                ),
                              ])
                            }
                            type="button"
                            variant="ghost"
                          >
                            <Plus size={16} /> Adicionar relacao
                          </Button>
                        </div>
                        {relationships.map((relationship, index) => (
                          <div
                            className="metadata-advanced-row metadata-advanced-row--columns"
                            key={relationship.key}
                          >
                            <label>
                              <span>Nome</span>
                              <input
                                required
                                value={relationship.label}
                                onChange={(event) =>
                                  setRelationships((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, label: event.target.value }
                                        : item,
                                    ),
                                  )
                                }
                              />
                            </label>
                            <label>
                              <span>Campo UUID</span>
                              <select
                                value={relationship.source_field_key}
                                onChange={(event) =>
                                  setRelationships((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            source_field_key:
                                              event.target.value,
                                          }
                                        : item,
                                    ),
                                  )
                                }
                              >
                                {selectedFields
                                  .filter((field) => field.data_type === "uuid")
                                  .map((field) => (
                                    <option key={field.id} value={field.key}>
                                      {field.label}
                                    </option>
                                  ))}
                              </select>
                            </label>
                            <label>
                              <span>Entidade relacionada</span>
                              <select
                                value={relationship.target_definition_id}
                                onChange={(event) =>
                                  setRelationships((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            target_definition_id:
                                              event.target.value,
                                          }
                                        : item,
                                    ),
                                  )
                                }
                              >
                                {entities.data?.map((entity) => (
                                  <option key={entity.id} value={entity.id}>
                                    {entity.label}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              <span>Cardinalidade</span>
                              <select
                                value={relationship.relationship_type}
                                onChange={(event) =>
                                  setRelationships((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            relationship_type: event.target
                                              .value as MetadataRelationshipInput["relationship_type"],
                                          }
                                        : item,
                                    ),
                                  )
                                }
                              >
                                <option value="many_to_one">
                                  Muitos para um
                                </option>
                                <option value="one_to_one">Um para um</option>
                              </select>
                            </label>
                            <button
                              aria-label={`Remover relacionamento ${index + 1}`}
                              className="metadata-remove-field"
                              onClick={() =>
                                setRelationships((current) =>
                                  current.filter(
                                    (_, itemIndex) => itemIndex !== index,
                                  ),
                                )
                              }
                              type="button"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        ))}
                      </section>

                      <section className="metadata-advanced-card">
                        <div className="metadata-rule-heading">
                          <div>
                            <strong>Campos calculados</strong>
                            <small>
                              Operacoes deterministas, sem codigo executavel.
                            </small>
                          </div>
                          <Button
                            onClick={() =>
                              setFormulas((current) => [
                                ...current,
                                blankFormula(
                                  current.length,
                                  selectedFields[0]?.key ?? "",
                                ),
                              ])
                            }
                            type="button"
                            variant="ghost"
                          >
                            <Plus size={16} /> Adicionar formula
                          </Button>
                        </div>
                        {formulas.map((formula, index) => (
                          <div
                            className="metadata-advanced-row metadata-advanced-row--columns"
                            key={formula.key}
                          >
                            <label>
                              <span>Nome</span>
                              <input
                                required
                                value={formula.label}
                                onChange={(event) =>
                                  setFormulas((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? { ...item, label: event.target.value }
                                        : item,
                                    ),
                                  )
                                }
                              />
                            </label>
                            <label>
                              <span>Campo calculado</span>
                              <select
                                value={formula.target_field_key}
                                onChange={(event) =>
                                  setFormulas((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            target_field_key:
                                              event.target.value,
                                          }
                                        : item,
                                    ),
                                  )
                                }
                              >
                                {selectedFields.map((field) => (
                                  <option key={field.id} value={field.key}>
                                    {field.label}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              <span>Operacao</span>
                              <select
                                value={formula.expression.operator}
                                onChange={(event) =>
                                  setFormulas((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            expression: {
                                              ...item.expression,
                                              operator: event.target
                                                .value as MetadataFormulaInput["expression"]["operator"],
                                            },
                                          }
                                        : item,
                                    ),
                                  )
                                }
                              >
                                <option value="add">Somar</option>
                                <option value="subtract">Subtrair</option>
                                <option value="multiply">Multiplicar</option>
                                <option value="divide">Dividir</option>
                                <option value="concat">Concatenar</option>
                                <option value="coalesce">
                                  Primeiro preenchido
                                </option>
                              </select>
                            </label>
                            {[0, 1].map((operandIndex) => (
                              <label key={operandIndex}>
                                <span>
                                  {operandIndex === 0
                                    ? "Primeiro campo"
                                    : "Segundo campo"}
                                </span>
                                <select
                                  value={
                                    formula.expression.operands[operandIndex]
                                      ?.field_key ?? ""
                                  }
                                  onChange={(event) =>
                                    setFormulas((current) =>
                                      current.map((item, itemIndex) =>
                                        itemIndex === index
                                          ? {
                                              ...item,
                                              expression: {
                                                ...item.expression,
                                                operands:
                                                  item.expression.operands.map(
                                                    (
                                                      operand,
                                                      currentOperand,
                                                    ) =>
                                                      currentOperand ===
                                                      operandIndex
                                                        ? {
                                                            type: "field",
                                                            field_key:
                                                              event.target
                                                                .value,
                                                            value: null,
                                                          }
                                                        : operand,
                                                  ),
                                              },
                                            }
                                          : item,
                                      ),
                                    )
                                  }
                                >
                                  {selectedFields.map((field) => (
                                    <option key={field.id} value={field.key}>
                                      {field.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                            ))}
                            <button
                              aria-label={`Remover formula ${index + 1}`}
                              className="metadata-remove-field"
                              onClick={() =>
                                setFormulas((current) =>
                                  current.filter(
                                    (_, itemIndex) => itemIndex !== index,
                                  ),
                                )
                              }
                              type="button"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        ))}
                      </section>
                    </div>
                    <div className="metadata-form-actions">
                      <Button loading={saveDesign.isPending} type="submit">
                        <FileCheck2 size={16} /> Salvar experiência
                      </Button>
                      <Button
                        onClick={() => setDesignOpen(false)}
                        type="button"
                        variant="ghost"
                      >
                        Cancelar
                      </Button>
                    </div>
                  </form>
                ) : null}
              </Card>

              {selected.published_version ? (
                <div className="metadata-record-workspace">
                  <Card className="metadata-record-form-card">
                    <div className="metadata-card-heading">
                      <div>
                        <span className="eyebrow">
                          {editingRecord ? "Editar registro" : "Novo registro"}
                        </span>
                        <h2>{selected.label}</h2>
                      </div>
                      {editingRecord ? (
                        <button
                          aria-label="Cancelar edição"
                          className="metadata-icon-button"
                          onClick={() => {
                            setEditingRecord(null);
                            setRecordValues({});
                          }}
                          type="button"
                        >
                          <X size={18} />
                        </button>
                      ) : null}
                    </div>
                    {canCreateRecords || (editingRecord && canUpdateRecords) ? (
                      <form
                        className="metadata-record-form"
                        onSubmit={submitRecord}
                      >
                        {(design.data?.record_types.length ?? 0) > 1 ? (
                          <label>
                            <span>Tipo de registro</span>
                            <select
                              value={recordTypeKey ?? ""}
                              onChange={(event) =>
                                setRecordTypeKey(event.target.value)
                              }
                            >
                              {design.data?.record_types
                                .filter((item) => item.active)
                                .map((item) => (
                                  <option key={item.key} value={item.key}>
                                    {item.label}
                                  </option>
                                ))}
                            </select>
                          </label>
                        ) : null}
                        {runtimeFields
                          .filter((field) => !formulaTargetKeys.has(field.key))
                          .map((field) => (
                            <label key={field.id}>
                              <span>
                                {field.label}
                                {field.required ? <b> obrigatório</b> : null}
                              </span>
                              {field.data_type === "boolean" ? (
                                <input
                                  checked={Boolean(recordValues[field.key])}
                                  onChange={(event) =>
                                    setRecordValues((current) => ({
                                      ...current,
                                      [field.key]: event.target.checked,
                                    }))
                                  }
                                  type="checkbox"
                                />
                              ) : field.data_type === "long_text" ||
                                field.data_type === "json" ? (
                                <textarea
                                  onChange={(event) =>
                                    setRecordValues((current) => ({
                                      ...current,
                                      [field.key]: event.target.value,
                                    }))
                                  }
                                  placeholder={
                                    field.data_type === "json"
                                      ? '{"chave":"valor"}'
                                      : "Digite o conteúdo"
                                  }
                                  required={field.required}
                                  rows={field.data_type === "json" ? 5 : 3}
                                  value={String(recordValues[field.key] ?? "")}
                                />
                              ) : (
                                <input
                                  onChange={(event) =>
                                    setRecordValues((current) => ({
                                      ...current,
                                      [field.key]: event.target.value,
                                    }))
                                  }
                                  required={field.required}
                                  step={
                                    field.data_type === "decimal"
                                      ? "any"
                                      : undefined
                                  }
                                  type={inputTypeForMetadataField(
                                    field.data_type,
                                  )}
                                  value={String(recordValues[field.key] ?? "")}
                                />
                              )}
                            </label>
                          ))}
                        <Button
                          loading={
                            createRecord.isPending || updateRecord.isPending
                          }
                          type="submit"
                        >
                          {editingRecord ? (
                            <Pencil size={16} />
                          ) : (
                            <Plus size={16} />
                          )}
                          {editingRecord
                            ? "Salvar alteração"
                            : `Criar ${selected.label}`}
                        </Button>
                      </form>
                    ) : (
                      <p>
                        Você possui acesso de consulta, sem permissão para
                        gravar.
                      </p>
                    )}
                  </Card>

                  <Card className="metadata-record-list-card">
                    <div className="metadata-card-heading">
                      <div>
                        <span className="eyebrow">Dados publicados</span>
                        <h2>{selected.plural_label}</h2>
                      </div>
                      <div className="metadata-record-list-tools">
                        {(design.data?.views.length ?? 0) > 0 &&
                        selected.version.status === "published" ? (
                          <label>
                            <span>Visualização</span>
                            <select
                              aria-label="Visualização de registros"
                              onChange={(event) => {
                                setActiveViewKey(event.target.value);
                                setRecordPage(1);
                              }}
                              value={activeViewKey ?? ""}
                            >
                              {design.data?.views.map((view) => (
                                <option key={view.key} value={view.key}>
                                  {view.label}
                                </option>
                              ))}
                            </select>
                          </label>
                        ) : null}
                        <span className="metadata-record-count">
                          {records.data?.total ?? 0} registros
                        </span>
                      </div>
                    </div>
                    {records.isLoading ? <p>Carregando registros…</p> : null}
                    {records.data?.items.length === 0 ? (
                      <div className="metadata-record-empty">
                        <Database size={25} />
                        <strong>Nenhum registro</strong>
                        <span>Use o formulário para começar.</span>
                      </div>
                    ) : null}
                    <div className="metadata-record-table" role="table">
                      {records.data?.items.map((record) => (
                        <article key={record.id} role="row">
                          <div className="metadata-record-primary">
                            <strong>
                              {primaryField &&
                              record.values[primaryField.key] !== undefined
                                ? displayMetadataValue(
                                    record.values[primaryField.key],
                                  )
                                : `Registro ${record.id.slice(0, 8)}`}
                            </strong>
                            <small>
                              v{record.record_version} · schema{" "}
                              {record.schema_version}
                            </small>
                          </div>
                          <dl>
                            {visibleFields
                              .filter(
                                (field) => field.key !== primaryField?.key,
                              )
                              .map((field) => (
                                <div key={field.id}>
                                  <dt>{field.label}</dt>
                                  <dd>
                                    {record.masked_fields.includes(field.key)
                                      ? "Protegido"
                                      : record.values[field.key] === undefined
                                        ? "—"
                                        : displayMetadataValue(
                                            record.values[field.key],
                                          )}
                                  </dd>
                                </div>
                              ))}
                          </dl>
                          <div className="metadata-record-actions">
                            {canUpdateRecords ? (
                              <button
                                onClick={() => editRecord(record)}
                                type="button"
                              >
                                <Pencil size={15} /> Editar
                              </button>
                            ) : null}
                            {canDeleteRecords ? (
                              <button
                                className="is-danger"
                                disabled={deleteRecord.isPending}
                                onClick={() => deleteRecord.mutate(record)}
                                type="button"
                              >
                                <Trash2 size={15} /> Excluir
                              </button>
                            ) : null}
                          </div>
                        </article>
                      ))}
                    </div>
                    {(records.data?.pages ?? 0) > 1 ? (
                      <div className="metadata-pagination">
                        <button
                          disabled={recordPage <= 1 || records.isFetching}
                          onClick={() =>
                            setRecordPage((current) => current - 1)
                          }
                          type="button"
                        >
                          <ChevronLeft size={16} /> Anterior
                        </button>
                        <span>
                          Página {records.data?.page ?? recordPage} de{" "}
                          {records.data?.pages}
                        </span>
                        <button
                          disabled={
                            recordPage >= (records.data?.pages ?? 1) ||
                            records.isFetching
                          }
                          onClick={() =>
                            setRecordPage((current) => current + 1)
                          }
                          type="button"
                        >
                          Próxima <ChevronRight size={16} />
                        </button>
                      </div>
                    ) : null}
                  </Card>
                </div>
              ) : (
                <div className="metadata-publish-callout">
                  <Rocket size={24} />
                  <div>
                    <strong>Publique o primeiro schema</strong>
                    <span>
                      Os formulários e registros serão liberados depois da
                      publicação.
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
