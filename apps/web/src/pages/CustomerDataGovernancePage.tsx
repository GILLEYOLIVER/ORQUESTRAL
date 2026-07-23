import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  CheckCircle2,
  Fingerprint,
  GitMerge,
  ScanSearch,
  ShieldCheck,
  Undo2,
  XCircle,
} from "lucide-react";
import { request } from "../lib/http";
import { useSession } from "../session/context";
import { CustomerPrivacyPanel } from "../components/CustomerPrivacyPanel";
import { CustomerPrivacyRightsPanel } from "../components/CustomerPrivacyRightsPanel";
import { CustomerSegmentsPanel } from "../components/CustomerSegmentsPanel";

type MatchRule = {
  id: string;
  version: number;
  name: string;
  status: "draft" | "published" | "retired";
  threshold: number;
  rules: Record<string, unknown>;
  created_at: string;
  published_at: string | null;
};

type MergeCase = {
  id: string;
  primary_profile_id: string;
  secondary_profile_id: string;
  primary_name: string;
  secondary_name: string;
  status: "pending" | "approved" | "rejected" | "reverted";
  score: number;
  reasons: string[];
  rule_version: number;
  decision_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  reverted_at: string | null;
};

type MatchScan = {
  rule_version: number;
  scanned_profiles: number;
  candidates_created: number;
};

export function CustomerDataGovernancePage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const readOnly = session.me?.access_mode === "read_only";
  const [ruleName, setRuleName] = useState("Correspondência principal");
  const [threshold, setThreshold] = useState("0.88");
  const [decisionNote, setDecisionNote] = useState(
    "Revisão humana concluída com fontes conferidas.",
  );
  const [feedback, setFeedback] = useState("");

  const rules = useQuery({
    queryKey: ["customer-match-rules"],
    queryFn: () =>
      request<MatchRule[]>("/crm/customer-data/match-rules"),
  });
  const mergeCases = useQuery({
    queryKey: ["customer-merge-cases"],
    queryFn: () =>
      request<MergeCase[]>("/crm/customer-data/merge-cases"),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["customer-match-rules"] }),
      queryClient.invalidateQueries({ queryKey: ["customer-merge-cases"] }),
    ]);
  };

  const createRule = useMutation({
    mutationFn: () =>
      request<MatchRule>("/crm/customer-data/match-rules", {
        method: "POST",
        body: {
          name: ruleName,
          threshold: Number(threshold),
          rules: {
            name_similarity_weight: 1,
            exact_identity_weight: 1,
            minimum_name_length: 4,
          },
        },
      }),
    onSuccess: async (created) => {
      setFeedback(`Regra v${created.version} criada como rascunho.`);
      await refresh();
    },
  });

  const publishRule = useMutation({
    mutationFn: (ruleId: string) =>
      request<MatchRule>(
        `/crm/customer-data/match-rules/${ruleId}/publish`,
        { method: "POST" },
      ),
    onSuccess: async (published) => {
      setFeedback(`Regra v${published.version} publicada com segurança.`);
      await refresh();
    },
  });

  const scan = useMutation({
    mutationFn: () =>
      request<MatchScan>("/crm/customer-data/matches/scan", {
        method: "POST",
      }),
    onSuccess: async (result) => {
      setFeedback(
        `${result.scanned_profiles} perfis analisados; ${result.candidates_created} caso(s) novo(s).`,
      );
      await refresh();
    },
  });

  const decide = useMutation({
    mutationFn: ({
      caseId,
      decision,
    }: {
      caseId: string;
      decision: "approved" | "rejected";
    }) =>
      request<MergeCase>(
        `/crm/customer-data/merge-cases/${caseId}/decision`,
        {
          method: "POST",
          body: { decision, note: decisionNote },
        },
      ),
    onSuccess: async (result) => {
      setFeedback(
        result.status === "approved"
          ? "Perfis unidos com trilha reversível."
          : "Sugestão rejeitada e registrada.",
      );
      await refresh();
    },
  });

  const revert = useMutation({
    mutationFn: (caseId: string) =>
      request<MergeCase>(
        `/crm/customer-data/merge-cases/${caseId}/revert`,
        {
          method: "POST",
          body: { note: decisionNote },
        },
      ),
    onSuccess: async () => {
      setFeedback("Fusão desfeita e vínculos originais restaurados.");
      await refresh();
    },
  });

  const pendingCount =
    mergeCases.data?.filter((item) => item.status === "pending").length ?? 0;
  const publishedRule = rules.data?.find((item) => item.status === "published");

  return (
    <main className="customer-governance">
      <header className="customer-governance__hero">
        <div>
          <span className="eyebrow">PLATAFORMA DE DADOS</span>
          <h1>Qualidade e identidade do cliente</h1>
          <p>
            Encontre cadastros parecidos, revise a decisão antes da fusão e
            preserve a origem de cada informação sem duplicar dados sensíveis.
          </p>
        </div>
        <div className="customer-governance__hero-metric">
          <ShieldCheck aria-hidden="true" />
          <strong>{pendingCount}</strong>
          <span>revisões aguardando decisão humana</span>
        </div>
      </header>

      {feedback ? (
        <p className="customer-governance__feedback" role="status">
          {feedback}
        </p>
      ) : null}

      <section className="customer-governance__grid">
        <article className="customer-governance__panel">
          <div className="customer-governance__panel-title">
            <Fingerprint aria-hidden="true" />
            <div>
              <span className="eyebrow">REGRAS VERSIONADAS</span>
              <h2>Como reconhecer duplicidades</h2>
            </div>
          </div>
          <p>
            A versão publicada é a única usada nas análises. Uma nova versão
            começa em rascunho e não altera decisões anteriores.
          </p>
          <div className="customer-governance__form">
            <label>
              Nome da regra
              <input
                value={ruleName}
                onChange={(event) => setRuleName(event.target.value)}
                disabled={readOnly}
              />
            </label>
            <label>
              Confiança mínima
              <input
                type="number"
                min="0.5"
                max="1"
                step="0.01"
                value={threshold}
                onChange={(event) => setThreshold(event.target.value)}
                disabled={readOnly}
              />
            </label>
            <button
              type="button"
              onClick={() => createRule.mutate()}
              disabled={readOnly || createRule.isPending}
              title={readOnly ? "Acesso somente leitura" : undefined}
            >
              Criar rascunho
            </button>
          </div>
          <div className="customer-governance__rules">
            {rules.data?.map((rule) => (
              <div key={rule.id} className="customer-governance__rule">
                <div>
                  <strong>
                    v{rule.version} · {rule.name}
                  </strong>
                  <span>
                    confiança de {(rule.threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <span className={`status-pill status-pill--${rule.status}`}>
                  {rule.status === "published"
                    ? "PUBLICADA"
                    : rule.status === "draft"
                      ? "RASCUNHO"
                      : "ARQUIVADA"}
                </span>
                {rule.status === "draft" ? (
                  <button
                    type="button"
                    onClick={() => publishRule.mutate(rule.id)}
                    disabled={readOnly || publishRule.isPending}
                  >
                    Publicar
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </article>

        <article className="customer-governance__panel customer-governance__panel--scan">
          <div className="customer-governance__panel-title">
            <ScanSearch aria-hidden="true" />
            <div>
              <span className="eyebrow">ANÁLISE EXPLICÁVEL</span>
              <h2>Buscar possíveis duplicidades</h2>
            </div>
          </div>
          <p>
            O sistema somente cria sugestões. Nenhum perfil é unido sem uma
            decisão humana registrada.
          </p>
          <dl className="customer-governance__summary">
            <div>
              <dt>Regra ativa</dt>
              <dd>{publishedRule ? `v${publishedRule.version}` : "Nenhuma"}</dd>
            </div>
            <div>
              <dt>Fila atual</dt>
              <dd>{pendingCount}</dd>
            </div>
          </dl>
          <button
            type="button"
            className="customer-governance__scan-button"
            onClick={() => scan.mutate()}
            disabled={readOnly || !publishedRule || scan.isPending}
          >
            <ScanSearch aria-hidden="true" />
            Analisar perfis agora
          </button>
        </article>
      </section>

      <section className="customer-governance__queue">
        <div className="customer-governance__queue-heading">
          <div>
            <span className="eyebrow">CONTROLE HUMANO</span>
            <h2>Fila de correspondências</h2>
          </div>
          <label>
            Justificativa da decisão
            <input
              value={decisionNote}
              onChange={(event) => setDecisionNote(event.target.value)}
              disabled={readOnly}
            />
          </label>
        </div>
        {mergeCases.isLoading ? <p>Carregando fila…</p> : null}
        {!mergeCases.isLoading && mergeCases.data?.length === 0 ? (
          <div className="customer-governance__empty">
            <GitMerge aria-hidden="true" />
            <strong>Nenhuma correspondência encontrada.</strong>
            <span>Publique uma regra e execute uma análise.</span>
          </div>
        ) : null}
        <div className="customer-governance__cases">
          {mergeCases.data?.map((item) => (
            <article key={item.id} className="customer-governance__case">
              <div className="customer-governance__case-names">
                <strong>{item.primary_name}</strong>
                <ArrowLeftRight aria-hidden="true" />
                <strong>{item.secondary_name}</strong>
              </div>
              <span className={`status-pill status-pill--${item.status}`}>
                {item.status.toUpperCase()}
              </span>
              <p>{item.reasons.join(" ")}</p>
              <small>
                Confiança {(item.score * 100).toFixed(0)}% · regra v
                {item.rule_version}
              </small>
              <div className="customer-governance__case-actions">
                {item.status === "pending" ? (
                  <>
                    <button
                      type="button"
                      onClick={() =>
                        decide.mutate({
                          caseId: item.id,
                          decision: "approved",
                        })
                      }
                      disabled={readOnly || decide.isPending}
                    >
                      <CheckCircle2 aria-hidden="true" />
                      Aprovar fusão
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() =>
                        decide.mutate({
                          caseId: item.id,
                          decision: "rejected",
                        })
                      }
                      disabled={readOnly || decide.isPending}
                    >
                      <XCircle aria-hidden="true" />
                      Rejeitar
                    </button>
                  </>
                ) : null}
                {item.status === "approved" ? (
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => revert.mutate(item.id)}
                    disabled={readOnly || revert.isPending}
                  >
                    <Undo2 aria-hidden="true" />
                    Desfazer fusão
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      <CustomerPrivacyPanel readOnly={readOnly} />
      <CustomerPrivacyRightsPanel readOnly={readOnly} />
      <CustomerSegmentsPanel readOnly={readOnly} />
    </main>
  );
}
