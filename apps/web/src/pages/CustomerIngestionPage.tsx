import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  DatabaseZap,
  FileWarning,
  RefreshCcw,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { request } from "../lib/http";
import { useSession } from "../session/context";
import { CustomerCdcPanel } from "../components/CustomerCdcPanel";

type QualityRule = {
  id: string;
  version: number;
  name: string;
  status: "draft" | "published" | "retired";
  rules: Record<string, unknown>;
};

type IngestionRecord = {
  id: string;
  source_record_id: string;
  payload_fingerprint: string;
  status: "accepted" | "rejected" | "dead_letter";
  error_code: string | null;
  errors: string[];
  profile_id: string | null;
  attempts: number;
};

type IngestionJob = {
  id: string;
  source_code: string;
  source_name: string;
  quality_rule_version: number;
  mode: "batch" | "incremental";
  status: "completed" | "partial" | "failed";
  idempotency_key: string;
  cursor: string | null;
  total_records: number;
  accepted_records: number;
  rejected_records: number;
  created_at: string;
  records: IngestionRecord[];
};

type DeadLetter = {
  id: string;
  job_id: string;
  source_code: string;
  source_record_id: string;
  payload_fingerprint: string;
  error_code: string;
  errors: string[];
  attempts: number;
};

const exampleRecords = JSON.stringify(
  [
    {
      source_record_id: "cliente-001",
      external_id: "erp-001",
      display_name: "Cliente Exemplo",
      email: "cliente@exemplo.com",
      phone: "+55 11 99999-0000",
    },
  ],
  null,
  2,
);

export function CustomerIngestionPage() {
  const queryClient = useQueryClient();
  const session = useSession();
  const readOnly = session.me?.access_mode === "read_only";
  const [sourceCode, setSourceCode] = useState("importacao.manual");
  const [sourceName, setSourceName] = useState("Importação manual");
  const [mode, setMode] = useState<"batch" | "incremental">("batch");
  const [recordsText, setRecordsText] = useState(exampleRecords);
  const [feedback, setFeedback] = useState("");
  const [reprocessText, setReprocessText] = useState(exampleRecords.slice(1, -1));

  const qualityRules = useQuery({
    queryKey: ["customer-quality-rules"],
    queryFn: () =>
      request<QualityRule[]>(
        "/crm/customer-data/ingestion/quality-rules",
      ),
  });
  const jobs = useQuery({
    queryKey: ["customer-ingestion-jobs"],
    queryFn: () =>
      request<IngestionJob[]>("/crm/customer-data/ingestion/jobs"),
  });
  const deadLetters = useQuery({
    queryKey: ["customer-ingestion-dead-letters"],
    queryFn: () =>
      request<DeadLetter[]>(
        "/crm/customer-data/ingestion/dead-letters",
      ),
  });
  const publishedRule = qualityRules.data?.find(
    (rule) => rule.status === "published",
  );
  const totals = useMemo(
    () =>
      jobs.data?.reduce(
        (sum, job) => ({
          accepted: sum.accepted + job.accepted_records,
          rejected: sum.rejected + job.rejected_records,
        }),
        { accepted: 0, rejected: 0 },
      ) ?? { accepted: 0, rejected: 0 },
    [jobs.data],
  );

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["customer-quality-rules"] }),
      queryClient.invalidateQueries({ queryKey: ["customer-ingestion-jobs"] }),
      queryClient.invalidateQueries({
        queryKey: ["customer-ingestion-dead-letters"],
      }),
    ]);
  };

  const createRule = useMutation({
    mutationFn: () =>
      request<QualityRule>(
        "/crm/customer-data/ingestion/quality-rules",
        {
          method: "POST",
          body: {
            name: "Qualidade padrão",
            rules: {
              required: ["external_id", "display_name"],
              email_format: true,
              phone_min_digits: 8,
              minimum_score: 60,
            },
          },
        },
      ),
    onSuccess: async (rule) => {
      await request(
        `/crm/customer-data/ingestion/quality-rules/${rule.id}/publish`,
        { method: "POST" },
      );
      setFeedback(`Regras de qualidade v${rule.version} publicadas.`);
      await refresh();
    },
  });

  const ingest = useMutation({
    mutationFn: () => {
      const records = JSON.parse(recordsText) as unknown[];
      return request<IngestionJob>("/crm/customer-data/ingestion/jobs", {
        method: "POST",
        body: {
          source_code: sourceCode,
          source_name: sourceName,
          mode,
          idempotency_key: `${sourceCode}:${crypto.randomUUID()}`,
          records,
        },
      });
    },
    onSuccess: async (job) => {
      setFeedback(
        `${job.accepted_records} aceito(s) e ${job.rejected_records} rejeitado(s).`,
      );
      await refresh();
    },
    onError: () => setFeedback("Revise o JSON e as regras publicadas."),
  });

  const reprocess = useMutation({
    mutationFn: ({ id, sourceRecordId }: { id: string; sourceRecordId: string }) => {
      const parsed = JSON.parse(reprocessText) as Record<string, unknown>;
      return request<IngestionRecord>(
        `/crm/customer-data/ingestion/dead-letters/${id}/reprocess`,
        {
          method: "POST",
          body: {
            record: { ...parsed, source_record_id: sourceRecordId },
            reason: "Carga corrigida após revisão humana.",
          },
        },
      );
    },
    onSuccess: async () => {
      setFeedback("Registro corrigido e reprocessado.");
      await refresh();
    },
  });

  return (
    <main className="customer-ingestion">
      <header className="customer-ingestion__hero">
        <div>
          <span className="eyebrow">ENTRADA GOVERNADA</span>
          <h1>Ingestão e qualidade de dados</h1>
          <p>
            Importe registros em lote ou incrementalmente, aplique regras
            versionadas e corrija falhas sem guardar a carga sensível na fila.
          </p>
        </div>
        <div className="customer-ingestion__metrics">
          <div>
            <CheckCircle2 aria-hidden="true" />
            <strong>{totals.accepted}</strong>
            <span>aceitos</span>
          </div>
          <div>
            <FileWarning aria-hidden="true" />
            <strong>{totals.rejected}</strong>
            <span>rejeitados</span>
          </div>
        </div>
      </header>

      {feedback ? (
        <p className="customer-ingestion__feedback" role="status">
          {feedback}
        </p>
      ) : null}

      <section className="customer-ingestion__grid">
        <article className="customer-ingestion__panel">
          <div className="customer-ingestion__title">
            <ShieldCheck aria-hidden="true" />
            <div>
              <span className="eyebrow">QUALIDADE</span>
              <h2>Contrato de entrada</h2>
            </div>
          </div>
          <p>
            {publishedRule
              ? `Versão ${publishedRule.version} publicada e ativa.`
              : "Nenhuma regra publicada. Crie o contrato padrão antes de importar."}
          </p>
          <button
            type="button"
            onClick={() => createRule.mutate()}
            disabled={readOnly || createRule.isPending}
            title={readOnly ? "Acesso somente leitura" : undefined}
          >
            {publishedRule ? "Criar nova versão padrão" : "Criar e publicar regras"}
          </button>
          <div className="customer-ingestion__rules">
            {qualityRules.data?.map((rule) => (
              <span key={rule.id} className={`status-pill status-pill--${rule.status}`}>
                v{rule.version} · {rule.status.toUpperCase()}
              </span>
            ))}
          </div>
        </article>

        <article className="customer-ingestion__panel customer-ingestion__panel--dark">
          <div className="customer-ingestion__title">
            <DatabaseZap aria-hidden="true" />
            <div>
              <span className="eyebrow">PRIVACIDADE</span>
              <h2>O que fica armazenado</h2>
            </div>
          </div>
          <ul>
            <li>Hash SHA-256 da carga</li>
            <li>Identificador da origem</li>
            <li>Códigos de validação</li>
            <li>Contadores e trilha de auditoria</li>
          </ul>
          <strong>A carga bruta não é salva na fila de erros.</strong>
        </article>
      </section>

      <section className="customer-ingestion__panel">
        <div className="customer-ingestion__title">
          <UploadCloud aria-hidden="true" />
          <div>
            <span className="eyebrow">LOTE OU INCREMENTAL</span>
            <h2>Enviar registros</h2>
          </div>
        </div>
        <div className="customer-ingestion__form">
          <label>
            Código da origem
            <input
              value={sourceCode}
              onChange={(event) => setSourceCode(event.target.value)}
              disabled={readOnly}
            />
          </label>
          <label>
            Nome da origem
            <input
              value={sourceName}
              onChange={(event) => setSourceName(event.target.value)}
              disabled={readOnly}
            />
          </label>
          <label>
            Modo
            <select
              value={mode}
              onChange={(event) =>
                setMode(event.target.value as "batch" | "incremental")
              }
              disabled={readOnly}
            >
              <option value="batch">Lote</option>
              <option value="incremental">Incremental</option>
            </select>
          </label>
        </div>
        <label>
          Registros em JSON
          <textarea
            rows={14}
            value={recordsText}
            onChange={(event) => setRecordsText(event.target.value)}
            disabled={readOnly}
          />
        </label>
        <button
          type="button"
          onClick={() => ingest.mutate()}
          disabled={readOnly || !publishedRule || ingest.isPending}
        >
          <UploadCloud aria-hidden="true" />
          Validar e importar
        </button>
      </section>

      <section className="customer-ingestion__panel">
        <span className="eyebrow">EXECUÇÕES</span>
        <h2>Histórico idempotente</h2>
        <div className="customer-ingestion__jobs">
          {jobs.data?.map((job) => (
            <article key={job.id}>
              <div>
                <strong>{job.source_name}</strong>
                <span>{job.mode === "batch" ? "Lote" : "Incremental"}</span>
              </div>
              <span className={`status-pill status-pill--${job.status}`}>
                {job.status.toUpperCase()}
              </span>
              <dl>
                <div>
                  <dt>Total</dt>
                  <dd>{job.total_records}</dd>
                </div>
                <div>
                  <dt>Aceitos</dt>
                  <dd>{job.accepted_records}</dd>
                </div>
                <div>
                  <dt>Rejeitados</dt>
                  <dd>{job.rejected_records}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="customer-ingestion__panel customer-ingestion__dlq">
        <div className="customer-ingestion__title">
          <FileWarning aria-hidden="true" />
          <div>
            <span className="eyebrow">FILA DE ERROS</span>
            <h2>Corrigir e reprocessar</h2>
          </div>
        </div>
        <p>
          Informe uma carga corrigida. O identificador de origem é preservado
          automaticamente e toda tentativa fica auditada.
        </p>
        <label>
          Registro corrigido em JSON
          <textarea
            rows={9}
            value={reprocessText}
            onChange={(event) => setReprocessText(event.target.value)}
            disabled={readOnly}
          />
        </label>
        <div className="customer-ingestion__dead-letters">
          {deadLetters.data?.map((item) => (
            <article key={item.id}>
              <div>
                <strong>{item.source_record_id}</strong>
                <span>{item.payload_fingerprint}</span>
              </div>
              <p>{item.errors.join(" · ")}</p>
              <button
                type="button"
                onClick={() =>
                  reprocess.mutate({
                    id: item.id,
                    sourceRecordId: item.source_record_id,
                  })
                }
                disabled={readOnly || reprocess.isPending}
              >
                <RefreshCcw aria-hidden="true" />
                Reprocessar
              </button>
            </article>
          ))}
        </div>
      </section>

      <CustomerCdcPanel readOnly={readOnly} />
    </main>
  );
}
