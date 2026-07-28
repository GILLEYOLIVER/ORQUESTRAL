import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, UsersRound } from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../../lib/http";
import "./marketing-audiences.css";

type Audience = {
  id: string;
  name: string;
  description: string | null;
  kind: "dynamic" | "static";
  status: "draft" | "active" | "paused" | "archived";
  segment_id: string | null;
  member_count: number;
  synchronized_at: string | null;
};
type Segment = {
  id: string;
  name: string;
  status: "draft" | "published" | "archived";
  member_count: number;
};

export function MarketingAudiencesPanel({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"dynamic" | "static">("dynamic");
  const [segmentId, setSegmentId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audiences = useQuery({
    queryKey: ["marketing", "audiences"],
    queryFn: () => request<Audience[]>("/marketing/audiences"),
  });
  const segments = useQuery({
    queryKey: ["crm", "customer-segments", "marketing"],
    queryFn: () => request<Segment[]>("/crm/customer-segments"),
    enabled: canManage,
  });
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["marketing", "audiences"] });
  const create = useMutation({
    mutationFn: () =>
      request<Audience>("/marketing/audiences", {
        method: "POST",
        body: {
          name,
          kind,
          segment_id: kind === "dynamic" ? segmentId : null,
        },
      }),
    onSuccess: async () => {
      setName("");
      setSegmentId("");
      setError(null);
      setMessage("Público criado com segurança.");
      await refresh();
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível criar o público.",
      ),
  });
  const sync = useMutation({
    mutationFn: (id: string) =>
      request<{ member_count: number; excluded_no_consent_count: number }>(
        `/marketing/audiences/${id}/sync`,
        { method: "POST" },
      ),
    onSuccess: async (result) => {
      setError(null);
      setMessage(
        `${result.member_count} contatos elegíveis. ${result.excluded_no_consent_count} excluídos por falta de consentimento.`,
      );
      await refresh();
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível sincronizar o público.",
      ),
  });

  return (
    <Card className="marketing-audiences">
      <header>
        <div>
          <span className="eyebrow">Públicos reutilizáveis</span>
          <h2>Segmentos e listas governadas</h2>
          <p>
            Organize contatos uma vez e reutilize-os em campanhas. Públicos
            dinâmicos respeitam restrições e consentimento de marketing.
          </p>
        </div>
        <UsersRound size={34} />
      </header>
      {message ? <Alert variant="success">{message}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      {canManage ? (
        <div className="marketing-audiences__form">
          <input
            aria-label="Nome do público"
            placeholder="Ex.: Clientes ativos com consentimento"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <select
            aria-label="Tipo do público"
            value={kind}
            onChange={(event) => setKind(event.target.value as typeof kind)}
          >
            <option value="dynamic">Dinâmico</option>
            <option value="static">Lista estática</option>
          </select>
          {kind === "dynamic" ? (
            <select
              aria-label="Segmento de origem"
              value={segmentId}
              onChange={(event) => setSegmentId(event.target.value)}
            >
              <option value="">Segmento publicado</option>
              {segments.data
                ?.filter((segment) => segment.status === "published")
                .map((segment) => (
                  <option key={segment.id} value={segment.id}>
                    {segment.name} · {segment.member_count}
                  </option>
                ))}
            </select>
          ) : null}
          <Button
            disabled={
              name.trim().length < 2 || (kind === "dynamic" && !segmentId)
            }
            loading={create.isPending}
            onClick={() => create.mutate()}
          >
            Criar público
          </Button>
        </div>
      ) : null}
      <div className="marketing-audiences__grid">
        {audiences.data?.length ? (
          audiences.data.map((audience) => (
            <article key={audience.id}>
              <span className={`audience-state audience-state--${audience.status}`}>
                {audience.status === "active" ? "Ativo" : "Rascunho"}
              </span>
              <strong>{audience.name}</strong>
              <small>
                {audience.kind === "dynamic" ? "Dinâmico" : "Lista estática"} ·{" "}
                {audience.member_count} contatos
              </small>
              {canManage && audience.kind === "dynamic" ? (
                <button
                  disabled={sync.isPending}
                  onClick={() => sync.mutate(audience.id)}
                  type="button"
                >
                  <RefreshCw size={15} /> Sincronizar
                </button>
              ) : null}
            </article>
          ))
        ) : (
          <p>Nenhum público reutilizável criado.</p>
        )}
      </div>
    </Card>
  );
}
