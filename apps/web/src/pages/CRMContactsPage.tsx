import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  ChevronLeft,
  ChevronRight,
  Database,
  Mail,
  Pencil,
  Phone,
  Plus,
  Search,
  ShieldCheck,
  Tag,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type {
  CRMContactPage,
  CRMContactResponse,
  CRMTagResponse,
} from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import { CRMPipelineView } from "./crm/CRMPipelineView";
import { SalesCatalogPanel } from "./crm/SalesCatalogPanel";
import { SalesIntelligencePanel } from "./crm/SalesIntelligencePanel";
import { SalesProspectingPanel } from "./crm/SalesProspectingPanel";

const contactSchema = z.object({
  name: z.string().min(2, "Informe o nome."),
  email: z
    .string()
    .refine(
      (value) => value === "" || z.email().safeParse(value).success,
      "Informe um e-mail válido.",
    ),
  phone: z.string().max(64),
  company_name: z.string().max(180),
  job_title: z.string().max(120),
  source: z.string().max(80),
  status: z.enum(["lead", "prospect", "customer", "inactive"]),
  tag_ids: z.array(z.string()),
});
type ContactFormValues = z.infer<typeof contactSchema>;

const statusLabels: Record<CRMContactResponse["status"], string> = {
  lead: "Lead",
  prospect: "Prospect",
  customer: "Cliente",
  inactive: "Inativo",
};

type Customer360 = {
  profile_id: string;
  display_name: string;
  profile_type: "person" | "organization";
  lifecycle_status: CRMContactResponse["status"];
  quality_score: number;
  quality_issues: string[];
  master_contact_id: string | null;
  linked_contact_ids: string[];
  duplicate_candidate_profile_ids: string[];
  identities: Array<{
    id: string;
    identity_type: "email" | "phone" | "external_id" | "document";
    display_hint: string;
    verified: boolean;
    source_code: string;
    source_name: string;
  }>;
  sources: Array<{
    id: string;
    code: string;
    name: string;
    mode: "system_of_record" | "copied" | "federated" | "cached";
    status: "active" | "paused" | "retired";
  }>;
  consents: Array<{
    id: string;
    purpose: string;
    channel: string;
    status: string;
    lawful_basis: string;
    captured_at: string;
  }>;
  opportunity_count: number;
  open_opportunity_value: string;
  recent_activities: Array<{
    id: string;
    activity_type: string;
    subject: string;
    occurred_at: string;
  }>;
};

function normalizedBody(values: ContactFormValues) {
  return {
    ...values,
    email: values.email || null,
    phone: values.phone || null,
    company_name: values.company_name || null,
    job_title: values.job_title || null,
    source: values.source || null,
  };
}

function ContactForm({
  contact,
  onClose,
  onSaved,
  tags,
}: {
  contact: CRMContactResponse | null;
  onClose: () => void;
  onSaved: (contact: CRMContactResponse) => void;
  tags: CRMTagResponse[];
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ContactFormValues>({
    defaultValues: {
      name: contact?.name ?? "",
      email: contact?.email ?? "",
      phone: contact?.phone ?? "",
      company_name: contact?.company_name ?? "",
      job_title: contact?.job_title ?? "",
      source: contact?.source ?? "",
      status: contact?.status ?? "lead",
      tag_ids: contact?.tags.map((tag) => tag.id) ?? [],
    },
    resolver: zodResolver(contactSchema),
  });
  const save = useMutation({
    mutationFn: (values: ContactFormValues) =>
      request<CRMContactResponse>(
        contact ? `/crm/contacts/${contact.id}` : "/crm/contacts",
        {
          method: contact ? "PATCH" : "POST",
          body: normalizedBody(values),
        },
      ),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["crm-contacts"] });
      onSaved(result);
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível salvar o contato.",
      ),
  });

  return (
    <Card
      className="crm-editor"
      eyebrow={contact ? "Editar contato" : "Novo contato"}
    >
      <div className="panel-heading">
        <div>
          <h2>{contact ? contact.name : "Cadastrar contato"}</h2>
          <p>Os dados serão salvos somente na empresa atual.</p>
        </div>
        <button
          aria-label="Fechar formulário"
          className="icon-button"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <form
        className="stack-form"
        noValidate
        onSubmit={(event) =>
          void handleSubmit((values) => save.mutate(values))(event)
        }
      >
        <div className="crm-form-grid">
          <TextField
            error={errors.name?.message}
            label="Nome"
            {...register("name")}
          />
          <TextField
            error={errors.email?.message}
            label="E-mail"
            type="email"
            {...register("email")}
          />
          <TextField label="Telefone" {...register("phone")} />
          <TextField label="Empresa" {...register("company_name")} />
          <TextField label="Cargo" {...register("job_title")} />
          <TextField
            label="Origem"
            placeholder="Indicação, site…"
            {...register("source")}
          />
          <label className="native-field">
            <span>Status</span>
            <select {...register("status")}>
              {Object.entries(statusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <fieldset className="tag-fieldset">
          <legend>Etiquetas</legend>
          {tags.length ? (
            tags.map((tag) => (
              <label className="tag-option" key={tag.id}>
                <input
                  type="checkbox"
                  value={tag.id}
                  {...register("tag_ids")}
                />
                <span>{tag.name}</span>
              </label>
            ))
          ) : (
            <span>Nenhuma etiqueta cadastrada.</span>
          )}
        </fieldset>
        <div className="form-actions">
          <Button loading={save.isPending} type="submit">
            Salvar contato
          </Button>
          <Button onClick={onClose} variant="ghost">
            Cancelar
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ContactDetails({
  contact,
  onClose,
  onDelete,
  onEdit,
}: {
  contact: CRMContactResponse;
  onClose: () => void;
  onDelete: () => void;
  onEdit: () => void;
}) {
  const queryClient = useQueryClient();
  const [consentPurpose, setConsentPurpose] = useState("service");
  const [consentChannel, setConsentChannel] = useState("all");
  const [consentStatus, setConsentStatus] = useState("granted");
  const customer360 = useQuery({
    queryKey: ["crm-customer-360", contact.id],
    queryFn: () =>
      request<Customer360>(`/crm/contacts/${contact.id}/customer-360`),
  });
  const recordConsent = useMutation({
    mutationFn: () =>
      request(`/crm/contacts/${contact.id}/consents`, {
        method: "POST",
        body: {
          purpose: consentPurpose,
          channel: consentChannel,
          status: consentStatus,
          lawful_basis:
            consentStatus === "granted" ? "consentimento" : "oposição do titular",
        },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["crm-customer-360", contact.id],
      }),
  });
  return (
    <Card className="crm-details" eyebrow="Detalhes do contato">
      <div className="panel-heading">
        <div>
          <h2>{contact.name}</h2>
          <span className={`status-chip status-chip--${contact.status}`}>
            {statusLabels[contact.status]}
          </span>
        </div>
        <button
          aria-label="Fechar detalhes"
          className="icon-button"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      <div className="contact-facts">
        <span>
          <Mail size={17} /> {contact.email ?? "E-mail não informado"}
        </span>
        <span>
          <Phone size={17} /> {contact.phone ?? "Telefone não informado"}
        </span>
        <span>
          <Building2 size={17} />{" "}
          {contact.company_name ?? "Empresa não informada"}
        </span>
        <span>
          <UserRound size={17} /> {contact.job_title ?? "Cargo não informado"}
        </span>
      </div>
      <div className="contact-tags">
        {contact.tags.map((tag) => (
          <span key={tag.id}>
            <Tag size={13} /> {tag.name}
          </span>
        ))}
      </div>
      <section className="customer-360">
        <div className="customer-360__heading">
          <div>
            <span className="eyebrow">VISÃO 360</span>
            <h3>Perfil canônico do cliente</h3>
          </div>
          <Database size={20} />
        </div>
        {customer360.isLoading ? <p>Consolidando dados autorizados…</p> : null}
        {customer360.isError ? (
          <Alert variant="error">Não foi possível consolidar a visão 360.</Alert>
        ) : null}
        {customer360.data ? (
          <>
            <div className="customer-360__metrics">
              <span>
                <strong>{customer360.data.quality_score}%</strong>
                Qualidade
              </span>
              <span>
                <strong>{customer360.data.linked_contact_ids.length}</strong>
                Cadastros ligados
              </span>
              <span>
                <strong>{customer360.data.opportunity_count}</strong>
                Oportunidades abertas
              </span>
            </div>
            {customer360.data.quality_issues.length ? (
              <small>
                Melhorar: {customer360.data.quality_issues.join(" · ")}
              </small>
            ) : (
              <small>Cadastro completo para ativação autorizada.</small>
            )}
            <div className="customer-360__section">
              <h4>
                <ShieldCheck size={16} /> Identidades protegidas
              </h4>
              {customer360.data.identities.map((identity) => (
                <span key={identity.id}>
                  {identity.identity_type}: {identity.display_hint} ·{" "}
                  {identity.source_name}
                </span>
              ))}
              {!customer360.data.identities.length ? (
                <span>Identidades serão indexadas na próxima atualização.</span>
              ) : null}
            </div>
            <div className="customer-360__section">
              <h4>
                <Activity size={16} /> Consentimentos
              </h4>
              {customer360.data.consents.slice(0, 5).map((consent) => (
                <span key={consent.id}>
                  {consent.purpose} · {consent.channel} · {consent.status}
                </span>
              ))}
              {!customer360.data.consents.length ? (
                <span>Nenhum consentimento registrado.</span>
              ) : null}
            </div>
            <PermissionGuard all={["crm.contacts.update"]}>
              <div className="customer-360__consent-form">
                <select
                  aria-label="Finalidade do consentimento"
                  onChange={(event) => setConsentPurpose(event.target.value)}
                  value={consentPurpose}
                >
                  <option value="service">Atendimento</option>
                  <option value="marketing">Marketing</option>
                  <option value="analytics">Analytics</option>
                  <option value="ai_processing">Processamento por IA</option>
                  <option value="data_sharing">Compartilhamento</option>
                </select>
                <select
                  aria-label="Canal do consentimento"
                  onChange={(event) => setConsentChannel(event.target.value)}
                  value={consentChannel}
                >
                  <option value="all">Todos os canais</option>
                  <option value="email">E-mail</option>
                  <option value="phone">Telefone</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="sms">SMS</option>
                  <option value="web">Web</option>
                </select>
                <select
                  aria-label="Decisão de consentimento"
                  onChange={(event) => setConsentStatus(event.target.value)}
                  value={consentStatus}
                >
                  <option value="granted">Concedido</option>
                  <option value="denied">Negado</option>
                  <option value="revoked">Revogado</option>
                </select>
                <Button
                  loading={recordConsent.isPending}
                  onClick={() => recordConsent.mutate()}
                  variant="secondary"
                >
                  Registrar decisão
                </Button>
              </div>
            </PermissionGuard>
          </>
        ) : null}
      </section>
      <div className="form-actions">
        <PermissionGuard all={["crm.contacts.update"]}>
          <Button onClick={onEdit} variant="secondary">
            <Pencil size={16} /> Editar
          </Button>
        </PermissionGuard>
        <PermissionGuard all={["crm.contacts.delete"]}>
          <Button onClick={onDelete} variant="ghost">
            <Trash2 size={16} /> Excluir
          </Button>
        </PermissionGuard>
      </div>
    </Card>
  );
}

export function CRMContactsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [sort, setSort] = useState("created_at:desc");
  const [selected, setSelected] = useState<CRMContactResponse | null>(null);
  const [editor, setEditor] = useState<"create" | "edit" | null>(null);
  const [tagName, setTagName] = useState("");

  const [sortBy, sortOrder] = sort.split(":");
  const contacts = useQuery({
    queryKey: ["crm-contacts", page, search, statusFilter, tagFilter, sort],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "10",
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (search) params.set("search", search);
      if (statusFilter) params.set("status", statusFilter);
      if (tagFilter) params.set("tag_id", tagFilter);
      return request<CRMContactPage>(`/crm/contacts?${params}`);
    },
  });
  const tags = useQuery({
    queryKey: ["crm-tags"],
    queryFn: () => request<CRMTagResponse[]>("/crm/tags"),
  });
  const createTag = useMutation({
    mutationFn: () =>
      request<CRMTagResponse>("/crm/tags", {
        method: "POST",
        body: { name: tagName },
      }),
    onSuccess: async () => {
      setTagName("");
      await queryClient.invalidateQueries({ queryKey: ["crm-tags"] });
    },
  });
  const remove = useMutation({
    mutationFn: (contactId: string) =>
      request<void>(`/crm/contacts/${contactId}`, { method: "DELETE" }),
    onSuccess: async () => {
      setSelected(null);
      await queryClient.invalidateQueries({ queryKey: ["crm-contacts"] });
    },
  });

  const setFilter = (setter: (value: string) => void, value: string) => {
    setter(value);
    setPage(1);
  };

  return (
    <div className="management-page crm-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">CRM e vendas</span>
          <h1>Relacionamentos comerciais</h1>
          <p>
            Conecte prospecção, contas, contatos, oportunidades, atividades e
            previsões de receita.
          </p>
        </div>
        <PermissionGuard all={["crm.contacts.create"]}>
          <Button
            onClick={() => {
              setSelected(null);
              setEditor("create");
            }}
          >
            <Plus size={17} /> Novo contato
          </Button>
        </PermissionGuard>
      </div>
      <SalesProspectingPanel />
      <SalesCatalogPanel />
      <SalesIntelligencePanel />
      <details className="crm-pipeline-disclosure" open>
        <summary>
          <span>Pipeline comercial</span>
          <small>
            Acompanhe oportunidades, valores, etapas e histórico de cada
            negociação.
          </small>
        </summary>
        <CRMPipelineView />
      </details>
      {contacts.isError ? (
        <Alert variant="error">
          {contacts.error instanceof ApiClientError
            ? contacts.error.message
            : "Não foi possível carregar os contatos."}
        </Alert>
      ) : null}
      <Card className="crm-filters" eyebrow="Pesquisa e filtros">
        <label className="search-field">
          <Search aria-hidden="true" size={17} />
          <input
            aria-label="Pesquisar contatos"
            onChange={(event) => setFilter(setSearch, event.target.value)}
            placeholder="Nome, e-mail, telefone ou empresa"
            type="search"
            value={search}
          />
        </label>
        <select
          aria-label="Filtrar por status"
          onChange={(event) => setFilter(setStatusFilter, event.target.value)}
          value={statusFilter}
        >
          <option value="">Todos os status</option>
          {Object.entries(statusLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar por etiqueta"
          onChange={(event) => setFilter(setTagFilter, event.target.value)}
          value={tagFilter}
        >
          <option value="">Todas as etiquetas</option>
          {tags.data?.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Ordenar contatos"
          onChange={(event) => setSort(event.target.value)}
          value={sort}
        >
          <option value="created_at:desc">Mais recentes</option>
          <option value="name:asc">Nome A–Z</option>
          <option value="company_name:asc">Empresa A–Z</option>
          <option value="updated_at:desc">Atualizados recentemente</option>
        </select>
      </Card>
      <div className="crm-layout">
        <Card
          className="crm-list"
          eyebrow={`${contacts.data?.total ?? 0} contatos`}
        >
          {contacts.isLoading ? <p>Carregando contatos…</p> : null}
          {!contacts.isLoading && contacts.data?.items.length === 0 ? (
            <div className="empty-state">
              <UserRound size={28} />
              <strong>Nenhum contato encontrado</strong>
              <span>Ajuste os filtros ou cadastre o primeiro contato.</span>
            </div>
          ) : null}
          {contacts.data?.items.map((contact) => (
            <button
              className={`contact-row ${selected?.id === contact.id ? "contact-row--active" : ""}`}
              key={contact.id}
              onClick={() => {
                setSelected(contact);
                setEditor(null);
              }}
              type="button"
            >
              <span className="contact-avatar">
                {contact.name.slice(0, 1).toUpperCase()}
              </span>
              <span className="contact-row__body">
                <strong>{contact.name}</strong>
                <small>
                  {contact.company_name ??
                    contact.email ??
                    "Sem empresa informada"}
                </small>
              </span>
              <span className={`status-chip status-chip--${contact.status}`}>
                {statusLabels[contact.status]}
              </span>
            </button>
          ))}
          <div className="pagination">
            <span>
              Página {contacts.data?.page ?? page} de{" "}
              {Math.max(contacts.data?.pages ?? 0, 1)}
            </span>
            <div>
              <Button
                aria-label="Página anterior"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
                variant="ghost"
              >
                <ChevronLeft size={17} />
              </Button>
              <Button
                aria-label="Próxima página"
                disabled={page >= (contacts.data?.pages ?? 0)}
                onClick={() => setPage((value) => value + 1)}
                variant="ghost"
              >
                <ChevronRight size={17} />
              </Button>
            </div>
          </div>
        </Card>
        <div className="crm-side-panel">
          {editor ? (
            <ContactForm
              contact={editor === "edit" ? selected : null}
              key={editor === "edit" ? selected?.id : "new"}
              onClose={() => setEditor(null)}
              onSaved={(contact) => {
                setSelected(contact);
                setEditor(null);
              }}
              tags={tags.data ?? []}
            />
          ) : selected ? (
            <ContactDetails
              contact={selected}
              onClose={() => setSelected(null)}
              onDelete={() => {
                if (window.confirm(`Excluir ${selected.name}?`))
                  remove.mutate(selected.id);
              }}
              onEdit={() => setEditor("edit")}
            />
          ) : (
            <Card className="crm-tag-manager" eyebrow="Etiquetas">
              <h2>Organização rápida</h2>
              <p>Crie etiquetas para segmentar e filtrar seus contatos.</p>
              <PermissionGuard all={["crm.contacts.update"]}>
                <div className="inline-form">
                  <input
                    aria-label="Nome da etiqueta"
                    onChange={(event) => setTagName(event.target.value)}
                    placeholder="Ex.: Prioritário"
                    value={tagName}
                  />
                  <Button
                    disabled={tagName.trim().length < 2}
                    loading={createTag.isPending}
                    onClick={() => createTag.mutate()}
                  >
                    Criar
                  </Button>
                </div>
              </PermissionGuard>
              <div className="contact-tags">
                {tags.data?.map((tag) => (
                  <span key={tag.id}>
                    <Tag size={13} /> {tag.name}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
