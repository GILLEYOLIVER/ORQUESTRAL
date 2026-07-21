from __future__ import annotations

import hmac
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utc_now
from app.core.tenancy import RequestContext
from app.modules.authorization.service import record_authorization_audit
from app.modules.events.schemas import DomainEventCreate
from app.modules.events.service import enqueue_domain_event
from app.modules.metadata.models import (
    MetadataPackageCatalog,
    MetadataPackageInstallation,
    MetadataPackageVersion,
)
from app.modules.metadata.package_engine import (
    calculate_bundle_checksum,
    calculate_plan_checksum,
    can_promote,
    parse_semver,
)
from app.modules.metadata.package_lifecycle_repository import (
    get_package_catalog,
    get_package_installation,
    get_package_release,
    get_package_release_by_version,
    list_package_installations,
    list_package_releases,
)
from app.modules.metadata.package_lifecycle_schemas import (
    MetadataPackageDependency,
    MetadataPackageInstallationResponse,
    MetadataPackageInstallPreview,
    MetadataPackageInstallPreviewRequest,
    MetadataPackageInstallRequest,
    MetadataPackageManifest,
    MetadataPackagePromotionResponse,
    MetadataPackageReleaseBundle,
    MetadataPackageReleaseCreate,
    MetadataPackageReleaseResponse,
    MetadataPackageValidationResponse,
    PackageEnvironment,
    PackageInstallationStatus,
    PackageReleaseStatus,
)
from app.modules.metadata.package_schemas import MetadataEntityPackage, MetadataPackageImportRequest
from app.modules.metadata.package_service import (
    calculate_package_checksum,
    export_entity_package,
    import_entity_package,
)
from app.modules.metadata.repository import get_entity_definition_by_key
from app.modules.metadata.service import MetadataServiceError, get_entity


def _event(
    database: AsyncSession,
    *,
    event_type: str,
    context: RequestContext,
    correlation_id: UUID,
    target_id: UUID,
    package_key: str,
    version: str,
) -> None:
    enqueue_domain_event(
        database,
        DomainEventCreate(
            event_type=event_type,
            company_id=context.company_id,
            actor_user_id=context.user_id,
            correlation_id=correlation_id,
            classification="internal",
            payload={"target_id": str(target_id), "package_key": package_key, "version": version},
        ),
    )


def _dependencies(version: MetadataPackageVersion) -> list[MetadataPackageDependency]:
    return [MetadataPackageDependency.model_validate(item) for item in version.dependencies]


def _manifest(
    catalog: MetadataPackageCatalog, version: MetadataPackageVersion
) -> MetadataPackageManifest:
    return MetadataPackageManifest(
        package_key=catalog.key,
        display_name=catalog.name,
        description=catalog.description,
        version=version.version,
        source_environment=cast(PackageEnvironment, version.source_environment),
        dependencies=_dependencies(version),
    )


def _release_response(
    catalog: MetadataPackageCatalog, version: MetadataPackageVersion
) -> MetadataPackageReleaseResponse:
    return MetadataPackageReleaseResponse(
        id=version.id,
        package_catalog_id=catalog.id,
        entity_definition_id=version.entity_definition_id,
        package_key=catalog.key,
        display_name=catalog.name,
        description=catalog.description,
        version=version.version,
        status=cast(PackageReleaseStatus, version.status),
        source_environment=cast(PackageEnvironment, version.source_environment),
        dependencies=_dependencies(version),
        checksum=version.checksum,
        created_at=version.created_at,
        published_at=version.published_at,
    )


def _installation_response(
    installation: MetadataPackageInstallation,
) -> MetadataPackageInstallationResponse:
    return MetadataPackageInstallationResponse(
        id=installation.id,
        package_key=installation.package_key,
        package_version=installation.package_version,
        source_checksum=installation.source_checksum,
        target_environment=cast(PackageEnvironment, installation.target_environment),
        status=cast(PackageInstallationStatus, installation.status),
        installed_definition_id=installation.installed_definition_id,
        installed_at=installation.installed_at,
    )


def _bundle(
    catalog: MetadataPackageCatalog, version: MetadataPackageVersion
) -> MetadataPackageReleaseBundle:
    return MetadataPackageReleaseBundle(
        created_at=version.created_at,
        manifest=_manifest(catalog, version),
        artifact=MetadataEntityPackage.model_validate(version.artifact),
        checksum=version.checksum,
    )


async def create_package_release(
    database: AsyncSession,
    context: RequestContext,
    payload: MetadataPackageReleaseCreate,
    correlation_id: UUID,
    source_environment: PackageEnvironment,
) -> MetadataPackageReleaseResponse:
    parse_semver(payload.version)
    entity = await get_entity(database, context, payload.definition_id, correlation_id)
    if entity.published_version is None:
        raise MetadataServiceError(
            "Publique a entidade antes de criar uma versao do pacote.", status_code=409
        )
    package_key = payload.package_key or entity.key
    if any(
        item.package_key == package_key and item.version == payload.version
        for item in payload.dependencies
    ):
        raise MetadataServiceError("Um pacote nao pode depender de si mesmo.", status_code=422)
    if await get_package_release_by_version(
        database, context.company_id, package_key, payload.version
    ):
        raise MetadataServiceError("Esta versao do pacote ja existe.", status_code=409)
    artifact = await export_entity_package(database, context, payload.definition_id, correlation_id)
    catalog = await get_package_catalog(database, context.company_id, package_key)
    if catalog is None:
        catalog = MetadataPackageCatalog(
            company_id=context.company_id,
            key=package_key,
            name=payload.display_name or entity.label,
            description=payload.description or entity.description,
            created_by_user_id=context.user_id,
        )
        database.add(catalog)
        await database.flush()
    manifest = MetadataPackageManifest(
        package_key=catalog.key,
        display_name=catalog.name,
        description=catalog.description,
        version=payload.version,
        source_environment=source_environment,
        dependencies=payload.dependencies,
    )
    release = MetadataPackageVersion(
        company_id=context.company_id,
        package_catalog_id=catalog.id,
        entity_definition_id=payload.definition_id,
        version=payload.version,
        status="draft",
        source_environment=source_environment,
        dependencies=[item.model_dump(mode="json") for item in payload.dependencies],
        artifact=artifact.model_dump(mode="json"),
        checksum=calculate_bundle_checksum(manifest, artifact),
        created_by_user_id=context.user_id,
    )
    database.add(release)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.release_created",
        target_type="metadata_package_version",
        target_id=release.id,
        details={"package_key": package_key, "version": payload.version},
    )
    _event(
        database,
        event_type="metadata.package.release_created",
        context=context,
        correlation_id=correlation_id,
        target_id=release.id,
        package_key=package_key,
        version=payload.version,
    )
    await database.commit()
    await database.refresh(release)
    return _release_response(catalog, release)


async def get_package_releases(
    database: AsyncSession, context: RequestContext, definition_id: UUID | None
) -> list[MetadataPackageReleaseResponse]:
    rows = await list_package_releases(database, context.company_id, definition_id)
    return [_release_response(catalog, version) for catalog, version in rows]


async def validate_package_release(
    database: AsyncSession, context: RequestContext, release_id: UUID, correlation_id: UUID
) -> MetadataPackageValidationResponse:
    row = await get_package_release(database, context.company_id, release_id)
    if row is None:
        raise MetadataServiceError("Versao de pacote nao encontrada.", status_code=404)
    catalog, version = row
    errors: list[str] = []
    warnings: list[str] = []
    try:
        parse_semver(version.version)
        artifact = MetadataEntityPackage.model_validate(version.artifact)
        if calculate_package_checksum(artifact.definition) != artifact.checksum:
            errors.append("O artefato interno foi alterado ou esta corrompido.")
        if calculate_bundle_checksum(_manifest(catalog, version), artifact) != version.checksum:
            errors.append("O checksum da versao nao corresponde ao conteudo armazenado.")
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    for dependency in _dependencies(version):
        found = await get_package_release_by_version(
            database,
            context.company_id,
            dependency.package_key,
            dependency.version,
            published_only=True,
        )
        identity = f"{dependency.package_key}@{dependency.version}"
        if found is None and dependency.optional:
            warnings.append(f"Dependencia opcional {identity} ausente.")
        elif found is None:
            errors.append(f"Dependencia obrigatoria {identity} nao esta publicada.")
    if not errors and version.status == "draft":
        version.status = "validated"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.release_validated",
        target_type="metadata_package_version",
        target_id=version.id,
        details={"valid": not errors, "error_count": len(errors)},
    )
    _event(
        database,
        event_type="metadata.package.release_validated",
        context=context,
        correlation_id=correlation_id,
        target_id=version.id,
        package_key=catalog.key,
        version=version.version,
    )
    await database.commit()
    await database.refresh(version)
    return MetadataPackageValidationResponse(
        release=_release_response(catalog, version),
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


async def publish_package_release(
    database: AsyncSession, context: RequestContext, release_id: UUID, correlation_id: UUID
) -> MetadataPackageReleaseResponse:
    row = await get_package_release(database, context.company_id, release_id)
    if row is None:
        raise MetadataServiceError("Versao de pacote nao encontrada.", status_code=404)
    catalog, version = row
    if version.status != "validated":
        raise MetadataServiceError(
            "A versao precisa ser validada antes da publicacao.", status_code=409
        )
    version.status = "published"
    version.published_by_user_id = context.user_id
    version.published_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.release_published",
        target_type="metadata_package_version",
        target_id=version.id,
        details={"package_key": catalog.key, "version": version.version},
    )
    _event(
        database,
        event_type="metadata.package.release_published",
        context=context,
        correlation_id=correlation_id,
        target_id=version.id,
        package_key=catalog.key,
        version=version.version,
    )
    await database.commit()
    await database.refresh(version)
    return _release_response(catalog, version)


async def export_release_bundle(
    database: AsyncSession, context: RequestContext, release_id: UUID
) -> MetadataPackageReleaseBundle:
    row = await get_package_release(database, context.company_id, release_id)
    if row is None:
        raise MetadataServiceError("Versao de pacote nao encontrada.", status_code=404)
    catalog, version = row
    if version.status != "published":
        raise MetadataServiceError(
            "Somente versoes publicadas podem ser exportadas.", status_code=409
        )
    return _bundle(catalog, version)


async def preview_package_installation(
    database: AsyncSession,
    context: RequestContext,
    payload: MetadataPackageInstallPreviewRequest,
    current_environment: PackageEnvironment,
) -> MetadataPackageInstallPreview:
    bundle = payload.bundle
    blockers: list[str] = []
    warnings: list[str] = []
    resolved: list[str] = []
    if calculate_bundle_checksum(bundle.manifest, bundle.artifact) != bundle.checksum:
        blockers.append("O bundle foi alterado ou esta corrompido.")
    if calculate_package_checksum(bundle.artifact.definition) != bundle.artifact.checksum:
        blockers.append("O artefato interno do bundle esta corrompido.")
    if payload.target_environment != current_environment:
        blockers.append(
            f"Este servidor opera em {current_environment}; a instalacao aponta para {payload.target_environment}."
        )
    target_key = payload.key_override or bundle.artifact.definition.key
    if await get_entity_definition_by_key(database, context.company_id, target_key):
        blockers.append(f"Ja existe uma entidade com a chave '{target_key}'.")
    if await get_package_installation(
        database,
        context.company_id,
        bundle.manifest.package_key,
        bundle.manifest.version,
        payload.target_environment,
    ):
        blockers.append("Esta versao do pacote ja esta instalada neste ambiente.")
    for dependency in bundle.manifest.dependencies:
        installation = await get_package_installation(
            database,
            context.company_id,
            dependency.package_key,
            dependency.version,
            payload.target_environment,
        )
        identity = f"{dependency.package_key}@{dependency.version}"
        if installation is not None:
            resolved.append(identity)
        elif dependency.optional:
            warnings.append(f"Dependencia opcional {identity} nao esta instalada.")
        else:
            blockers.append(f"Dependencia obrigatoria {identity} nao esta instalada.")
    definition = bundle.artifact.definition
    actions = [
        f"Criar entidade {target_key}",
        f"Criar {len(definition.fields)} campos",
        f"Criar {len(definition.design.layouts)} layouts",
        f"Criar {len(definition.design.views)} visualizacoes",
        f"Criar {len(definition.design.validation_rules)} regras de validacao",
        f"Registrar instalacao {bundle.manifest.package_key}@{bundle.manifest.version}",
    ]
    plan_checksum = calculate_plan_checksum(
        {
            "bundle_checksum": bundle.checksum,
            "company_id": str(context.company_id),
            "target_environment": payload.target_environment,
            "target_key": target_key,
            "actions": actions,
            "blockers": blockers,
        }
    )
    return MetadataPackageInstallPreview(
        can_install=not blockers,
        package_key=bundle.manifest.package_key,
        version=bundle.manifest.version,
        target_environment=payload.target_environment,
        actions=actions,
        blockers=blockers,
        warnings=warnings,
        resolved_dependencies=resolved,
        plan_checksum=plan_checksum,
    )


async def install_package_release(
    database: AsyncSession,
    context: RequestContext,
    payload: MetadataPackageInstallRequest,
    correlation_id: UUID,
    current_environment: PackageEnvironment,
) -> MetadataPackageInstallationResponse:
    preview = await preview_package_installation(
        database,
        context,
        MetadataPackageInstallPreviewRequest(
            bundle=payload.bundle,
            target_environment=payload.target_environment,
            key_override=payload.key_override,
        ),
        current_environment,
    )
    if not hmac.compare_digest(preview.plan_checksum, payload.plan_checksum):
        raise MetadataServiceError(
            "A previa mudou. Gere uma nova previa antes de instalar.", status_code=409
        )
    if not preview.can_install:
        raise MetadataServiceError("A instalacao possui bloqueios pendentes.", status_code=422)
    imported = await import_entity_package(
        database,
        context,
        MetadataPackageImportRequest(
            package=payload.bundle.artifact, key_override=payload.key_override
        ),
        correlation_id,
    )
    installation = MetadataPackageInstallation(
        company_id=context.company_id,
        package_key=payload.bundle.manifest.package_key,
        package_version=payload.bundle.manifest.version,
        source_checksum=payload.bundle.checksum,
        target_environment=payload.target_environment,
        status="installed",
        installed_definition_id=imported.id,
        installed_by_user_id=context.user_id,
    )
    database.add(installation)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.installed",
        target_type="metadata_package_installation",
        target_id=installation.id,
        details={
            "package_key": installation.package_key,
            "version": installation.package_version,
            "environment": installation.target_environment,
        },
    )
    _event(
        database,
        event_type="metadata.package.installed",
        context=context,
        correlation_id=correlation_id,
        target_id=installation.id,
        package_key=installation.package_key,
        version=installation.package_version,
    )
    await database.commit()
    await database.refresh(installation)
    return _installation_response(installation)


async def get_package_installations(
    database: AsyncSession, context: RequestContext
) -> list[MetadataPackageInstallationResponse]:
    rows = await list_package_installations(database, context.company_id)
    return [_installation_response(item) for item in rows]


async def prepare_package_promotion(
    database: AsyncSession,
    context: RequestContext,
    release_id: UUID,
    target_environment: PackageEnvironment,
    current_environment: PackageEnvironment,
    correlation_id: UUID,
) -> MetadataPackagePromotionResponse:
    row = await get_package_release(database, context.company_id, release_id)
    if row is None:
        raise MetadataServiceError("Versao de pacote nao encontrada.", status_code=404)
    catalog, version = row
    blockers: list[str] = []
    if version.status != "published":
        blockers.append("Somente versoes publicadas podem ser promovidas.")
    if version.source_environment != current_environment:
        blockers.append("A versao nao foi criada no ambiente que prepara a promocao.")
    if not can_promote(current_environment, target_environment):
        blockers.append(
            f"Promocao direta de {current_environment} para {target_environment} nao e permitida."
        )
    bundle = _bundle(catalog, version) if not blockers else None
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="metadata.package.promotion_prepared",
        target_type="metadata_package_version",
        target_id=version.id,
        details={
            "source_environment": current_environment,
            "target_environment": target_environment,
            "allowed": not blockers,
        },
    )
    _event(
        database,
        event_type="metadata.package.promotion_prepared",
        context=context,
        correlation_id=correlation_id,
        target_id=version.id,
        package_key=catalog.key,
        version=version.version,
    )
    await database.commit()
    return MetadataPackagePromotionResponse(
        allowed=not blockers,
        source_environment=current_environment,
        target_environment=target_environment,
        blockers=blockers,
        instructions=(
            "Importe este bundle no ambiente de destino, gere a previa e confirme a instalacao."
            if not blockers
            else "Corrija os bloqueios antes de preparar a promocao."
        ),
        bundle=bundle,
    )
