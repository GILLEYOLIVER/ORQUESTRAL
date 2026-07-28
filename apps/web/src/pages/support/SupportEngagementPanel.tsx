import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, MessageSquareQuote, Search, Sparkles, Star } from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";

import { PermissionGuard } from "../../components/PermissionGuard";
import { ApiClientError, request } from "../../lib/http";
import "./support-engagement.css";

type Template = {
  id: string;
  name: string;
  shortcut: string;
  kind: "macro" | "quick_response";
  content: string;
};
type Citation = {
  knowledge_base_id: string;
  knowledge_document_id: string;
  knowledge_chunk_id: string;
  document_name: string;
  chunk_index: number;
  excerpt: string;
};
type Satisfaction = {
  responses: number;
  overall_average: number;
};
type Props = {
  ticketId: string | null;
  onSent: () => Promise<void>;
};

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a operação.";
}

export function SupportEngagementPanel({ ticketId, onSent }: Props) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("Saudação inicial");
  const [shortcut, setShortcut] = useState("saudacao-inicial");
  const [kind, setKind] = useState<Template["kind"]>("quick_response");
  const [content, setContent] = useState(
    "Olá! Recebemos sua solicitação e vamos acompanhá-la até a resolução.",
  );
  const [message, setMessage] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [query, setQuery] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);

  const templates = useQuery({
    queryKey: ["support", "engagement", "templates"],
    queryFn: () => request<Template[]>("/support/engagement/templates"),
  });
  const satisfaction = useQuery({
    queryKey: ["support", "engagement", "satisfaction"],
    queryFn: () =>
      request<Satisfaction>("/support/engagement/satisfaction/summary"),
  });
  const createTemplate = useMutation({
    mutationFn: () =>
      request<Template>("/support/engagement/templates", {
        method: "POST",
        body: { name, shortcut, kind, content },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["support", "engagement", "templates"],
      });
    },
  });
  const searchKnowledge = useMutation({
    mutationFn: () =>
      request<{ citations: Citation[] }>(
        `/support/engagement/knowledge?q=${encodeURIComponent(query)}`,
      ),
    onSuccess: (result) => setCitations(result.citations),
  });
  const send = useMutation({
    mutationFn: () =>
      request(`/support/engagement/tickets/${ticketId}/responses`, {
        method: "POST",
        body: {
          message,
          template_id: templateId || null,
          citations: citations.map((citation) => ({
            knowledge_base_id: citation.knowledge_base_id,
            knowledge_document_id: citation.knowledge_document_id,
            knowledge_chunk_id: citation.knowledge_chunk_id,
          })),
        },
      }),
    onSuccess: async () => {
      setMessage("");
      setCitations([]);
      await onSent();
    },
  });
  const mutationError =
    createTemplate.error ?? searchKnowledge.error ?? send.error;

  return (
    <section className="support-engagement">
      <header>
        <div>
          <span className="eyebrow">Atendimento consistente</span>
          <h2>Respostas e conhecimento</h2>
          <p>Reutilize conteúdo aprovado, cite fontes e acompanhe a experiência.</p>
        </div>
        <Button variant="secondary" onClick={() => setExpanded((value) => !value)}>
          <MessageSquareQuote size={17} />
          {expanded ? "Recolher conteúdo" : "Abrir conteúdo"}
        </Button>
      </header>
      <div className="support-engagement__summary">
        <article><Sparkles size={19} /><span>Modelos ativos</span><strong>{templates.data?.length ?? 0}</strong></article>
        <article><Star size={19} /><span>Satisfação geral</span><strong>{satisfaction.data?.overall_average ?? 0}/5</strong></article>
        <article><BookOpenCheck size={19} /><span>Avaliações</span><strong>{satisfaction.data?.responses ?? 0}</strong></article>
      </div>
      {mutationError ? <Alert variant="error">{errorMessage(mutationError)}</Alert> : null}
      {expanded ? (
        <div className="support-engagement__body">
          <PermissionGuard all={["support.tickets.update"]}>
            <Card eyebrow="Biblioteca de respostas">
              <label>Nome<input value={name} onChange={(event) => setName(event.target.value)} /></label>
              <label>Atalho<input value={shortcut} onChange={(event) => setShortcut(event.target.value)} /></label>
              <label>Tipo<select value={kind} onChange={(event) => setKind(event.target.value as Template["kind"])}>
                <option value="quick_response">Resposta rápida</option>
                <option value="macro">Macro operacional</option>
              </select></label>
              <textarea aria-label="Conteúdo do modelo" value={content} onChange={(event) => setContent(event.target.value)} />
              <Button onClick={() => createTemplate.mutate()}>Salvar modelo</Button>
            </Card>
          </PermissionGuard>
          <Card eyebrow="Resposta orientada">
            <label>Modelo aprovado<select value={templateId} onChange={(event) => {
              setTemplateId(event.target.value);
              const template = templates.data?.find((item) => item.id === event.target.value);
              if (template) setMessage(template.content);
            }}>
              <option value="">Escolha para preencher</option>
              {templates.data?.map((template) => <option key={template.id} value={template.id}>/{template.shortcut} — {template.name}</option>)}
            </select></label>
            <textarea aria-label="Resposta ao cliente" disabled={!ticketId} value={message} onChange={(event) => setMessage(event.target.value)} placeholder={ticketId ? "Revise antes de enviar." : "Selecione um chamado."} />
            <PermissionGuard all={["support.tickets.comment"]}>
              <Button disabled={!ticketId || !message.trim()} onClick={() => send.mutate()}>Enviar resposta auditável</Button>
            </PermissionGuard>
          </Card>
          <Card eyebrow="Fontes verificáveis">
            <label>Pesquisar conhecimento<div className="support-engagement__search">
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ex.: prazo de reembolso" />
              <Button variant="secondary" disabled={query.trim().length < 2} onClick={() => searchKnowledge.mutate()}><Search size={17} /></Button>
            </div></label>
            <div className="support-engagement__citations">
              {citations.map((citation) => <article key={citation.knowledge_chunk_id}>
                <strong>{citation.document_name}</strong><p>{citation.excerpt}</p><small>Trecho {citation.chunk_index + 1}</small>
              </article>)}
              {!citations.length ? <p>Pesquise para anexar fontes.</p> : null}
            </div>
          </Card>
        </div>
      ) : null}
    </section>
  );
}

