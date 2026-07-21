from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import DatabaseSession, RequestSettings
from app.core.field_encryption import FieldDecryptionError, decrypt_text, encrypt_text
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.modularity.dependencies import require_active_module
from app.modules.projects.models import (
    Project,
    ProjectMember,
    ProjectMilestone,
    ProjectPortfolio,
    ProjectRisk,
    ProjectTask,
    ProjectTaskDependency,
)
from app.modules.projects.schemas import (
    ProjectGovernanceUpdate,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMilestoneCreate,
    ProjectMilestoneResponse,
    ProjectMilestoneUpdate,
    ProjectPortfolioCreate,
    ProjectPortfolioResponse,
    ProjectPortfolioSummary,
    ProjectResponse,
    ProjectRiskCreate,
    ProjectRiskResponse,
    ProjectRiskUpdate,
    ProjectTaskDependencyCreate,
    ProjectTaskDependencyResponse,
    ProjectTaskPlanningUpdate,
    ProjectTaskResponse,
)
from app.modules.users.models import CompanyUser

router = APIRouter(prefix="/projects", tags=["project-portfolio"])

ActiveProjects = Annotated[Principal, Depends(require_active_module("projects"))]
CanViewProjects = Annotated[Principal, Depends(require_permission("projects.view"))]
CanCreateProjects = Annotated[Principal, Depends(require_permission("projects.create"))]
CanUpdateProjects = Annotated[Principal, Depends(require_permission("projects.update"))]
CanManageTasks = Annotated[Principal, Depends(require_permission("projects.tasks.manage"))]


async def _project(database: DatabaseSession, company_id: UUID, project_id: UUID) -> Project:
    project = await database.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company_id,
            Project.archived_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return project


async def _task(
    database: DatabaseSession, company_id: UUID, project_id: UUID, task_id: UUID
) -> ProjectTask:
    task = await database.scalar(
        select(ProjectTask).where(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id,
            ProjectTask.company_id == company_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return task


async def _validate_member(
    database: DatabaseSession, company_id: UUID, user_id: UUID | None
) -> None:
    if user_id is None:
        return
    membership = await database.scalar(
        select(CompanyUser.id).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
            CompanyUser.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="Usuário não pertence à empresa atual.")


async def _project_response(database: DatabaseSession, project: Project) -> ProjectResponse:
    tasks = list(
        await database.scalars(select(ProjectTask).where(ProjectTask.project_id == project.id))
    )
    done = sum(task.status == "done" for task in tasks)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        priority=project.priority,
        portfolio_id=project.portfolio_id,
        owner_user_id=project.owner_user_id,
        health=project.health,
        budget_cents=project.budget_cents,
        version=project.version,
        start_date=project.start_date,
        due_date=project.due_date,
        completed_at=project.completed_at,
        task_total=len(tasks),
        task_done=done,
        progress_percent=round(done / len(tasks) * 100) if tasks else 0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def _milestone_response(
    database: DatabaseSession, milestone: ProjectMilestone
) -> ProjectMilestoneResponse:
    tasks = list(
        await database.scalars(select(ProjectTask).where(ProjectTask.milestone_id == milestone.id))
    )
    return ProjectMilestoneResponse(
        id=milestone.id,
        project_id=milestone.project_id,
        name=milestone.name,
        description=milestone.description,
        due_date=milestone.due_date,
        status=milestone.status,
        completed_at=milestone.completed_at,
        task_total=len(tasks),
        task_done=sum(task.status == "done" for task in tasks),
    )


def _risk_response(risk: ProjectRisk, settings: RequestSettings) -> ProjectRiskResponse:
    aad = f"{risk.company_id}:project-risk"
    try:
        description = decrypt_text(settings, risk.description_encrypted, associated_data=aad)
        mitigation = (
            decrypt_text(settings, risk.mitigation_encrypted, associated_data=aad)
            if risk.mitigation_encrypted
            else None
        )
    except FieldDecryptionError as exc:
        raise HTTPException(
            status_code=409,
            detail="O registro sensível não pôde ser autenticado. Acione a administração.",
        ) from exc
    return ProjectRiskResponse(
        id=risk.id,
        project_id=risk.project_id,
        owner_user_id=risk.owner_user_id,
        title=risk.title,
        description=description,
        mitigation=mitigation,
        probability=risk.probability,
        impact=risk.impact,
        score=risk.probability * risk.impact,
        status=risk.status,
        created_at=risk.created_at,
        updated_at=risk.updated_at,
    )


@router.get("/portfolio-summary", response_model=ProjectPortfolioSummary)
async def portfolio_summary(
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectPortfolioSummary:
    context = get_request_context(principal)
    projects = list(
        await database.scalars(
            select(Project).where(
                Project.company_id == context.company_id,
                Project.archived_at.is_(None),
            )
        )
    )
    risks = list(
        await database.scalars(
            select(ProjectRisk).where(ProjectRisk.company_id == context.company_id)
        )
    )
    milestones = list(
        await database.scalars(
            select(ProjectMilestone).where(ProjectMilestone.company_id == context.company_id)
        )
    )
    tasks = list(
        await database.scalars(
            select(ProjectTask).where(ProjectTask.company_id == context.company_id)
        )
    )
    portfolio_count = await database.scalar(
        select(func.count(ProjectPortfolio.id)).where(
            ProjectPortfolio.company_id == context.company_id,
            ProjectPortfolio.is_active.is_(True),
        )
    )
    today = date.today()
    return ProjectPortfolioSummary(
        portfolio_count=int(portfolio_count or 0),
        project_count=len(projects),
        active_projects=sum(project.status == "active" for project in projects),
        overdue_projects=sum(
            project.due_date is not None
            and project.due_date < today
            and project.status not in {"completed", "cancelled"}
            for project in projects
        ),
        at_risk_projects=sum(project.health in {"at_risk", "off_track"} for project in projects),
        open_risks=sum(risk.status in {"open", "mitigating"} for risk in risks),
        critical_risks=sum(
            risk.status in {"open", "mitigating"} and risk.probability * risk.impact >= 15
            for risk in risks
        ),
        milestone_count=len(milestones),
        overdue_milestones=sum(
            milestone.due_date < today and milestone.status not in {"completed", "cancelled"}
            for milestone in milestones
        ),
        planned_minutes=sum(task.estimated_minutes for task in tasks),
        actual_minutes=sum(task.actual_minutes for task in tasks),
    )


@router.get("/portfolios", response_model=list[ProjectPortfolioResponse])
async def list_portfolios(
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> list[ProjectPortfolioResponse]:
    context = get_request_context(principal)
    portfolios = list(
        await database.scalars(
            select(ProjectPortfolio)
            .where(
                ProjectPortfolio.company_id == context.company_id,
                ProjectPortfolio.is_active.is_(True),
            )
            .order_by(ProjectPortfolio.name)
        )
    )
    projects = list(
        await database.scalars(
            select(Project).where(
                Project.company_id == context.company_id,
                Project.archived_at.is_(None),
            )
        )
    )
    return [
        ProjectPortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            objective=portfolio.objective,
            budget_cents=portfolio.budget_cents,
            is_active=portfolio.is_active,
            project_count=sum(project.portfolio_id == portfolio.id for project in projects),
            active_projects=sum(
                project.portfolio_id == portfolio.id and project.status == "active"
                for project in projects
            ),
            at_risk_projects=sum(
                project.portfolio_id == portfolio.id and project.health in {"at_risk", "off_track"}
                for project in projects
            ),
        )
        for portfolio in portfolios
    ]


@router.post(
    "/portfolios",
    response_model=ProjectPortfolioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_portfolio(
    payload: ProjectPortfolioCreate,
    principal: CanCreateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectPortfolioResponse:
    context = get_request_context(principal)
    portfolio = ProjectPortfolio(company_id=context.company_id, **payload.model_dump())
    database.add(portfolio)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(
            status_code=409, detail="Já existe um portfólio com este nome."
        ) from exc
    await database.refresh(portfolio)
    return ProjectPortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        objective=portfolio.objective,
        budget_cents=portfolio.budget_cents,
        is_active=portfolio.is_active,
        project_count=0,
        active_projects=0,
        at_risk_projects=0,
    )


@router.get("/{project_id}/governance", response_model=ProjectResponse)
async def get_governance(
    project_id: UUID,
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectResponse:
    context = get_request_context(principal)
    project = await _project(database, context.company_id, project_id)
    return await _project_response(database, project)


@router.patch("/{project_id}/governance", response_model=ProjectResponse)
async def update_governance(
    project_id: UUID,
    payload: ProjectGovernanceUpdate,
    principal: CanUpdateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectResponse:
    context = get_request_context(principal)
    project = await _project(database, context.company_id, project_id)
    if payload.portfolio_id is not None:
        portfolio = await database.scalar(
            select(ProjectPortfolio.id).where(
                ProjectPortfolio.id == payload.portfolio_id,
                ProjectPortfolio.company_id == context.company_id,
                ProjectPortfolio.is_active.is_(True),
            )
        )
        if portfolio is None:
            raise HTTPException(status_code=422, detail="Portfólio inválido para esta empresa.")
    await _validate_member(database, context.company_id, payload.owner_user_id)
    changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    updated_project_id = await database.scalar(
        update(Project)
        .where(
            Project.id == project.id,
            Project.company_id == context.company_id,
            Project.version == payload.expected_version,
        )
        .values(**changes, version=Project.version + 1, updated_at=utc_now())
        .returning(Project.id)
    )
    if updated_project_id is None:
        await database.rollback()
        raise HTTPException(
            status_code=409,
            detail="O projeto foi alterado por outra pessoa. Atualize a página antes de salvar.",
        )
    await database.commit()
    refreshed = await _project(database, context.company_id, project_id)
    return await _project_response(database, refreshed)


@router.get("/{project_id}/milestones", response_model=list[ProjectMilestoneResponse])
async def list_milestones(
    project_id: UUID,
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> list[ProjectMilestoneResponse]:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    milestones = list(
        await database.scalars(
            select(ProjectMilestone)
            .where(
                ProjectMilestone.company_id == context.company_id,
                ProjectMilestone.project_id == project_id,
            )
            .order_by(ProjectMilestone.due_date)
        )
    )
    return [await _milestone_response(database, milestone) for milestone in milestones]


@router.post(
    "/{project_id}/milestones",
    response_model=ProjectMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    project_id: UUID,
    payload: ProjectMilestoneCreate,
    principal: CanUpdateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectMilestoneResponse:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    milestone = ProjectMilestone(
        company_id=context.company_id,
        project_id=project_id,
        **payload.model_dump(),
    )
    database.add(milestone)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Já existe um marco com este nome.") from exc
    await database.refresh(milestone)
    return await _milestone_response(database, milestone)


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=ProjectMilestoneResponse)
async def update_milestone(
    project_id: UUID,
    milestone_id: UUID,
    payload: ProjectMilestoneUpdate,
    principal: CanUpdateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectMilestoneResponse:
    context = get_request_context(principal)
    milestone = await database.scalar(
        select(ProjectMilestone).where(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.company_id == context.company_id,
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Marco não encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    if milestone.status == "completed":
        milestone.completed_at = milestone.completed_at or utc_now()
    elif "status" in payload.model_fields_set:
        milestone.completed_at = None
    await database.commit()
    await database.refresh(milestone)
    return await _milestone_response(database, milestone)


@router.get("/{project_id}/risks", response_model=list[ProjectRiskResponse])
async def list_risks(
    project_id: UUID,
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
    settings: RequestSettings,
) -> list[ProjectRiskResponse]:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    risks = list(
        await database.scalars(
            select(ProjectRisk)
            .where(
                ProjectRisk.company_id == context.company_id,
                ProjectRisk.project_id == project_id,
            )
            .order_by((ProjectRisk.probability * ProjectRisk.impact).desc())
        )
    )
    return [_risk_response(risk, settings) for risk in risks]


@router.post(
    "/{project_id}/risks",
    response_model=ProjectRiskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_risk(
    project_id: UUID,
    payload: ProjectRiskCreate,
    principal: CanUpdateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
    settings: RequestSettings,
) -> ProjectRiskResponse:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    await _validate_member(database, context.company_id, payload.owner_user_id)
    aad = f"{context.company_id}:project-risk"
    risk = ProjectRisk(
        company_id=context.company_id,
        project_id=project_id,
        owner_user_id=payload.owner_user_id,
        title=payload.title,
        description_encrypted=encrypt_text(settings, payload.description, associated_data=aad),
        mitigation_encrypted=encrypt_text(settings, payload.mitigation, associated_data=aad)
        if payload.mitigation
        else None,
        probability=payload.probability,
        impact=payload.impact,
    )
    database.add(risk)
    await database.commit()
    await database.refresh(risk)
    return _risk_response(risk, settings)


@router.patch("/{project_id}/risks/{risk_id}", response_model=ProjectRiskResponse)
async def update_risk(
    project_id: UUID,
    risk_id: UUID,
    payload: ProjectRiskUpdate,
    principal: CanUpdateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
    settings: RequestSettings,
) -> ProjectRiskResponse:
    context = get_request_context(principal)
    risk = await database.scalar(
        select(ProjectRisk).where(
            ProjectRisk.id == risk_id,
            ProjectRisk.project_id == project_id,
            ProjectRisk.company_id == context.company_id,
        )
    )
    if risk is None:
        raise HTTPException(status_code=404, detail="Risco não encontrado.")
    if payload.owner_user_id is not None:
        await _validate_member(database, context.company_id, payload.owner_user_id)
        risk.owner_user_id = payload.owner_user_id
    if payload.status is not None:
        risk.status = payload.status
    if "mitigation" in payload.model_fields_set:
        risk.mitigation_encrypted = (
            encrypt_text(
                settings,
                payload.mitigation,
                associated_data=f"{context.company_id}:project-risk",
            )
            if payload.mitigation
            else None
        )
    await database.commit()
    await database.refresh(risk)
    return _risk_response(risk, settings)


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_members(
    project_id: UUID,
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> list[ProjectMemberResponse]:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    members = list(
        await database.scalars(
            select(ProjectMember).where(
                ProjectMember.company_id == context.company_id,
                ProjectMember.project_id == project_id,
            )
        )
    )
    return [
        ProjectMemberResponse.model_validate(member, from_attributes=True) for member in members
    ]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse)
async def upsert_member(
    project_id: UUID,
    payload: ProjectMemberCreate,
    principal: CanUpdateProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectMemberResponse:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    await _validate_member(database, context.company_id, payload.user_id)
    member = await database.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == payload.user_id,
            ProjectMember.company_id == context.company_id,
        )
    )
    if member is None:
        member = ProjectMember(
            company_id=context.company_id,
            project_id=project_id,
            **payload.model_dump(),
        )
        database.add(member)
    else:
        member.role = payload.role
        member.allocation_percent = payload.allocation_percent
    await database.commit()
    await database.refresh(member)
    return ProjectMemberResponse.model_validate(member, from_attributes=True)


@router.patch("/{project_id}/tasks/{task_id}/planning", response_model=ProjectTaskResponse)
async def update_task_planning(
    project_id: UUID,
    task_id: UUID,
    payload: ProjectTaskPlanningUpdate,
    principal: CanManageTasks,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectTaskResponse:
    context = get_request_context(principal)
    task = await _task(database, context.company_id, project_id, task_id)
    await _validate_member(database, context.company_id, payload.assignee_user_id)
    if payload.milestone_id is not None:
        milestone = await database.scalar(
            select(ProjectMilestone.id).where(
                ProjectMilestone.id == payload.milestone_id,
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.company_id == context.company_id,
            )
        )
        if milestone is None:
            raise HTTPException(status_code=422, detail="Marco inválido para este projeto.")
    changes = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    updated_task_id = await database.scalar(
        update(ProjectTask)
        .where(
            ProjectTask.id == task.id,
            ProjectTask.company_id == context.company_id,
            ProjectTask.version == payload.expected_version,
        )
        .values(**changes, version=ProjectTask.version + 1, updated_at=utc_now())
        .returning(ProjectTask.id)
    )
    if updated_task_id is None:
        await database.rollback()
        raise HTTPException(status_code=409, detail="A tarefa foi alterada em outra sessão.")
    await database.commit()
    refreshed = await _task(database, context.company_id, project_id, task_id)
    return ProjectTaskResponse.model_validate(refreshed, from_attributes=True)


@router.get("/{project_id}/dependencies", response_model=list[ProjectTaskDependencyResponse])
async def list_dependencies(
    project_id: UUID,
    principal: CanViewProjects,
    _: ActiveProjects,
    database: DatabaseSession,
) -> list[ProjectTaskDependencyResponse]:
    context = get_request_context(principal)
    await _project(database, context.company_id, project_id)
    items = list(
        await database.scalars(
            select(ProjectTaskDependency).where(
                ProjectTaskDependency.company_id == context.company_id,
                ProjectTaskDependency.project_id == project_id,
            )
        )
    )
    return [
        ProjectTaskDependencyResponse.model_validate(item, from_attributes=True) for item in items
    ]


@router.post(
    "/{project_id}/dependencies",
    response_model=ProjectTaskDependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dependency(
    project_id: UUID,
    payload: ProjectTaskDependencyCreate,
    principal: CanManageTasks,
    _: ActiveProjects,
    database: DatabaseSession,
) -> ProjectTaskDependencyResponse:
    context = get_request_context(principal)
    await _task(database, context.company_id, project_id, payload.predecessor_task_id)
    await _task(database, context.company_id, project_id, payload.successor_task_id)
    existing = list(
        await database.scalars(
            select(ProjectTaskDependency).where(
                ProjectTaskDependency.company_id == context.company_id,
                ProjectTaskDependency.project_id == project_id,
            )
        )
    )
    graph: dict[UUID, set[UUID]] = {}
    for item in existing:
        graph.setdefault(item.predecessor_task_id, set()).add(item.successor_task_id)
    pending = [payload.successor_task_id]
    visited: set[UUID] = set()
    while pending:
        current = pending.pop()
        if current == payload.predecessor_task_id:
            raise HTTPException(
                status_code=409, detail="A dependência criaria um ciclo no projeto."
            )
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph.get(current, set()))
    dependency = ProjectTaskDependency(
        company_id=context.company_id,
        project_id=project_id,
        **payload.model_dump(),
    )
    database.add(dependency)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status_code=409, detail="Dependência já cadastrada.") from exc
    await database.refresh(dependency)
    return ProjectTaskDependencyResponse.model_validate(dependency, from_attributes=True)


@router.delete("/{project_id}/dependencies/{dependency_id}", status_code=204)
async def delete_dependency(
    project_id: UUID,
    dependency_id: UUID,
    principal: CanManageTasks,
    _: ActiveProjects,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    deleted_dependency_id = await database.scalar(
        delete(ProjectTaskDependency)
        .where(
            ProjectTaskDependency.id == dependency_id,
            ProjectTaskDependency.project_id == project_id,
            ProjectTaskDependency.company_id == context.company_id,
        )
        .returning(ProjectTaskDependency.id)
    )
    if deleted_dependency_id is None:
        raise HTTPException(status_code=404, detail="Dependência não encontrada.")
    await database.commit()
    return Response(status_code=204)
