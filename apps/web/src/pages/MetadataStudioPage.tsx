import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Braces,
  CheckCircle2,
  CirclePlus,
  Database,
  FileCheck2,
  Layers3,
  Pencil,
  Plus,
  Rocket,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import {
  type MetadataDataType,
  type MetadataEntityDetail,
  type MetadataEntitySummary,
  type MetadataFieldInput,
  type MetadataRecordResponse,
  type MetadataValidationResponse,
  type MetadataValue,
  useMetadataEntities,
  useMetadataEntity,
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
  const records = useMetadataRecords(
    selectedId,
    Boolean(selected?.published_version),
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

  useEffect(() => {
    if (!selectedId && entities.data?.length) {
      setSelectedId(entities.data[0].id);
    }
  }, [entities.data, selectedId]);

  const refresh = (definitionId = selectedId) => {
    void queryClient.invalidateQueries({ queryKey: ["metadata-entities"] });
    void queryClient.invalidateQueries({
      queryKey: ["metadata-entity", definitionId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["metadata-records", definitionId],
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

  const createRecord = useMutation({
    mutationFn: (values: Record<string, MetadataValue>) =>
      request<MetadataRecordResponse>(
        `/metadata/entities/${selectedId}/records`,
        {
          method: "POST",
          body: { values, idempotency_key: crypto.randomUUID() },
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
          body: { values, expected_version: record.record_version },
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
    createRecord.error ??
    updateRecord.error ??
    deleteRecord.error;

  const selectedFields = useMemo(
    () => selected?.version.fields ?? [],
    [selected],
  );
  const primaryField = useMemo(
    () => selectedFields.find((field) => field.required) ?? selectedFields[0],
    [selectedFields],
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
        selectedFields.flatMap((field) => {
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
      setLocalError("Revise os campos estruturados. O JSON informado não é válido.");
    }
  };

  const editRecord = (record: MetadataRecordResponse) => {
    setEditingRecord(record);
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
          <Button
            onClick={() => {
              resetSchema();
              setSchemaOpen(true);
            }}
          >
            <CirclePlus size={18} /> Nova entidade
          </Button>
        </PermissionGuard>
      </header>

      {entities.isError || selectedQuery.isError || records.isError ? (
        <Alert variant="error">
          Não foi possível carregar todas as informações do Studio.
        </Alert>
      ) : null}
      {mutationError || localError ? (
        <Alert variant="error">
          {localError || errorMessage(mutationError)}
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
                <div className="metadata-field-row" key={`${field.key}-${index}`}>
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
              <span className={`metadata-status metadata-status--${entity.status}`}>
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
                    <ShieldCheck size={16} /> {selected.version.fields.length} campos
                  </span>
                  <span>
                    <FileCheck2 size={16} /> checksum {selected.version.schema_checksum.slice(0, 10)}
                  </span>
                  <span>
                    <Layers3 size={16} /> publicada v{selected.published_version ?? "—"}
                  </span>
                </div>
                <div className="metadata-field-catalog">
                  {selected.version.fields.map((field) => (
                    <div key={field.id}>
                      <span className="metadata-field-type">{field.data_type}</span>
                      <strong>{field.label}</strong>
                      <small>{field.key}</small>
                      <span>{field.required ? "Obrigatório" : "Opcional"}</span>
                    </div>
                  ))}
                </div>
                <div className="metadata-lifecycle-actions">
                  {selected.version.status === "draft" && canConfigure ? (
                    <>
                      <Button onClick={() => loadSchema(selected)} variant="ghost">
                        <Pencil size={16} /> Editar schema
                      </Button>
                      <Button
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
                      <form className="metadata-record-form" onSubmit={submitRecord}>
                        {selectedFields.map((field) => (
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
                            ) : field.data_type === "long_text" || field.data_type === "json" ? (
                              <textarea
                                onChange={(event) =>
                                  setRecordValues((current) => ({
                                    ...current,
                                    [field.key]: event.target.value,
                                  }))
                                }
                                placeholder={field.data_type === "json" ? '{"chave":"valor"}' : "Digite o conteúdo"}
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
                                step={field.data_type === "decimal" ? "any" : undefined}
                                type={inputTypeForMetadataField(field.data_type)}
                                value={String(recordValues[field.key] ?? "")}
                              />
                            )}
                          </label>
                        ))}
                        <Button
                          loading={createRecord.isPending || updateRecord.isPending}
                          type="submit"
                        >
                          {editingRecord ? <Pencil size={16} /> : <Plus size={16} />}
                          {editingRecord ? "Salvar alteração" : `Criar ${selected.label}`}
                        </Button>
                      </form>
                    ) : (
                      <p>Você possui acesso de consulta, sem permissão para gravar.</p>
                    )}
                  </Card>

                  <Card className="metadata-record-list-card">
                    <div className="metadata-card-heading">
                      <div>
                        <span className="eyebrow">Dados publicados</span>
                        <h2>{selected.plural_label}</h2>
                      </div>
                      <span className="metadata-record-count">
                        {records.data?.total ?? 0} registros
                      </span>
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
                              {primaryField && record.values[primaryField.key] !== undefined
                                ? displayMetadataValue(record.values[primaryField.key])
                                : `Registro ${record.id.slice(0, 8)}`}
                            </strong>
                            <small>v{record.record_version} · schema {record.schema_version}</small>
                          </div>
                          <dl>
                            {selectedFields
                              .filter((field) => field.key !== primaryField?.key)
                              .map((field) => (
                                <div key={field.id}>
                                  <dt>{field.label}</dt>
                                  <dd>
                                    {record.masked_fields.includes(field.key)
                                      ? "Protegido"
                                      : record.values[field.key] === undefined
                                        ? "—"
                                        : displayMetadataValue(record.values[field.key])}
                                  </dd>
                                </div>
                              ))}
                          </dl>
                          <div className="metadata-record-actions">
                            {canUpdateRecords ? (
                              <button onClick={() => editRecord(record)} type="button">
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
                  </Card>
                </div>
              ) : (
                <div className="metadata-publish-callout">
                  <Rocket size={24} />
                  <div>
                    <strong>Publique o primeiro schema</strong>
                    <span>Os formulários e registros serão liberados depois da publicação.</span>
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
