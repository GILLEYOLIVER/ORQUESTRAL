import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { CompanyResponse } from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";

const schema = z.object({
  legal_name: z.string().min(2, "Informe a razão social."),
  trade_name: z.string().min(2, "Informe o nome fantasia."),
  document_number: z.string().min(5, "Informe o documento."),
  slug: z
    .string()
    .min(3, "Informe o identificador.")
    .regex(
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      "Use letras minúsculas, números e hífen.",
    ),
});
type FormValues = z.infer<typeof schema>;

export function CompaniesPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => request<CompanyResponse[]>("/companies"),
    enabled: Boolean(me?.user.is_platform_admin),
  });
  const createCompany = useMutation({
    mutationFn: (values: FormValues) =>
      request<CompanyResponse>("/companies", {
        method: "POST",
        body: { ...values, status: "trial" },
      }),
    onSuccess: async () => {
      reset();
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Falha ao criar empresa.",
      ),
  });
  const changeStatus = useMutation({
    mutationFn: ({ id, status }: Pick<CompanyResponse, "id" | "status">) =>
      request<CompanyResponse>(`/companies/${id}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["companies"] }),
  });

  if (!me?.user.is_platform_admin) {
    return (
      <Alert variant="error">
        Acesso restrito à administração da plataforma.
      </Alert>
    );
  }
  return (
    <div className="management-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Plataforma</span>
          <h1>Empresas</h1>
          <p>Cadastre tenants e controle seu estado operacional.</p>
        </div>
      </div>
      <div className="management-grid">
        <Card eyebrow="Nova empresa">
          {error ? <Alert variant="error">{error}</Alert> : null}
          <form
            className="stack-form"
            noValidate
            onSubmit={(event) =>
              void handleSubmit((values) => createCompany.mutate(values))(event)
            }
          >
            <TextField
              error={errors.legal_name?.message}
              label="Razão social"
              {...register("legal_name")}
            />
            <TextField
              error={errors.trade_name?.message}
              label="Nome fantasia"
              {...register("trade_name")}
            />
            <TextField
              error={errors.document_number?.message}
              label="CNPJ ou documento"
              {...register("document_number")}
            />
            <TextField
              error={errors.slug?.message}
              label="Identificador (slug)"
              placeholder="empresa-exemplo"
              {...register("slug")}
            />
            <Button loading={createCompany.isPending} type="submit">
              <Plus size={17} /> Cadastrar empresa
            </Button>
          </form>
        </Card>
        <Card className="management-list" eyebrow="Empresas cadastradas">
          {companies.isLoading ? <p>Carregando empresas…</p> : null}
          {companies.isError ? (
            <Alert variant="error">
              Não foi possível carregar as empresas.
            </Alert>
          ) : null}
          {companies.data?.map((company) => (
            <article className="management-row" key={company.id}>
              <Building2 aria-hidden="true" />
              <div>
                <strong>{company.trade_name}</strong>
                <span>
                  {company.legal_name} · {company.document_number}
                </span>
              </div>
              <span className={`status-chip status-chip--${company.status}`}>
                {company.status}
              </span>
              <Button
                onClick={() =>
                  changeStatus.mutate({
                    id: company.id,
                    status:
                      company.status === "suspended" ? "active" : "suspended",
                  })
                }
                variant="ghost"
              >
                {company.status === "suspended" ? "Ativar" : "Suspender"}
              </Button>
            </article>
          ))}
        </Card>
      </div>
    </div>
  );
}
