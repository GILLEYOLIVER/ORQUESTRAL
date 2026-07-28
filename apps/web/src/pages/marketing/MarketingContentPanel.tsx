import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileCheck2, Globe2, Send } from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../../lib/http";
import "./marketing-content.css";

type ContentKind = "email" | "whatsapp" | "sms" | "landing_page";
type Content = {
  id: string;
  name: string;
  kind: ContentKind;
  status: "draft" | "in_review" | "approved" | "archived";
  current_version: number;
  subject: string | null;
  body: string;
  ai_generated: boolean;
  review_status: "draft" | "pending" | "approved" | "rejected";
};
type Page = {
  id: string;
  title: string;
  status: string;
  public_path: string;
};

function message(error: unknown) {
  return error instanceof ApiClientError ? error.message : "Não foi possível concluir a operação.";
}

export function MarketingContentPanel({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ContentKind>("email");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [aiGenerated, setAiGenerated] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const contents = useQuery({
    queryKey: ["marketing", "content"],
    queryFn: () => request<Content[]>("/marketing/content"),
  });
  const pages = useQuery({
    queryKey: ["marketing", "content", "pages"],
    queryFn: () => request<Page[]>("/marketing/content/pages"),
  });
  const refresh = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ["marketing", "content"] }),
      client.invalidateQueries({ queryKey: ["marketing", "content", "pages"] }),
    ]);
  const create = useMutation({
    mutationFn: () =>
      request<Content>("/marketing/content", {
        method: "POST",
        body: {
          name,
          kind,
          subject: subject || null,
          body,
          ai_generated: aiGenerated,
        },
      }),
    onSuccess: async () => {
      setName("");
      setSubject("");
      setBody("");
      setAiGenerated(false);
      setError(null);
      setFeedback("Conteúdo versionado criado.");
      await refresh();
    },
    onError: (caught) => setError(message(caught)),
  });
  const review = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "submit" | "approve" | "reject" }) =>
      request<Content>(`/marketing/content/${id}/review`, {
        method: "POST",
        body: { decision },
      }),
    onSuccess: async () => {
      setError(null);
      setFeedback("Fluxo de revisão atualizado.");
      await refresh();
    },
    onError: (caught) => setError(message(caught)),
  });
  const createPage = useMutation({
    mutationFn: (content: Content) =>
      request<Page>("/marketing/content/pages", {
        method: "POST",
        body: {
          content_id: content.id,
          slug: `${content.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}-${content.id.slice(0, 6)}`,
          title: content.name,
          form_schema: {
            require_consent: true,
            fields: [
              { name: "name", type: "text", required: true },
              { name: "email", type: "email", required: true },
            ],
          },
        },
      }),
    onSuccess: async () => {
      setFeedback("Landing page criada. Publique quando estiver pronta.");
      await refresh();
    },
    onError: (caught) => setError(message(caught)),
  });
  return (
    <Card className="marketing-content">
      <header>
        <div>
          <span className="eyebrow">Conteúdo e captação</span>
          <h2>Criação, revisão e páginas</h2>
          <p>Conteúdo de IA fica identificado e toda versão exige revisão por outra pessoa.</p>
        </div>
        <FileCheck2 size={34} />
      </header>
      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      {canManage ? (
        <div className="marketing-content__form">
          <input placeholder="Nome do conteúdo" value={name} onChange={(event) => setName(event.target.value)} />
          <select value={kind} onChange={(event) => setKind(event.target.value as ContentKind)}>
            <option value="email">E-mail</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="sms">SMS</option>
            <option value="landing_page">Landing page</option>
          </select>
          <input placeholder="Assunto" value={subject} onChange={(event) => setSubject(event.target.value)} />
          <textarea placeholder="Conteúdo" value={body} onChange={(event) => setBody(event.target.value)} />
          <label><input type="checkbox" checked={aiGenerated} onChange={(event) => setAiGenerated(event.target.checked)} /> Gerado com IA</label>
          <Button disabled={name.trim().length < 2 || !body.trim()} loading={create.isPending} onClick={() => create.mutate()}>
            Criar conteúdo
          </Button>
        </div>
      ) : null}
      <div className="marketing-content__grid">
        {contents.data?.map((content) => (
          <article key={content.id}>
            <strong>{content.name}</strong>
            <small>v{content.current_version} · {content.review_status}{content.ai_generated ? " · IA" : ""}</small>
            {canManage && content.review_status === "draft" ? (
              <button onClick={() => review.mutate({ id: content.id, decision: "submit" })}><Send size={15} /> Enviar para revisão</button>
            ) : null}
            {canManage && content.review_status === "pending" ? (
              <button onClick={() => review.mutate({ id: content.id, decision: "approve" })}><FileCheck2 size={15} /> Aprovar</button>
            ) : null}
            {canManage && content.kind === "landing_page" && content.status === "approved" ? (
              <button onClick={() => createPage.mutate(content)}><Globe2 size={15} /> Criar página</button>
            ) : null}
          </article>
        ))}
      </div>
      {pages.data?.length ? <small>{pages.data.length} página(s) preparada(s).</small> : null}
    </Card>
  );
}
