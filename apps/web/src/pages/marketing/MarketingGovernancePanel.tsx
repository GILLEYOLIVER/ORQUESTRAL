import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, ShieldCheck } from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../../lib/http";
import "./marketing-governance.css";

type Channel = "email" | "whatsapp" | "sms" | "web";
type Policy = {
  id: string;
  channel: Channel;
  window_start: string;
  window_end: string;
  daily_limit: number;
  weekly_limit: number;
};
const labels: Record<Channel, string> = {
  email: "E-mail",
  whatsapp: "WhatsApp",
  sms: "SMS",
  web: "Web",
};

export function MarketingGovernancePanel({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState<Channel>("email");
  const [daily, setDaily] = useState("2");
  const [weekly, setWeekly] = useState("5");
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("20:00");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const policies = useQuery({
    queryKey: ["marketing", "governance", "policies"],
    queryFn: () => request<Policy[]>("/marketing/governance/policies"),
  });
  const save = useMutation({
    mutationFn: () =>
      request<Policy>(`/marketing/governance/policies/${channel}`, {
        method: "PUT",
        body: {
          channel,
          timezone: "America/Sao_Paulo",
          allowed_weekdays: [0, 1, 2, 3, 4],
          window_start: `${start}:00`,
          window_end: `${end}:00`,
          daily_limit: Number(daily),
          weekly_limit: Number(weekly),
          enabled: true,
        },
      }),
    onSuccess: async () => {
      setError(null);
      setMessage("Política de contato salva e ativa no backend.");
      await queryClient.invalidateQueries({
        queryKey: ["marketing", "governance", "policies"],
      });
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível salvar a política.",
      ),
  });
  return (
    <Card className="marketing-governance">
      <header>
        <div>
          <span className="eyebrow">Governança de contato</span>
          <h2>Consentimento, frequência e horário</h2>
          <p>
            O backend bloqueia contatos sem consentimento, fora do horário ou
            acima do limite antes que qualquer provedor receba a mensagem.
          </p>
        </div>
        <ShieldCheck size={34} />
      </header>
      {message ? <Alert variant="success">{message}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      {canManage ? (
        <div className="marketing-governance__form">
          <label>
            Canal
            <select value={channel} onChange={(event) => setChannel(event.target.value as Channel)}>
              {Object.entries(labels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Limite diário
            <input min="1" type="number" value={daily} onChange={(event) => setDaily(event.target.value)} />
          </label>
          <label>
            Limite semanal
            <input min="1" type="number" value={weekly} onChange={(event) => setWeekly(event.target.value)} />
          </label>
          <label>
            Início
            <input type="time" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label>
            Término
            <input type="time" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
          <Button loading={save.isPending} onClick={() => save.mutate()}>
            Salvar política
          </Button>
        </div>
      ) : null}
      <div className="marketing-governance__policies">
        {policies.data?.map((policy) => (
          <article key={policy.id}>
            <Clock3 size={18} />
            <span>
              <strong>{labels[policy.channel]}</strong>
              <small>
                {policy.window_start.slice(0, 5)}–{policy.window_end.slice(0, 5)}
                {" · "}{policy.daily_limit}/dia · {policy.weekly_limit}/semana
              </small>
            </span>
          </article>
        ))}
      </div>
    </Card>
  );
}
