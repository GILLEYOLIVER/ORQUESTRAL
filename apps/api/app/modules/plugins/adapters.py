from __future__ import annotations

import asyncio
import imaplib
import smtplib
from collections.abc import Mapping
from typing import Any

import asyncpg
import httpx
from orkestral_plugin_sdk import (
    BasePlugin,
    ConnectionTestResult,
    PluginDefinition,
    PluginField,
    PluginRegistry,
    PluginSDKError,
    PluginTool,
    PluginValidationError,
)

from app.modules.plugins.managed_vault import (
    ManagedVaultResolutionError,
    ManagedVaultSecretResolver,
)


class PluginAdapterError(PluginValidationError):
    pass


class HttpAdapter(BasePlugin):
    definition = PluginDefinition(
        code="rest_api",
        name="API REST genérica",
        version="1.0.0",
        description="Integração segura com APIs HTTP externas.",
        authentication_type="api_key",
        credential_fields=(
            PluginField("base_url", "URL base", "url", placeholder="https://api.exemplo.com"),
            PluginField("api_key", "Chave da API", "password", required=False, secret=True),
            PluginField(
                "auth_header", "Cabeçalho de autenticação", required=False, default="Authorization"
            ),
        ),
        tools=(PluginTool("request", "Requisição HTTP", "Executa uma chamada autenticada."),),
        actions=("request",),
    )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        url = str(credentials.get("base_url") or credentials.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise PluginAdapterError("Informe uma URL HTTP ou HTTPS válida.")
        headers = credentials.get("headers") or {}
        if not isinstance(headers, dict):
            raise PluginAdapterError("O campo headers deve ser um objeto.")
        api_key = str(credentials.get("api_key", ""))
        if api_key:
            header_name = str(credentials.get("auth_header") or "Authorization")
            headers[header_name] = api_key
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url, headers={str(k): str(v) for k, v in headers.items()})
        if response.status_code >= 500:
            return ConnectionTestResult(
                False, f"O destino respondeu com HTTP {response.status_code}."
            )
        return ConnectionTestResult(
            True, f"Conexão HTTP validada com status {response.status_code}."
        )


class WebhookAdapter(HttpAdapter):
    definition = PluginDefinition(
        code="generic_webhook",
        name="Webhook genérico",
        version="1.0.0",
        description="Recebe e envia eventos HTTP assinados.",
        authentication_type="secret",
        credential_fields=(
            PluginField("url", "URL de destino", "url", placeholder="https://exemplo.com/webhook"),
            PluginField(
                "signing_secret", "Segredo de assinatura", "password", required=False, secret=True
            ),
        ),
        tools=(PluginTool("send", "Enviar webhook", "Envia um evento HTTP assinado."),),
        triggers=("receive",),
        actions=("send",),
        supports_webhooks=True,
    )


class SmtpAdapter(BasePlugin):
    definition = PluginDefinition(
        code="smtp_email",
        name="E-mail SMTP",
        version="1.0.0",
        description="Envio de mensagens por servidor SMTP.",
        authentication_type="username_password",
        credential_fields=(
            PluginField("host", "Servidor SMTP"),
            PluginField("port", "Porta", "integer", default=587),
            PluginField("username", "Usuário", required=False),
            PluginField("password", "Senha", "password", required=False, secret=True),
            PluginField("use_tls", "Usar STARTTLS", "boolean", required=False, default=True),
        ),
        tools=(
            PluginTool("send_email", "Enviar e-mail", "Envia uma mensagem pelo SMTP configurado."),
        ),
        actions=("send_email",),
    )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        host = str(credentials.get("host", "")).strip()
        if not host:
            raise PluginAdapterError("Informe o servidor SMTP.")
        port = int(credentials.get("port") or 587)
        username = str(credentials.get("username", "")).strip()
        password = str(credentials.get("password", ""))
        use_tls = str(credentials.get("use_tls", "true")).lower() not in {"false", "0", "no"}

        def connect() -> None:
            with smtplib.SMTP(host=host, port=port, timeout=5) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if username:
                    smtp.login(username, password)

        await asyncio.to_thread(connect)
        return ConnectionTestResult(True, "Conexão SMTP validada com sucesso.")


class ImapAdapter(BasePlugin):
    definition = PluginDefinition(
        code="imap_email",
        name="E-mail IMAP",
        version="1.0.0",
        description="Leitura de caixas de e-mail via IMAP ou provedor compatível.",
        authentication_type="username_password",
        credential_fields=(
            PluginField("host", "Servidor IMAP"),
            PluginField("port", "Porta", "integer", default=993),
            PluginField("username", "Usuário"),
            PluginField("password", "Senha ou token", "password", secret=True),
            PluginField("use_ssl", "Usar SSL", "boolean", required=False, default=True),
        ),
        triggers=("email_received",),
    )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        host = str(credentials.get("host", "")).strip()
        port = int(credentials.get("port") or 993)
        username = str(credentials.get("username", ""))
        password = str(credentials.get("password", ""))
        use_ssl = str(credentials.get("use_ssl", "true")).lower() not in {"false", "0", "no"}

        def connect() -> None:
            client: imaplib.IMAP4
            client = (
                imaplib.IMAP4_SSL(host, port, timeout=5)
                if use_ssl
                else imaplib.IMAP4(host, port, timeout=5)
            )
            try:
                client.login(username, password)
            finally:
                try:
                    client.logout()
                except imaplib.IMAP4.error:
                    pass

        await asyncio.to_thread(connect)
        return ConnectionTestResult(True, "Conexão IMAP validada com sucesso.")


class GoogleCalendarAdapter(BasePlugin):
    definition = PluginDefinition(
        code="google_calendar",
        name="Google Calendar",
        version="1.0.0",
        description="Agenda e eventos do Google por OAuth 2.0.",
        authentication_type="oauth2",
        credential_fields=(
            PluginField("access_token", "Token de acesso OAuth", "password", secret=True),
            PluginField(
                "refresh_token", "Token de renovação", "password", required=False, secret=True
            ),
        ),
        tools=(PluginTool("calendar_event", "Gerenciar evento", "Cria e atualiza eventos."),),
        triggers=("event_changed",),
        actions=("list_events", "create_event", "update_event"),
        supports_token_refresh=True,
        supports_webhooks=True,
    )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        token = str(credentials.get("access_token", ""))
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://www.googleapis.com/calendar/v3/users/me/calendarList",
                params={"maxResults": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            return ConnectionTestResult(
                False, f"Google Calendar respondeu com HTTP {response.status_code}."
            )
        return ConnectionTestResult(True, "Conexão com Google Calendar validada.")


class WhatsAppBusinessAdapter(BasePlugin):
    definition = PluginDefinition(
        code="whatsapp_business",
        name="WhatsApp Business",
        version="1.0.0",
        description="Mensagens pela API oficial do WhatsApp Business.",
        authentication_type="oauth2",
        credential_fields=(
            PluginField("access_token", "Token de acesso", "password", secret=True),
            PluginField("phone_number_id", "ID do número de telefone"),
            PluginField("api_version", "Versão da Graph API", placeholder="vXX.X"),
        ),
        tools=(
            PluginTool("send_message", "Enviar mensagem", "Envia mensagem pelo provedor oficial."),
        ),
        triggers=("message_received", "message_status"),
        actions=("send_message",),
        supports_token_refresh=True,
        supports_webhooks=True,
    )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        version = str(credentials.get("api_version", "")).strip("/")
        phone_number_id = str(credentials.get("phone_number_id", ""))
        token = str(credentials.get("access_token", ""))
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"https://graph.facebook.com/{version}/{phone_number_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            return ConnectionTestResult(
                False, f"WhatsApp Business respondeu com HTTP {response.status_code}."
            )
        return ConnectionTestResult(True, "Conexão com WhatsApp Business validada.")


class ExternalPostgresAdapter(BasePlugin):
    definition = PluginDefinition(
        code="external_postgresql",
        name="PostgreSQL externo",
        version="1.0.0",
        description="Acesso controlado a um banco PostgreSQL externo.",
        authentication_type="connection_string",
        credential_fields=(
            PluginField(
                "dsn", "String de conexão", "password", secret=True, placeholder="postgresql://..."
            ),
        ),
        tools=(
            PluginTool(
                "query", "Consulta PostgreSQL", "Executa consultas permitidas no banco externo."
            ),
        ),
        actions=("query",),
    )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        dsn = str(credentials.get("dsn", ""))
        connection = await asyncpg.connect(dsn=dsn, timeout=5.0)
        try:
            await connection.fetchval("SELECT 1")
        finally:
            await connection.close()
        return ConnectionTestResult(True, "Conexão PostgreSQL validada com sucesso.")


MANAGED_VAULT_PROVIDERS: dict[str, tuple[str, str]] = {
    "aws_secrets_manager": ("AWS Secrets Manager", "aws-sm://"),
    "azure_key_vault": ("Azure Key Vault", "azure-kv://"),
    "google_secret_manager": ("Google Secret Manager", "gcp-sm://"),
    "hashicorp_vault": ("HashiCorp Vault", "vault://"),
}


def managed_vault_provider(plugin_code: str) -> tuple[str, str] | None:
    return MANAGED_VAULT_PROVIDERS.get(plugin_code.lower())


def _managed_vault_definition(code: str, description: str) -> PluginDefinition:
    provider_name, reference_prefix = MANAGED_VAULT_PROVIDERS[code]
    return PluginDefinition(
        code=code,
        name=provider_name,
        version="1.0.0",
        description=description,
        authentication_type="workload_identity",
        credential_fields=(
            PluginField(
                "key_reference",
                "Referência da chave",
                "password",
                secret=True,
                placeholder=f"{reference_prefix}caminho/da/chave",
            ),
            PluginField(
                "identity_reference",
                "Identidade gerenciada ou papel",
                required=False,
            ),
        ),
    )


class ManagedVaultAdapter(BasePlugin):
    reference_prefix: str

    def validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        super().validate_credentials(credentials)
        reference = str(credentials.get("key_reference", ""))
        invalid = (
            len(reference) > 512
            or not reference.startswith(self.reference_prefix)
            or reference == self.reference_prefix
            or reference != reference.strip()
            or any(character.isspace() for character in reference)
            or any(character in reference for character in ("?", "#", "@"))
        )
        if invalid:
            raise PluginAdapterError(
                f"Use uma referência protegida iniciada por {self.reference_prefix}, sem segredo embutido."
            )

    async def test_connection(
        self,
        credentials: Mapping[str, Any],
        configuration: Mapping[str, Any] | None = None,
    ) -> ConnectionTestResult:
        self.validate_credentials(credentials)
        try:
            await ManagedVaultSecretResolver().resolve(
                str(credentials["key_reference"]),
                identity_reference=str(credentials.get("identity_reference", "")).strip() or None,
            )
        except ManagedVaultResolutionError as exc:
            raise PluginAdapterError(
                "A identidade gerenciada não conseguiu acessar a referência protegida."
            ) from exc
        return ConnectionTestResult(
            True,
            "Identidade gerenciada e leitura protegida validadas com sucesso.",
        )


class AwsSecretsManagerAdapter(ManagedVaultAdapter):
    reference_prefix = "aws-sm://"
    definition = _managed_vault_definition(
        "aws_secrets_manager",
        "Referências de chaves protegidas pelo AWS Secrets Manager com identidade gerenciada.",
    )


class AzureKeyVaultAdapter(ManagedVaultAdapter):
    reference_prefix = "azure-kv://"
    definition = _managed_vault_definition(
        "azure_key_vault",
        "Referências de chaves protegidas pelo Azure Key Vault com identidade gerenciada.",
    )


class GoogleSecretManagerAdapter(ManagedVaultAdapter):
    reference_prefix = "gcp-sm://"
    definition = _managed_vault_definition(
        "google_secret_manager",
        "Referências de chaves protegidas pelo Google Secret Manager com identidade gerenciada.",
    )


class HashicorpVaultAdapter(ManagedVaultAdapter):
    reference_prefix = "vault://"
    definition = _managed_vault_definition(
        "hashicorp_vault",
        "Referências de chaves protegidas pelo HashiCorp Vault sem armazenar tokens na URI.",
    )


_RUNTIME = PluginRegistry()
for _adapter in (
    WebhookAdapter(),
    SmtpAdapter(),
    ImapAdapter(),
    GoogleCalendarAdapter(),
    WhatsAppBusinessAdapter(),
    ExternalPostgresAdapter(),
    HttpAdapter(),
    AwsSecretsManagerAdapter(),
    AzureKeyVaultAdapter(),
    GoogleSecretManagerAdapter(),
    HashicorpVaultAdapter(),
):
    _RUNTIME.register(_adapter)

try:
    _RUNTIME.discover()
except PluginSDKError:
    # Um pacote externo inválido não impede o núcleo nem os plugins oficiais de iniciar.
    pass


def get_plugin_runtime() -> PluginRegistry:
    return _RUNTIME


def get_plugin_adapter(plugin_code: str) -> BasePlugin:
    try:
        plugin = _RUNTIME.get(plugin_code)
    except PluginSDKError as exc:
        raise PluginAdapterError(str(exc)) from exc
    return plugin  # type: ignore[return-value]
