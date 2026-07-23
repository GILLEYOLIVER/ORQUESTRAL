import { useCallback, useEffect, useState } from "react";

import { request } from "../lib/http";

interface SegmentDefinition {
  profile_type: "person" | "organization" | null;
  lifecycle_status: "lead" | "prospect" | "customer" | "inactive" | null;
  min_quality_score: number;
  consent_purpose:
    | "marketing"
    | "service"
    | "analytics"
    | "ai_processing"
    | "data_sharing"
    | null;
  consent_channel: "all" | "email" | "phone" | "whatsapp" | "sms" | "web";
}

interface Segment {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "published" | "paused";
  version: number;
  definition: SegmentDefinition;
  member_count: number;
  materialized_at: string | null;
  published_at: string | null;
}

interface SearchResult {
  profile_id: string;
  display_name: string;
  profile_type: string;
  lifecycle_status: string;
  quality_score: number;
  identity_hint: string | null;
  processing_restricted: boolean;
}

interface SearchResponse {
  query_kind: "text" | "email" | "phone";
  results: SearchResult[];
}

interface ActivationResult {
  status: "completed" | "partial" | "blocked";
  eligible_count: number;
  activated_count: number;
  excluded_restricted_count: number;
  excluded_no_consent_count: number;
}

export function CustomerSegmentsPanel({ readOnly }: { readOnly: boolean }) {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [name, setName] = useState("");
  const [profileType, setProfileType] = useState("");
  const [lifecycle, setLifecycle] = useState("");
  const [quality, setQuality] = useState(0);
  const [consentPurpose, setConsentPurpose] = useState("");
  const [consentChannel, setConsentChannel] = useState("all");
  const [campaignId, setCampaignId] = useState("");
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setSegments(await request<Segment[]>("/crm/customer-data/segments"));
  }, []);

  useEffect(() => {
    void refresh().catch(() => setStatusMessage("Não foi possível carregar os segmentos."));
  }, [refresh]);

  const run = async (operation: () => Promise<string>) => {
    setBusy(true);
    setStatusMessage("");
    try {
      const message = await operation();
      setStatusMessage(message);
      await refresh();
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "A operação não pôde ser concluída.",
      );
    } finally {
      setBusy(false);
    }
  };

  const createSegment = () =>
    run(async () => {
      await request<Segment>("/crm/customer-data/segments", {
        method: "POST",
        body: {
          name: name.trim(),
          definition: {
            profile_type: profileType || null,
            lifecycle_status: lifecycle || null,
            min_quality_score: quality,
            consent_purpose: consentPurpose || null,
            consent_channel: consentPurpose ? consentChannel : "all",
          },
        },
      });
      setName("");
      return "Segmento criado como rascunho.";
    });

  const segmentAction = (
    segment: Segment,
    action: "materialize" | "publish",
  ) =>
    run(async () => {
      await request(`/crm/customer-data/segments/${segment.id}/${action}`, {
        method: "POST",
      });
      return action === "publish"
        ? "Segmento publicado e versionado."
        : "Membros recalculados com as políticas atuais.";
    });

  const activate = (segment: Segment) =>
    run(async () => {
      const activation = await request<ActivationResult>(
        `/crm/customer-data/segments/${segment.id}/activate`,
        {
          method: "POST",
          body: { campaign_id: campaignId.trim() },
        },
      );
      return `${activation.activated_count} contato(s) ativado(s); ${activation.excluded_no_consent_count} sem consentimento e ${activation.excluded_restricted_count} restrito(s).`;
    });

  const searchProfiles = async () => {
    if (search.trim().length < 2) {
      return;
    }
    setBusy(true);
    setStatusMessage("");
    try {
      const response = await request<SearchResponse>(
        `/crm/customer-data/segments/search/profiles?q=${encodeURIComponent(search.trim())}`,
      );
      setResults(response.results);
      setStatusMessage(`${response.results.length} perfil(is) localizado(s).`);
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "A busca não pôde ser concluída.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="customer-segments-panel">
      <div className="customer-segments-intro">
        <div>
          <p className="eyebrow">Ativação governada</p>
          <h2>Segmentos e busca segura</h2>
          <p>
            Encontre perfis por dados mascarados e prepare audiências somente com
            consentimento válido.
          </p>
        </div>
        <div className="customer-profile-search">
          <label>
            Buscar perfil
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Nome, e-mail exato ou telefone exato"
            />
          </label>
          <button
            type="button"
            disabled={busy || search.trim().length < 2}
            onClick={() => void searchProfiles()}
          >
            Buscar
          </button>
        </div>
      </div>

      {results.length ? (
        <div className="customer-profile-results">
          {results.map((profile) => (
            <article key={profile.profile_id}>
              <span>
                <strong>{profile.display_name}</strong>
                <small>
                  {profile.identity_hint ?? "Sem dica de identidade"} · qualidade{" "}
                  {profile.quality_score}
                </small>
              </span>
              <span
                className={
                  profile.processing_restricted
                    ? "customer-profile-restricted"
                    : "customer-profile-available"
                }
              >
                {profile.processing_restricted ? "Processamento restrito" : "Disponível"}
              </span>
            </article>
          ))}
        </div>
      ) : null}

      <div className="customer-segment-builder">
        <div>
          <h3>Novo segmento</h3>
          <p>Todos os critérios são validados pelo backend.</p>
        </div>
        <label>
          Nome
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Clientes ativos e consentidos"
            disabled={readOnly}
          />
        </label>
        <label>
          Tipo de perfil
          <select
            value={profileType}
            onChange={(event) => setProfileType(event.target.value)}
            disabled={readOnly}
          >
            <option value="">Todos</option>
            <option value="person">Pessoa</option>
            <option value="organization">Organização</option>
          </select>
        </label>
        <label>
          Ciclo de vida
          <select
            value={lifecycle}
            onChange={(event) => setLifecycle(event.target.value)}
            disabled={readOnly}
          >
            <option value="">Todos</option>
            <option value="lead">Lead</option>
            <option value="prospect">Prospect</option>
            <option value="customer">Cliente</option>
            <option value="inactive">Inativo</option>
          </select>
        </label>
        <label>
          Qualidade mínima
          <input
            type="number"
            min={0}
            max={100}
            value={quality}
            onChange={(event) => setQuality(Number(event.target.value))}
            disabled={readOnly}
          />
        </label>
        <label>
          Finalidade do consentimento
          <select
            value={consentPurpose}
            onChange={(event) => setConsentPurpose(event.target.value)}
            disabled={readOnly}
          >
            <option value="">Não filtrar</option>
            <option value="marketing">Marketing</option>
            <option value="service">Atendimento</option>
            <option value="analytics">Analytics</option>
            <option value="ai_processing">Processamento por IA</option>
            <option value="data_sharing">Compartilhamento</option>
          </select>
        </label>
        <label>
          Canal
          <select
            value={consentChannel}
            onChange={(event) => setConsentChannel(event.target.value)}
            disabled={readOnly || !consentPurpose}
          >
            <option value="all">Todos</option>
            <option value="email">E-mail</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="sms">SMS</option>
            <option value="phone">Telefone</option>
            <option value="web">Web</option>
          </select>
        </label>
        <button
          type="button"
          disabled={readOnly || busy || name.trim().length < 2}
          onClick={() => void createSegment()}
        >
          Criar rascunho
        </button>
      </div>

      <label className="customer-campaign-target">
        ID da campanha de destino
        <input
          value={campaignId}
          onChange={(event) => setCampaignId(event.target.value)}
          placeholder="00000000-0000-0000-0000-000000000000"
          disabled={readOnly}
        />
      </label>

      {statusMessage ? <p className="customer-segment-status">{statusMessage}</p> : null}

      <div className="customer-segment-list">
        {segments.length === 0 ? (
          <p>Nenhum segmento criado.</p>
        ) : (
          segments.map((segment) => (
            <article key={segment.id}>
              <header>
                <span>
                  <strong>{segment.name}</strong>
                  <small>
                    versão {segment.version} · {segment.member_count} membro(s)
                  </small>
                </span>
                <b data-status={segment.status}>
                  {segment.status === "published" ? "Publicado" : "Rascunho"}
                </b>
              </header>
              <p>
                Qualidade mínima {segment.definition.min_quality_score}
                {segment.definition.lifecycle_status
                  ? ` · ${segment.definition.lifecycle_status}`
                  : ""}
                {segment.definition.consent_purpose
                  ? ` · consentimento ${segment.definition.consent_purpose}`
                  : ""}
              </p>
              <div>
                <button
                  type="button"
                  disabled={readOnly || busy}
                  onClick={() => void segmentAction(segment, "materialize")}
                >
                  Recalcular membros
                </button>
                <button
                  type="button"
                  disabled={readOnly || busy || !segment.materialized_at}
                  onClick={() => void segmentAction(segment, "publish")}
                >
                  Publicar
                </button>
                <button
                  type="button"
                  disabled={
                    readOnly ||
                    busy ||
                    segment.status !== "published" ||
                    campaignId.trim().length < 32
                  }
                  onClick={() => void activate(segment)}
                >
                  Ativar na campanha
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
