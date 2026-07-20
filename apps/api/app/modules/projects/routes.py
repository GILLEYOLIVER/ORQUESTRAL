from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.modularity.dependencies import require_active_module
from app.modules.projects.models import Project, ProjectTask
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectTaskCreate,
    ProjectTaskResponse,
    ProjectTaskUpdate,
    ProjectUpdate,
)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(require_active_module("projects"))],
)
CanViewProjects = Annotated[Principal, Depends(require_permission("projects.view"))]
CanCreateProjects = Annotated[Principal, Depends(require_permission("projects.create"))]
CanUpdateProjects = Annotated[Principal, Depends(require_permission("projects.update"))]
CanDeleteProjects = Annotated[Principal, Depends(require_permission("projects.delete"))]
CanManageTasks = Annotated[Principal, Depends(require_permission("projects.tasks.manage"))]


async def _project(database: DatabaseSession, *, project_id: UUID, company_id: UUID) -> Project:
    project = await database.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company_id,
            Project.archived_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Projeto nao encontrado nesta empresa.")
    return project


async def _task(
    database: DatabaseSession, *, task_id: UUID, project_id: UUID, company_id: UUID
) -> ProjectTask:
    task = await database.scalar(
        select(ProjectTask).where(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id,
            ProjectTask.company_id == company_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa nao encontrada neste projeto.")
    return task


async def _project_response(database: DatabaseSession, project: Project) -> ProjectResponse:
    total, done = (
        await database.execute(
            select(
                func.count(ProjectTask.id),
                func.count(ProjectTask.id).filter(ProjectTask.status == "done"),
            ).where(
                ProjectTask.project_id == project.id,
                ProjectTask.company_id == project.company_id,
                ProjectTask.status != "cancelled",
            )
        )
    ).one()
    task_total = int(total or 0)
    task_done = int(done or 0)
    return ProjectResponse.model_validate(
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "priority": project.priority,
            "start_date": project.start_date,
            "due_date": project.due_date,
            "completed_at": project.completed_at,
            "task_total": task_total,
            "task_done": task_done,
            "progress_percent": round((task_done / task_total) * 100) if task_total else 0,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }
    )


def _task_response(task: ProjectTask) -> ProjectTaskResponse:
    return ProjectTaskResponse.model_validate(task, from_attributes=True)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    principal: CanViewProjects,
    database: DatabaseSession,
    project_status: str | None = Query(default=None, alias="status"),
) -> list[ProjectResponse]:
    context = get_request_context(principal)
    statement = select(Project).where(
        Project.company_id == context.company_id,
        Project.archived_at.is_(None),
    )
    if project_status:
        statement = statement.where(Project.status == project_status)
    rows = list(await database.scalars(statement.order_by(Project.updated_at.desc()).limit(200)))
    return [await _project_response(database, row) for row in rows]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, principal: CanCreateProjects, database: DatabaseSession
) -> ProjectResponse:
    context = get_request_context(principal)
    project = Project(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    if project.status == "completed":
        project.completed_at = utc_now()
    database.add(project)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="project.created",
        target_type="project",
        target_id=project.id,
        details={"name": project.name, "status": project.status},
    )
    await database.commit()
    await database.refresh(project)
    return await _project_response(database, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID, principal: CanViewProjects, database: DatabaseSession
) -> ProjectResponse:
    context = get_request_context(principal)
    return await _project_response(
        database,
        await _project(database, project_id=project_id, company_id=context.company_id),
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    principal: CanUpdateProjects,
    database: DatabaseSession,
) -> ProjectResponse:
    context = get_request_context(principal)
    project = await _project(database, project_id=project_id, company_id=context.company_id)
    changes = payload.model_dump(exclude_unset=True)
    start_date = changes.get("start_date", project.start_date)
    due_date = changes.get("due_date", project.due_date)
    if start_date and due_date and due_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A data final deve ser igual ou posterior a data inicial.",
        )
    for field, value in changes.items():
        setattr(project, field, value)
    if payload.status == "completed" and project.completed_at is None:
        project.completed_at = utc_now()
    elif payload.status is not None and payload.status != "completed":
        project.completed_at = None
    project.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="project.updated",
        target_type="project",
        target_id=project.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(project)
    return await _project_response(database, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_project(
    project_id: UUID, principal: CanDeleteProjects, database: DatabaseSession
) -> Response:
    context = get_request_context(principal)
    project = await _project(database, project_id=project_id, company_id=context.company_id)
    project.archived_at = utc_now()
    project.status = "cancelled"
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="project.archived",
        target_type="project",
        target_id=project.id,
        details={"name": project.name},
    )
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/tasks", response_model=list[ProjectTaskResponse])
async def list_tasks(
    project_id: UUID, principal: CanViewProjects, database: DatabaseSession
) -> list[ProjectTaskResponse]:
    context = get_request_context(principal)
    await _project(database, project_id=project_id, company_id=context.company_id)
    rows = list(
        await database.scalars(
            select(ProjectTask)
            .where(
                ProjectTask.project_id == project_id,
                ProjectTask.company_id == context.company_id,
            )
            .order_by(ProjectTask.position, ProjectTask.created_at)
        )
    )
    return [_task_response(row) for row in rows]


@router.post(
    "/{project_id}/tasks",
    response_model=ProjectTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: UUID,
    payload: ProjectTaskCreate,
    principal: CanManageTasks,
    database: DatabaseSession,
) -> ProjectTaskResponse:
    context = get_request_context(principal)
    await _project(database, project_id=project_id, company_id=context.company_id)
    task = ProjectTask(
        company_id=context.company_id,
        project_id=project_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    if task.status == "done":
        task.completed_at = utc_now()
    database.add(task)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="project.task.created",
        target_type="project_task",
        target_id=task.id,
        details={"project_id": str(project_id), "title": task.title},
    )
    await database.commit()
    await database.refresh(task)
    return _task_response(task)


@router.patch("/{project_id}/tasks/{task_id}", response_model=ProjectTaskResponse)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    payload: ProjectTaskUpdate,
    principal: CanManageTasks,
    database: DatabaseSession,
) -> ProjectTaskResponse:
    context = get_request_context(principal)
    await _project(database, project_id=project_id, company_id=context.company_id)
    task = await _task(
        database, task_id=task_id, project_id=project_id, company_id=context.company_id
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if payload.status == "done" and task.completed_at is None:
        task.completed_at = utc_now()
    elif payload.status is not None and payload.status != "done":
        task.completed_at = None
    task.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="project.task.updated",
        target_type="project_task",
        target_id=task.id,
        details={"project_id": str(project_id), "fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(task)
    return _task_response(task)


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    principal: CanManageTasks,
    database: DatabaseSession,
) -> Response:
    context = get_request_context(principal)
    await _project(database, project_id=project_id, company_id=context.company_id)
    task = await _task(
        database, task_id=task_id, project_id=project_id, company_id=context.company_id
    )
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="project.task.deleted",
        target_type="project_task",
        target_id=task.id,
        details={"project_id": str(project_id), "title": task.title},
    )
    await database.delete(task)
    await database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
