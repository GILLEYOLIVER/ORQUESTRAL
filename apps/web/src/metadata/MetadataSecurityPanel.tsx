import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Share2, ShieldCheck, Trash2, UserRound } from "lucide-react";
import type {
  CompanyUserResponse,
  RoleResponse,
} from "@orkestral/shared-types";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";

type SubjectType = "user" | "role";
type RecordScope = "all" | "owned" | "owned_shared";

type EntityRule = {
  id?: string;
  subject_type: SubjectType;
  subject_id: string;
  can_view: boolean;
  can_create: boolean;
  can_update: boolean;
  can_delete: boolean;
  can_export: boolean;
  record_scope: RecordScope;
};

type FieldRule = {
  id?: string;
  field_key: string;
  subject_type: SubjectType;
  subject_id: string;
  can_view: boolean;
  can_edit: boolean;
};

type SecurityConfiguration = {
  definition_id: string;
  configured: boolean;
  entity_rules: EntityRule[];
  field_rules: FieldRule[];
};

type RecordShare = {
  id: string;
  record_id: string;
  subject_type: SubjectType;
  subject_id: string;
  can_view: boolean;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
};

type Subject = {
  key: string;
  type: SubjectType;
  id: string;
  label: string;
};

type Props = {
  definitionId: string;
  fields: Array<{ key: string; label: string }>;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof ApiClientError ? caught.message : fallback;
}

export function MetadataSecurityPanel({ definitionId, fields }: Props) {
  const queryClient = useQueryClient();
  const [entityRules, setEntityRules] = useState<EntityRule[]>([]);
  const [fieldRules, setFieldRules] = useState<FieldRule[]>([]);
  const [activeSubject, setActiveSubject] = useState("");
  const [recordId, setRecordId] = useState("");
  const [shareCanEdit, setShareCanEdit] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const security = useQuery({
    queryKey: ["metadata-security", definitionId],
    queryFn: () =>
      request<SecurityConfiguration>(`/metadata/entities/${definitionId}/security`),
  });
  const users = useQuery({
    queryKey: ["company-users"],
    queryFn: () => request<CompanyUserResponse[]>("/company/users"),
  });
  const roles = useQuery({
    queryKey: ["authorization-roles"],
    queryFn: () => request<RoleResponse[]>("/authorization/roles"),
  });
  const subjects = useMemo<Subject[]>(
    () => [
      ...(users.data ?? []).map((user) => ({
        key: `user:${user.user_id}`,
        type: "user" as const,
        id: user.user_id,
        label: `${user.name} (${user.email})`,
      })),
      ...(roles.data ?? []).map((role) => ({
        key: `role:${role.id}`,
        type: "role" as const,
        id: role.id,
        label: `Papel: ${role.name}`,
      })),
    ],
    [roles.data, users.data],
  );
  const subjectLabels = useMemo(
    () => new Map(subjects.map((subject) => [subject.key, subject.label])),
    [subjects],
  );

  useEffect(() => {
    if (!security.data) return;
    setEntityRules(security.data.entity_rules);
    setFieldRules(security.data.field_rules);
  }, [security.data]);

  useEffect(() => {
    if (!activeSubject && subjects[0]) setActiveSubject(subjects[0].key);
  }, [activeSubject, subjects]);

  const selectedSubject = subjects.find((subject) => subject.key === activeSubject);
  const selectedRule = selectedSubject
    ? entityRules.find(
        (rule) =>
          rule.subject_type === selectedSubject.type &&
          rule.subject_id === selectedSubject.id,
      )
    : undefined;
  const validRecordId = UUID_PATTERN.test(recordId.trim());
  const shares = useQuery({
    queryKey: ["metadata-record-shares", definitionId, recordId.trim()],
    queryFn: () =>
      request<RecordShare[]>(
        `/metadata/entities/${definitionId}/records/${recordId.trim()}/shares`,
      ),
    enabled: validRecordId,
  });

  const save = useMutation({
    mutationFn: () =>
      request<SecurityConfiguration>(`/metadata/entities/${definitionId}/security`, {
        method: "PUT",
        body: {
          entity_rules: entityRules.map((rule) => ({
            subject_type: rule.subject_type,
            subject_id: rule.subject_id,
            can_view: rule.can_view,
            can_create: rule.can_create,
            can_update: rule.can_update,
            can_delete: rule.can_delete,
            can_export: rule.can_export,
            record_scope: rule.record_scope,
          })),
          field_rules: fieldRules.map((rule) => ({
            field_key: rule.field_key,
            subject_type: rule.subject_type,
            subject_id: rule.subject_id,
            can_view: rule.can_view,
            can_edit: rule.can_edit,
          })),
        },
      }),
    onSuccess: async (result) => {
      setError(null);
      setEntityRules(result.entity_rules);
      setFieldRules(result.field_rules);
      await queryClient.invalidateQueries({
        queryKey: ["metadata-security", definitionId],
      });
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Falha ao salvar as regras de acesso.")),
  });

  const share = useMutation({
    mutationFn: () => {
      if (!selectedSubject || !validRecordId) throw new Error("Dados incompletos");
      return request<RecordShare>(
        `/metadata/entities/${definitionId}/records/${recordId.trim()}/shares`,
        {
          method: "POST",
          body: {
            subject_type: selectedSubject.type,
            subject_id: selectedSubject.id,
            can_view: true,
            can_edit: shareCanEdit,
          },
        },
      );
    },
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({
        queryKey: ["metadata-record-shares", definitionId, recordId.trim()],
      });
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Falha ao compartilhar o registro.")),
  });

  const revoke = useMutation({
    mutationFn: (shareId: string) =>
      request<void>(
        `/metadata/entities/${definitionId}/records/${recordId.trim()}/shares/${shareId}`,
        { method: "DELETE" },
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["metadata-record-shares", definitionId, recordId.trim()],
      }),
  });

  function addSubjectRule() {
    if (!selectedSubject || selectedRule) return;
    setEntityRules((current) => [
      ...current,
      {
        subject_type: selectedSubject.type,
        subject_id: selectedSubject.id,
        can_view: true,
        can_create: false,
        can_update: false,
        can_delete: false,
        can_export: false,
        record_scope: "owned",
      },
    ]);
  }

  function updateEntityRule(change: Partial<EntityRule>) {
    if (!selectedSubject) return;
    setEntityRules((current) =>
      current.map((rule) =>
        rule.subject_type === selectedSubject.type &&
        rule.subject_id === selectedSubject.id
          ? { ...rule, ...change }
          : rule,
      ),
    );
  }

  function removeSubjectRule() {
    if (!selectedSubject) return;
    setEntityRules((current) =>
      current.filter(
        (rule) =>
          rule.subject_type !== selectedSubject.type ||
          rule.subject_id !== selectedSubject.id,
      ),
    );
    setFieldRules((current) =>
      current.filter(
        (rule) =>
          rule.subject_type !== selectedSubject.type ||
          rule.subject_id !== selectedSubject.id,
      ),
    );
  }

  function updateFieldRule(fieldKey: string, change: Partial<FieldRule>) {
    if (!selectedSubject) return;
    setFieldRules((current) => {
      const existing = current.find(
        (rule) =>
          rule.field_key === fieldKey &&
          rule.subject_type === selectedSubject.type &&
          rule.subject_id === selectedSubject.id,
      );
      if (!existing) {
        return [
          ...current,
          {
            field_key: fieldKey,
            subject_type: selectedSubject.type,
            subject_id: selectedSubject.id,
            can_view: true,
            can_edit: false,
            ...change,
          },
        ];
      }
      return current.map((rule) =>
        rule === existing ? { ...rule, ...change } : rule,
      );
    });
  }

  function removeFieldRule(fieldKey: string) {
    if (!selectedSubject) return;
    setFieldRules((current) =>
      current.filter(
        (rule) =>
          rule.field_key !== fieldKey ||
          rule.subject_type !== selectedSubject.type ||
          rule.subject_id !== selectedSubject.id,
      ),
    );
  }

  if (security.isLoading || users.isLoading || roles.isLoading) {
    return <Card>Carregando controles de acesso...</Card>;
  }

  return (
    <Card className="metadata-security-card">
      <div className="metadata-card-heading">
        <div>
          <span className="eyebrow">Segurança empresarial</span>
          <h2>Acesso por entidade, campo e registro</h2>
          <p>
            Defina o menor privilégio. Proprietários da empresa preservam acesso de
            recuperação administrativa.
          </p>
        </div>
        <ShieldCheck size={28} />
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="metadata-security-subject">
        <label>
          Usuário ou papel
          <select value={activeSubject} onChange={(event) => setActiveSubject(event.target.value)}>
            {subjects.map((subject) => (
              <option key={subject.key} value={subject.key}>
                {subject.label}
              </option>
            ))}
          </select>
        </label>
        {!selectedRule ? (
          <Button disabled={!selectedSubject} onClick={addSubjectRule} variant="ghost">
            <UserRound size={16} /> Criar regra
          </Button>
        ) : (
          <Button onClick={removeSubjectRule} variant="ghost">
            <Trash2 size={16} /> Remover regra
          </Button>
        )}
      </div>
      {selectedRule ? (
        <>
          <div className="metadata-security-actions">
            {(
              [
                ["can_view", "Visualizar"],
                ["can_create", "Criar"],
                ["can_update", "Editar"],
                ["can_delete", "Excluir"],
                ["can_export", "Exportar"],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                <input
                  checked={selectedRule[key]}
                  onChange={(event) => updateEntityRule({ [key]: event.target.checked })}
                  type="checkbox"
                />
                {label}
              </label>
            ))}
            <label>
              Registros acessíveis
              <select
                value={selectedRule.record_scope}
                onChange={(event) =>
                  updateEntityRule({ record_scope: event.target.value as RecordScope })
                }
              >
                <option value="owned">Somente próprios</option>
                <option value="owned_shared">Próprios e compartilhados</option>
                <option value="all">Todos da entidade</option>
              </select>
            </label>
          </div>
          <div className="metadata-security-fields">
            <div className="metadata-fields-heading">
              <div>
                <strong>Segurança dos campos</strong>
                <small>Sem regra específica, o campo herda o acesso da entidade.</small>
              </div>
            </div>
            {fields.map((field) => {
              const rule = fieldRules.find(
                (item) =>
                  item.field_key === field.key &&
                  item.subject_type === selectedSubject?.type &&
                  item.subject_id === selectedSubject.id,
              );
              return (
                <div className="metadata-security-field" key={field.key}>
                  <div>
                    <strong>{field.label}</strong>
                    <small>{field.key}</small>
                  </div>
                  <label>
                    <input
                      checked={Boolean(rule)}
                      onChange={(event) =>
                        event.target.checked
                          ? updateFieldRule(field.key, {})
                          : removeFieldRule(field.key)
                      }
                      type="checkbox"
                    />
                    Personalizar
                  </label>
                  <label>
                    <input
                      checked={rule?.can_view ?? true}
                      disabled={!rule}
                      onChange={(event) =>
                        updateFieldRule(field.key, {
                          can_view: event.target.checked,
                          can_edit: event.target.checked ? rule?.can_edit : false,
                        })
                      }
                      type="checkbox"
                    />
                    Ver
                  </label>
                  <label>
                    <input
                      checked={rule?.can_edit ?? false}
                      disabled={!rule || !rule.can_view}
                      onChange={(event) =>
                        updateFieldRule(field.key, { can_edit: event.target.checked })
                      }
                      type="checkbox"
                    />
                    Editar
                  </label>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <p className="metadata-package-empty">
          Selecione um usuário ou papel e crie a primeira regra. Sem regras, o
          comportamento compatível atual é preservado.
        </p>
      )}
      <div className="metadata-security-save">
        <Button loading={save.isPending} onClick={() => save.mutate()}>
          <Save size={16} /> Salvar política de acesso
        </Button>
      </div>
      <div className="metadata-record-sharing">
        <div>
          <strong>Compartilhar um registro específico</strong>
          <small>Use o identificador exibido no registro e o destinatário selecionado acima.</small>
        </div>
        <input
          aria-label="Identificador do registro"
          onChange={(event) => setRecordId(event.target.value)}
          placeholder="UUID do registro"
          value={recordId}
        />
        <label>
          <input
            checked={shareCanEdit}
            onChange={(event) => setShareCanEdit(event.target.checked)}
            type="checkbox"
          />
          Permitir edição
        </label>
        <Button
          disabled={!validRecordId || !selectedSubject}
          loading={share.isPending}
          onClick={() => share.mutate()}
          variant="ghost"
        >
          <Share2 size={16} /> Compartilhar
        </Button>
      </div>
      {validRecordId ? (
        <div className="metadata-share-list">
          {(shares.data ?? []).map((item) => (
            <div key={item.id}>
              <span>
                {subjectLabels.get(`${item.subject_type}:${item.subject_id}`) ?? item.subject_id}
              </span>
              <small>{item.can_edit ? "Leitura e edição" : "Somente leitura"}</small>
              <Button
                loading={revoke.isPending}
                onClick={() => revoke.mutate(item.id)}
                variant="ghost"
              >
                <Trash2 size={14} /> Revogar
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
