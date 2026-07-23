from __future__ import annotations

import asyncio
from typing import cast

from sqlalchemy import select

from app.core.config import get_settings
from app.core.resources import create_resources
from app.core.security import hash_password
from app.modules.authorization.service import ensure_company_system_roles
from app.modules.companies.models import Company
from app.modules.users.models import CompanyUser, User


async def bootstrap() -> None:
    settings = get_settings()
    if not settings.bootstrap_enabled:
        return
    required = {
        "BOOTSTRAP_ADMIN_NAME": settings.bootstrap_admin_name,
        "BOOTSTRAP_ADMIN_EMAIL": settings.bootstrap_admin_email,
        "BOOTSTRAP_ADMIN_PASSWORD": settings.effective_bootstrap_admin_password,
        "BOOTSTRAP_COMPANY_NAME": settings.bootstrap_company_name,
        "BOOTSTRAP_COMPANY_SLUG": settings.bootstrap_company_slug,
        "BOOTSTRAP_COMPANY_DOCUMENT": settings.bootstrap_company_document,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Bootstrap incompleto: {', '.join(missing)}")
    admin_name = cast(str, required["BOOTSTRAP_ADMIN_NAME"])
    admin_email = cast(str, required["BOOTSTRAP_ADMIN_EMAIL"])
    admin_password = cast(str, required["BOOTSTRAP_ADMIN_PASSWORD"])
    company_name = cast(str, required["BOOTSTRAP_COMPANY_NAME"])
    company_slug = cast(str, required["BOOTSTRAP_COMPANY_SLUG"])
    company_document = cast(str, required["BOOTSTRAP_COMPANY_DOCUMENT"])

    resources = create_resources(settings, database_role="migration")
    try:
        async with resources.sessions() as database:
            company = await database.scalar(select(Company).where(Company.slug == company_slug))
            if company is None:
                company = Company(
                    legal_name=company_name,
                    trade_name=company_name,
                    document_number=company_document,
                    slug=company_slug,
                    status="active",
                )
                database.add(company)
                await database.flush()

            owner_role, _ = await ensure_company_system_roles(database, company.id)

            user = await database.scalar(select(User).where(User.email == admin_email))
            if user is None:
                user = User(
                    name=admin_name,
                    email=admin_email.lower(),
                    password_hash=hash_password(admin_password),
                    status="active",
                    is_platform_admin=True,
                )
                database.add(user)
                await database.flush()
            elif settings.app_env == "local":
                user.password_hash = hash_password(admin_password)

            membership = await database.scalar(
                select(CompanyUser).where(
                    CompanyUser.company_id == company.id,
                    CompanyUser.user_id == user.id,
                )
            )
            if membership is None:
                database.add(
                    CompanyUser(
                        company_id=company.id,
                        user_id=user.id,
                        role_id=owner_role.id,
                        status="active",
                        is_owner=True,
                    )
                )
            else:
                membership.role_id = owner_role.id
            await database.commit()
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
