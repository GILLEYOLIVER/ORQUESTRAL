import { useCallback, useEffect, useState } from "react";

import { request } from "../lib/http";

interface RightsSummary {
  active_restrictions: number;
  exports_last_30_days: number;
  corrections_last_30_days: number;
}

interface Restriction {
  id: string;
  profile_id: string;
  status: "active" | "released";
  reason_code: string;
  enforced_at: string;
  released_at: string | null;
}

interface SubjectExport {
  generated_at: string;
  profile: { id: string; display_name: string };
  integrity_sha256: string;
}

const reasonLabels: Record<string, string> = {
  accuracy_dispute: "Dados em contestação",
  legal_request: "Solicitação legal",
  consent_withdrawn: "Consentimento retirado",
  fraud_review: "Análise de fraude",
  other_governed_reason: "Outro motivo governado",
};

export function CustomerPrivacyRightsPanel({ readOnly }: { readOnly: boolean }) {
  const [summary, setSummary] = useState<RightsSummary | null>(null);
  const [restrictions, setRestrictions] = useState<Restriction[]>([]);
  const [profileId, setProfileId] = useState("");
  const [reasonCode, setReasonCode] = useState("accuracy_dispute");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [nextSummary, nextRestrictions] = await Promise.all([
      request<RightsSummary>("/crm/customer-data/rights/summary"),
      request<Restriction[]>("/crm/customer-data/rights/restrictions"),
    ]);
    setSummary(nextSummary);
    setRestrictions(nextRestrictions);
  }, []);

  useEffect(() => {
    void refresh().catch(() => {
      setStatusMessage("Não foi possível carregar os direitos do titular.");
    });
  }, [refresh]);

  const run = async (operation: () => Promise<void>) => {
    setBusy(true);
    setStatusMessage("");
    try {
      await operation();
      await refresh();
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "A operação não pôde ser concluída.",
      );
    } finally {
      setBusy(false);
    }
  };

  const downloadExport = () =>
    run(async () => {
      const data = await request<SubjectExport>(
        `/crm/customer-data/rights/subjects/${profileId}/export`,
        { method: "POST" },
      );
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `orkestral-dados-${data.profile.id}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setStatusMessage(
        `Pacote de ${data.profile.display_name} gerado com integridade ${data.integrity_sha256.slice(0, 12)}.`,
      );
    });

  const applyCorrection = () =>
    run(async () => {
      const payload = Object.fromEntries(
        Object.entries({
          display_name: displayName.trim(),
          email: email.trim(),
          phone: phone.trim(),
        }).filter(([, value]) => value),
      );
      await request(`/crm/customer-data/rights/subjects/${profileId}`, {
        method: "PATCH",
        body: payload,
      });
      setDisplayName("");
      setEmail("");
      setPhone("");
      setStatusMessage("Correção aplicada e auditada sem armazenar os valores no pedido.");
    });

  const restrict = () =>
    run(async () => {
      await request(`/crm/customer-data/rights/subjects/${profileId}/restriction`, {
        method: "POST",
        body: { reason_code: reasonCode },
      });
      setStatusMessage("Processamento automatizado bloqueado para este perfil.");
    });

  const release = (restriction: Restriction) =>
    run(async () => {
      await request(
        `/crm/customer-data/rights/subjects/${restriction.profile_id}/restriction`,
        { method: "DELETE" },
      );
      setStatusMessage("Restrição liberada com trilha de auditoria.");
    });

  const invalidProfile = profileId.trim().length < 32;

  return (
    <section className="customer-rights-panel">
      <div className="customer-rights-heading">
        <div>
          <p className="eyebrow">Direitos do titular</p>
          <h2>Portabilidade, correção e restrição</h2>
          <p>
            Atenda solicitações de dados sem gravar valores pessoais no histórico
            operacional.
          </p>
        </div>
        <div className="customer-rights-metrics" aria-label="Resumo de direitos">
          <strong>{summary?.active_restrictions ?? 0}</strong>
          <span>restrições ativas</span>
          <strong>{summary?.exports_last_30_days ?? 0}</strong>
          <span>pacotes em 30 dias</span>
          <strong>{summary?.corrections_last_30_days ?? 0}</strong>
          <span>correções em 30 dias</span>
        </div>
      </div>

      <label className="customer-rights-profile">
        ID interno do perfil 360
        <input
          value={profileId}
          onChange={(event) => setProfileId(event.target.value)}
          placeholder="00000000-0000-0000-0000-000000000000"
        />
      </label>

      <div className="customer-rights-grid">
        <article>
          <h3>Pacote de acesso</h3>
          <p>Gera JSON verificável somente em memória e impede cache HTTP.</p>
          <button
            type="button"
            disabled={busy || invalidProfile}
            onClick={() => void downloadExport()}
          >
            Gerar pacote portátil
          </button>
        </article>

        <article>
          <h3>Correção governada</h3>
          <p>Somente os nomes dos campos alterados entram na auditoria.</p>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Nome de exibição corrigido"
            disabled={readOnly}
          />
          <input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="E-mail corrigido"
            disabled={readOnly}
          />
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="Telefone corrigido"
            disabled={readOnly}
          />
          <button
            type="button"
            disabled={
              readOnly ||
              busy ||
              invalidProfile ||
              ![displayName, email, phone].some((value) => value.trim())
            }
            onClick={() => void applyCorrection()}
          >
            Aplicar correção
          </button>
        </article>

        <article>
          <h3>Restringir processamento</h3>
          <p>Bloqueia ingestões e sincronizações automatizadas desse perfil.</p>
          <select
            value={reasonCode}
            onChange={(event) => setReasonCode(event.target.value)}
            disabled={readOnly}
          >
            {Object.entries(reasonLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={readOnly || busy || invalidProfile}
            onClick={() => void restrict()}
          >
            Ativar restrição
          </button>
        </article>
      </div>

      {statusMessage ? <p className="customer-rights-status">{statusMessage}</p> : null}

      <div className="customer-rights-list">
        <h3>Restrições ativas</h3>
        {restrictions.length === 0 ? (
          <p>Nenhuma restrição ativa.</p>
        ) : (
          restrictions.map((restriction) => (
            <div key={restriction.id}>
              <span>
                <strong>{restriction.profile_id}</strong>
                {reasonLabels[restriction.reason_code] ?? restriction.reason_code}
              </span>
              <button
                type="button"
                disabled={readOnly || busy}
                onClick={() => void release(restriction)}
              >
                Liberar
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
