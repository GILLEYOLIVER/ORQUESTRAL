import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { FileLock2, ShieldAlert, UserRoundX } from "lucide-react";

import { request } from "../lib/http";

type PrivacyStatus =
  | "received"
  | "identity_verified"
  | "approved"
  | "rejected"
  | "completed";

type PrivacyRequest = {
  id: string;
  profile_id: string | null;
  request_type: "anonymization" | "deletion";
  status: PrivacyStatus;
  reason_code: string;
  scope: string[];
  legal_hold: boolean;
  legal_hold_reason: string | null;
  due_at: string;
  requested_at: string;
  completed_at: string | null;
  result_counts: Record<string, number>;
};

type PrivacySummary = {
  received: number;
  awaiting_decision: number;
  approved: number;
  blocked_by_legal_hold: number;
  completed: number;
  overdue: number;
};

const privacyBasePath = "/crm/customer-data/privacy";

const statusLabels: Record<PrivacyStatus, string> = {
  received: "Recebida",
  identity_verified: "Identidade verificada",
  approved: "Aprovada",
  rejected: "Rejeitada",
  completed: "Concluida",
};

export function CustomerPrivacyPanel({ readOnly }: { readOnly: boolean }) {
  const queryClient = useQueryClient();
  const [profileId, setProfileId] = useState("");
  const [reference, setReference] = useState("");
  const [requestType, setRequestType] = useState<"anonymization" | "deletion">(
    "anonymization",
  );
  const [feedback, setFeedback] = useState("");

  const requests = useQuery({
    queryKey: ["customer-privacy-requests"],
    queryFn: () =>
      request<PrivacyRequest[]>(`${privacyBasePath}/requests`),
  });
  const summary = useQuery({
    queryKey: ["customer-privacy-summary"],
    queryFn: () => request<PrivacySummary>(`${privacyBasePath}/summary`),
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["customer-privacy-requests"] }),
      queryClient.invalidateQueries({ queryKey: ["customer-privacy-summary"] }),
    ]);
  };
  const create = useMutation({
    mutationFn: () =>
      request<PrivacyRequest>(`${privacyBasePath}/requests`, {
        method: "POST",
        body: {
          profile_id: profileId,
          request_type: requestType,
          request_reference: reference,
          reason_code: "data_subject_request",
          due_days: 15,
        },
      }),
    onSuccess: async () => {
      setReference("");
      setFeedback("Solicitacao registrada sem armazenar a referencia original.");
      await refresh();
    },
  });
  const action = useMutation({
    mutationFn: ({
      item,
      operation,
    }: {
      item: PrivacyRequest;
      operation: "verify" | "approve" | "reject" | "hold" | "release" | "execute";
    }) => {
      if (operation === "approve" || operation === "reject") {
        return request<PrivacyRequest>(
          `${privacyBasePath}/requests/${item.id}/decision`,
          {
            method: "POST",
            body: {
              decision: operation === "approve" ? "approved" : "rejected",
              reason_code: "data_subject_request",
            },
          },
        );
      }
      if (operation === "hold" || operation === "release") {
        return request<PrivacyRequest>(
          `${privacyBasePath}/requests/${item.id}/legal-hold`,
          {
            method: "POST",
            body: {
              enabled: operation === "hold",
              reason: operation === "hold" ? "regulatory" : null,
            },
          },
        );
      }
      return request<PrivacyRequest>(
        `${privacyBasePath}/requests/${item.id}/${operation}`,
        { method: "POST" },
      );
    },
    onSuccess: async (item) => {
      setFeedback(`Solicitacao atualizada para ${statusLabels[item.status]}.`);
      await refresh();
    },
  });

  return (
    <section className="customer-privacy" aria-labelledby="privacy-title">
      <header>
        <div>
          <span className="eyebrow">PRIVACIDADE E LGPD</span>
          <h2 id="privacy-title">Direitos do titular sem rastros de PII</h2>
          <p>
            Verifique, aprove e execute anonimizacao ou exclusao com bloqueio
            legal e auditoria.
          </p>
        </div>
        <dl>
          <div>
            <dt>Pendentes</dt>
            <dd>
              {(summary.data?.received ?? 0) +
                (summary.data?.awaiting_decision ?? 0)}
            </dd>
          </div>
          <div>
            <dt>Bloqueadas</dt>
            <dd>{summary.data?.blocked_by_legal_hold ?? 0}</dd>
          </div>
          <div>
            <dt>Concluidas</dt>
            <dd>{summary.data?.completed ?? 0}</dd>
          </div>
        </dl>
      </header>

      <div className="customer-privacy__create">
        <label>
          ID do perfil 360
          <input
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            disabled={readOnly}
          />
        </label>
        <label>
          Protocolo recebido
          <input
            value={reference}
            onChange={(event) => setReference(event.target.value)}
            placeholder="PROTOCOLO-CLIENTE-001"
            disabled={readOnly}
          />
        </label>
        <label>
          Tratamento
          <select
            value={requestType}
            onChange={(event) =>
              setRequestType(event.target.value as "anonymization" | "deletion")
            }
            disabled={readOnly}
          >
            <option value="anonymization">Anonimizar</option>
            <option value="deletion">Excluir definitivamente</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={
            readOnly ||
            create.isPending ||
            profileId.length !== 36 ||
            reference.length < 8
          }
        >
          Registrar solicitacao
        </button>
      </div>

      {feedback ? <p className="customer-privacy__feedback">{feedback}</p> : null}

      <div className="customer-privacy__requests">
        {requests.data?.map((item) => (
          <article key={item.id}>
            <div className="customer-privacy__request-title">
              {item.request_type === "deletion" ? (
                <UserRoundX aria-hidden="true" />
              ) : (
                <ShieldAlert aria-hidden="true" />
              )}
              <div>
                <strong>
                  {item.request_type === "deletion"
                    ? "Exclusao definitiva"
                    : "Anonimizacao"}
                </strong>
                <span>{item.profile_id ?? "Perfil removido"}</span>
              </div>
              <span className={`status-pill status-pill--${item.status}`}>
                {statusLabels[item.status]}
              </span>
            </div>
            <small>
              Prazo {new Date(item.due_at).toLocaleDateString("pt-BR")} ·{" "}
              {item.scope.length} areas protegidas
            </small>
            {item.legal_hold ? (
              <p className="customer-privacy__hold">
                <FileLock2 aria-hidden="true" />
                Retencao legal: {item.legal_hold_reason}
              </p>
            ) : null}
            <div className="customer-privacy__actions">
              {item.status === "received" ? (
                <button
                  type="button"
                  onClick={() => action.mutate({ item, operation: "verify" })}
                  disabled={readOnly || action.isPending}
                >
                  Confirmar identidade
                </button>
              ) : null}
              {item.status === "identity_verified" ? (
                <>
                  <button
                    type="button"
                    onClick={() => action.mutate({ item, operation: "approve" })}
                    disabled={readOnly || action.isPending}
                  >
                    Aprovar
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => action.mutate({ item, operation: "reject" })}
                    disabled={readOnly || action.isPending}
                  >
                    Rejeitar
                  </button>
                </>
              ) : null}
              {item.status === "approved" ? (
                <>
                  <button
                    type="button"
                    onClick={() => action.mutate({ item, operation: "execute" })}
                    disabled={readOnly || item.legal_hold || action.isPending}
                  >
                    Executar tratamento
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() =>
                      action.mutate({
                        item,
                        operation: item.legal_hold ? "release" : "hold",
                      })
                    }
                    disabled={readOnly || action.isPending}
                  >
                    {item.legal_hold ? "Liberar retencao" : "Aplicar retencao"}
                  </button>
                </>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

