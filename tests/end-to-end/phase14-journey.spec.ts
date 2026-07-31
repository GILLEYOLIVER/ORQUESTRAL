import {
  expect,
  test,
  type APIRequestContext,
  type APIResponse,
} from "@playwright/test";

type JsonRecord = Record<string, unknown>;

async function readJson<T>(
  response: APIResponse,
  accepted: number[] = [200],
): Promise<T> {
  const payload = await response.text();
  expect(accepted, `${response.url()}: ${payload}`).toContain(
    response.status(),
  );
  return (payload ? JSON.parse(payload) : {}) as T;
}

function authorization(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function developmentAdmin(request: APIRequestContext) {
  const login = await readJson<{ access_token: string }>(
    await request.post("/api/auth/development-login"),
  );
  const home = await readJson<{
    current_company: { id: string } | null;
    memberships: Array<{ company: { id: string; slug: string } }>;
  }>(
    await request.get("/api/auth/me", {
      headers: authorization(login.access_token),
    }),
  );

  if (home.current_company) {
    return { token: login.access_token, companyId: home.current_company.id };
  }

  const membership =
    home.memberships.find(({ company }) => company.slug === "orkestral-dev") ??
    home.memberships[0];
  expect(
    membership,
    "Administrador de desenvolvimento sem empresa ativa",
  ).toBeTruthy();
  const selected = await readJson<{ access_token: string }>(
    await request.post("/api/auth/select-company", {
      headers: authorization(login.access_token),
      data: { company_id: membership.company.id },
    }),
  );
  return { token: selected.access_token, companyId: membership.company.id };
}

test.describe
  .serial("Fase 14 - contratos, seguranca e jornada completa", () => {
  test.skip(
    process.env.PHASE14_E2E !== "true",
    "Execute com docker-compose.test.yml e PHASE14_E2E=true.",
  );

  test("PostgreSQL, Redis, S3, n8n e contratos externos estao disponiveis", async ({
    request,
  }) => {
    const readiness = await request.get("/ready");
    expect(readiness.status()).toBe(200);
    const readinessBody = (await readiness.text()).toLowerCase();
    expect(readinessBody).toMatch(/postgres|database/);
    expect(readinessBody).toContain("redis");

    const admin = await developmentAdmin(request);
    const engine = await readJson<{ configured: boolean; available: boolean }>(
      await request.get("/api/workflows/engine/status", {
        headers: authorization(admin.token),
      }),
    );
    expect(engine).toEqual(
      expect.objectContaining({ configured: true, available: true }),
    );
  });

  test("executa os 10 passos e bloqueia ataques multiempresa", async ({
    request,
    playwright,
    baseURL,
  }) => {
    test.setTimeout(120_000);
    const suffix = `${Date.now().toString(36)}-${test.info().workerIndex}`;
    const secret = `phase14-secret-${suffix}`;
    const memberEmail = `phase14-${suffix}@example.com`;
    const memberPassword = "Phase14!Secure2026";

    const anonymous = await playwright.request.newContext({
      baseURL: baseURL ?? "http://localhost",
    });
    try {
      for (const route of ["/api/agents", "/api/workflows", "/api/plugins"]) {
        const response = await anonymous.get(route);
        expect(response.status(), `${route} deve exigir autenticacao`).toBe(
          401,
        );
      }
    } finally {
      await anonymous.dispose();
    }

    const developmentSession = await developmentAdmin(request);
    let adminToken = developmentSession.token;
    const homeCompanyId = developmentSession.companyId;

    // 1. Criar empresa e confirmar que o criador se tornou proprietario.
    const company = await readJson<{ id: string }>(
      await request.post("/api/companies", {
        headers: authorization(adminToken),
        data: {
          legal_name: `Orkestral Phase 14 ${suffix} Ltda`,
          trade_name: `Phase 14 ${suffix}`,
          document_number: `${Date.now()}${test.info().workerIndex}`,
          slug: `phase14-${suffix}`,
        },
      }),
      [201],
    );
    const selected = await readJson<{ access_token: string }>(
      await request.post("/api/auth/select-company", {
        headers: authorization(adminToken),
        data: { company_id: company.id },
      }),
    );
    adminToken = selected.access_token;
    const selectedMe = await readJson<{
      current_company: { id: string };
      permissions: string[];
    }>(
      await request.get("/api/auth/me", { headers: authorization(adminToken) }),
    );
    expect(selectedMe.current_company.id).toBe(company.id);
    expect(selectedMe.permissions).toContain("agents.create");
    expect(selectedMe.permissions).toContain("workflows.configure");

    // 2. Criar usuario por convite e validar que um membro nao escala privilegios.
    const roles = await readJson<Array<{ id: string; name: string }>>(
      await request.get("/api/authorization/roles", {
        headers: authorization(adminToken),
      }),
    );
    const memberRole = roles.find((role) => role.name === "Membro");
    if (!memberRole) {
      throw new Error(
        "O papel de sistema Membro nao foi criado para a nova empresa.",
      );
    }
    const invitation = await readJson<{ development_token: string | null }>(
      await request.post("/api/company/invitations", {
        headers: authorization(adminToken),
        data: {
          email: memberEmail,
          name: "Membro Fase 14",
          role_id: memberRole.id,
        },
      }),
      [200, 201],
    );
    if (!invitation.development_token) {
      throw new Error(
        "DEVELOPMENT_EXPOSE_TOKENS deve estar ativo no ambiente de teste.",
      );
    }
    await readJson<JsonRecord>(
      await request.post("/api/auth/accept-invitation", {
        data: {
          token: invitation.development_token,
          name: "Membro Fase 14",
          password: memberPassword,
        },
      }),
    );
    const memberLogin = await readJson<{ access_token: string }>(
      await request.post("/api/auth/login", {
        data: { email: memberEmail, password: memberPassword },
      }),
    );
    const memberToken = memberLogin.access_token;
    expect(
      (
        await request.patch("/api/modules/crm", {
          headers: authorization(memberToken),
          data: { status: "active" },
        })
      ).status(),
    ).toBe(403);
    expect(
      (
        await request.post("/api/companies", {
          headers: authorization(memberToken),
          data: {
            legal_name: "Escalation attempt",
            trade_name: "Escalation",
            document_number: "99999999999999",
            slug: `escalation-${suffix}`,
          },
        })
      ).status(),
    ).toBe(403);
    expect(
      (
        await request.post("/api/auth/select-company", {
          headers: authorization(memberToken),
          data: { company_id: homeCompanyId },
        })
      ).status(),
    ).toBe(403);

    // 3. Ativar modulo.
    const module = await readJson<{ company_status: string }>(
      await request.patch("/api/modules/crm", {
        headers: authorization(adminToken),
        data: { status: "active", configuration: { source: "phase14-e2e" } },
      }),
    );
    expect(module.company_status).toBe("active");

    // 4. Configurar plugin, testar HTTP real e garantir que o segredo nao vaza.
    const plugin = await readJson<{ company_status: string }>(
      await request.patch("/api/plugins/rest_api", {
        headers: authorization(adminToken),
        data: { status: "active", configuration: { environment: "phase14" } },
      }),
    );
    expect(plugin.company_status).toBe("active");
    const credential = await readJson<{
      id: string;
      masked_values: JsonRecord;
    }>(
      await request.post("/api/plugins/rest_api/credentials", {
        headers: authorization(adminToken),
        data: {
          name: "Contrato HTTP Fase 14",
          values: {
            base_url: "http://phase14-contract:5678/plugin/ping",
            api_key: secret,
            auth_header: "X-Phase14-Key",
          },
        },
      }),
      [201],
    );
    expect(JSON.stringify(credential)).not.toContain(secret);
    const connection = await readJson<{ success: boolean }>(
      await request.post(
        `/api/plugins/rest_api/credentials/${credential.id}/test`,
        {
          headers: authorization(adminToken),
        },
      ),
    );
    expect(connection.success).toBe(true);

    // 5. Criar agente usando o contrato OpenAI compativel.
    const agent = await readJson<{ id: string }>(
      await request.post("/api/agents", {
        headers: authorization(adminToken),
        data: {
          name: `Agente Fase 14 ${suffix}`,
          instructions:
            "Responda de forma objetiva durante a validacao automatizada.",
          provider: "openai_compatible",
          model: "phase14-contract-model",
        },
      }),
      [201],
    );
    expect(
      (
        await request.post("/api/agents", {
          headers: authorization(adminToken),
          data: {
            name: "Tentativa de tenant",
            instructions:
              "Esta requisicao nao pode escolher a empresa diretamente.",
            company_id: homeCompanyId,
          },
        })
      ).status(),
    ).toBe(422);

    // 6. Adicionar ferramenta e executar o provedor de IA externo controlado.
    const tools = await readJson<Array<{ tool_key: string; enabled: boolean }>>(
      await request.put(`/api/agents/${agent.id}/tools`, {
        headers: authorization(adminToken),
        data: { tool_keys: ["orkestral.company.summary"] },
      }),
    );
    expect(tools).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          tool_key: "orkestral.company.summary",
          enabled: true,
        }),
      ]),
    );
    const chat = await request.post(`/api/agents/${agent.id}/chat`, {
      headers: authorization(adminToken),
      data: { message: "Confirme a integracao da Fase 14." },
    });
    expect(chat.status(), await chat.text()).toBe(200);

    // Integracao de armazenamento real e bloqueio de upload executavel.
    const knowledgeBase = await readJson<{ id: string }>(
      await request.post("/api/knowledge-bases", {
        headers: authorization(adminToken),
        data: { name: `Conhecimento Fase 14 ${suffix}` },
      }),
      [201],
    );
    const safeUpload = await request.post(
      `/api/knowledge-bases/${knowledgeBase.id}/documents`,
      {
        headers: authorization(adminToken),
        multipart: {
          file: {
            name: "phase14.txt",
            mimeType: "text/plain",
            buffer: Buffer.from(
              "Documento seguro usado no teste de armazenamento da Fase 14.",
            ),
          },
        },
      },
    );
    expect([200, 201, 202]).toContain(safeUpload.status());
    const documents = await readJson<JsonRecord[]>(
      await request.get(`/api/knowledge-bases/${knowledgeBase.id}/documents`, {
        headers: authorization(adminToken),
      }),
    );
    expect(JSON.stringify(documents)).toContain("phase14.txt");
    const maliciousUpload = await request.post(
      `/api/knowledge-bases/${knowledgeBase.id}/documents`,
      {
        headers: authorization(adminToken),
        multipart: {
          file: {
            name: "payload.exe",
            mimeType: "application/x-msdownload",
            buffer: Buffer.from("MZ phase14 malicious fixture"),
          },
        },
      },
    );
    expect([400, 415, 422]).toContain(maliciousUpload.status());

    // 7. Criar workflow; 8. sincronizar, ativar e executar.
    const workflow = await readJson<{ id: string }>(
      await request.post("/api/workflows", {
        headers: authorization(adminToken),
        data: { name: `Workflow Fase 14 ${suffix}` },
      }),
      [201],
    );
    const synced = await readJson<{ sync_status: string }>(
      await request.post(`/api/workflows/${workflow.id}/sync`, {
        headers: authorization(adminToken),
      }),
    );
    expect(synced.sync_status).toBe("synced");
    const activated = await readJson<{ status: string }>(
      await request.post(`/api/workflows/${workflow.id}/activate`, {
        headers: authorization(adminToken),
      }),
    );
    expect(activated.status).toBe("active");
    const execution = await readJson<{
      id: string;
      status: string;
      input_summary: JsonRecord;
      output_summary: JsonRecord;
    }>(
      await request.post(`/api/workflows/${workflow.id}/execute`, {
        headers: authorization(adminToken),
        data: { input: { source: "phase14", api_key: secret } },
      }),
    );
    expect(execution.status).toBe("success");
    expect(JSON.stringify(execution)).not.toContain(secret);

    // 9. Verificar logs de execucao.
    const executions = await readJson<Array<{ id: string; status: string }>>(
      await request.get(`/api/workflows/${workflow.id}/executions`, {
        headers: authorization(adminToken),
      }),
    );
    expect(executions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: execution.id, status: "success" }),
      ]),
    );

    // 10. Verificar consumo e ausencia de credenciais nos eventos auditaveis.
    const usage = await readJson<
      Array<{ metric: string; metadata: JsonRecord }>
    >(
      await request.get("/api/billing/usage-records", {
        headers: authorization(adminToken),
      }),
    );
    expect(usage).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          metric: "workflow_executions",
          metadata: expect.objectContaining({ execution_id: execution.id }),
        }),
      ]),
    );
    const audit = await request.get("/api/authorization/audit-events", {
      headers: authorization(adminToken),
    });
    expect(audit.status()).toBe(200);
    expect(await audit.text()).not.toContain(secret);

    // IDs de outro tenant nao podem ser lidos, executados nem removidos.
    const homeSelection = await readJson<{ access_token: string }>(
      await request.post("/api/auth/select-company", {
        headers: authorization(adminToken),
        data: { company_id: homeCompanyId },
      }),
    );
    const homeToken = homeSelection.access_token;
    for (const operation of [
      request.get(`/api/agents/${agent.id}`, {
        headers: authorization(homeToken),
      }),
      request.delete(`/api/agents/${agent.id}`, {
        headers: authorization(homeToken),
      }),
      request.get(`/api/workflows/${workflow.id}`, {
        headers: authorization(homeToken),
      }),
      request.post(`/api/workflows/${workflow.id}/execute`, {
        headers: authorization(homeToken),
        data: { input: {} },
      }),
      request.get(`/api/knowledge-bases/${knowledgeBase.id}/documents`, {
        headers: authorization(homeToken),
      }),
    ]) {
      expect((await operation).status()).toBe(404);
    }
  });
});
