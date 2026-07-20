from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.core.dependencies import DatabaseSession
from app.core.security import utc_now
from app.core.tenancy import Principal, get_request_context, require_permission
from app.modules.authorization.service import record_authorization_audit
from app.modules.hr.models import HRDepartment, HREmployee, HRLeaveRequest
from app.modules.hr.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    HRSummaryResponse,
    LeaveDecision,
    LeaveRequestCreate,
    LeaveRequestResponse,
)
from app.modules.modularity.dependencies import require_active_module

router = APIRouter(
    prefix="/hr",
    tags=["hr"],
    dependencies=[Depends(require_active_module("hr"))],
)
CanViewHR = Annotated[Principal, Depends(require_permission("hr.view"))]
CanManageEmployees = Annotated[Principal, Depends(require_permission("hr.employees.manage"))]
CanManageDepartments = Annotated[Principal, Depends(require_permission("hr.departments.manage"))]
CanCreateLeave = Annotated[Principal, Depends(require_permission("hr.leave.create"))]
CanDecideLeave = Annotated[Principal, Depends(require_permission("hr.leave.decide"))]


async def _employee(
    database: DatabaseSession, *, employee_id: UUID, company_id: UUID
) -> HREmployee:
    employee = await database.scalar(
        select(HREmployee).where(
            HREmployee.id == employee_id,
            HREmployee.company_id == company_id,
        )
    )
    if employee is None:
        raise HTTPException(status_code=404, detail="Colaborador nao encontrado nesta empresa.")
    return employee


async def _validate_employee_links(
    database: DatabaseSession,
    *,
    company_id: UUID,
    department_id: UUID | None,
    manager_employee_id: UUID | None,
    current_employee_id: UUID | None = None,
) -> None:
    if department_id is not None:
        department = await database.scalar(
            select(HRDepartment.id).where(
                HRDepartment.id == department_id,
                HRDepartment.company_id == company_id,
                HRDepartment.active.is_(True),
            )
        )
        if department is None:
            raise HTTPException(status_code=404, detail="Departamento ativo nao encontrado.")
    if manager_employee_id is not None:
        if manager_employee_id == current_employee_id:
            raise HTTPException(
                status_code=409, detail="O colaborador nao pode ser gestor de si mesmo."
            )
        manager = await database.scalar(
            select(HREmployee.id).where(
                HREmployee.id == manager_employee_id,
                HREmployee.company_id == company_id,
                HREmployee.status != "terminated",
            )
        )
        if manager is None:
            raise HTTPException(status_code=404, detail="Gestor ativo nao encontrado.")


async def _leave_response(database: DatabaseSession, leave: HRLeaveRequest) -> LeaveRequestResponse:
    employee = await database.scalar(
        select(HREmployee).where(
            HREmployee.id == leave.employee_id,
            HREmployee.company_id == leave.company_id,
        )
    )
    if employee is None:
        raise HTTPException(status_code=500, detail="Colaborador do afastamento nao encontrado.")
    return LeaveRequestResponse.model_validate(
        {
            "id": leave.id,
            "employee_id": leave.employee_id,
            "employee_name": employee.name,
            "leave_type": leave.leave_type,
            "status": leave.status,
            "start_date": leave.start_date,
            "end_date": leave.end_date,
            "day_count": (leave.end_date - leave.start_date).days + 1,
            "reason": leave.reason,
            "decision_note": leave.decision_note,
            "decided_at": leave.decided_at,
            "created_at": leave.created_at,
            "updated_at": leave.updated_at,
        }
    )


@router.get("/summary", response_model=HRSummaryResponse)
async def hr_summary(principal: CanViewHR, database: DatabaseSession) -> HRSummaryResponse:
    context = get_request_context(principal)
    today = date.today()
    employees_active = int(
        await database.scalar(
            select(func.count(HREmployee.id)).where(
                HREmployee.company_id == context.company_id,
                HREmployee.status != "terminated",
            )
        )
        or 0
    )
    employees_on_leave = int(
        await database.scalar(
            select(func.count(func.distinct(HRLeaveRequest.employee_id))).where(
                HRLeaveRequest.company_id == context.company_id,
                HRLeaveRequest.status == "approved",
                HRLeaveRequest.start_date <= today,
                HRLeaveRequest.end_date >= today,
            )
        )
        or 0
    )
    pending_requests = int(
        await database.scalar(
            select(func.count(HRLeaveRequest.id)).where(
                HRLeaveRequest.company_id == context.company_id,
                HRLeaveRequest.status == "pending",
            )
        )
        or 0
    )
    departments_active = int(
        await database.scalar(
            select(func.count(HRDepartment.id)).where(
                HRDepartment.company_id == context.company_id,
                HRDepartment.active.is_(True),
            )
        )
        or 0
    )
    return HRSummaryResponse(
        employees_active=employees_active,
        employees_on_leave=employees_on_leave,
        pending_requests=pending_requests,
        departments_active=departments_active,
    )


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    principal: CanViewHR, database: DatabaseSession
) -> list[DepartmentResponse]:
    context = get_request_context(principal)
    rows = list(
        await database.scalars(
            select(HRDepartment)
            .where(HRDepartment.company_id == context.company_id)
            .order_by(HRDepartment.active.desc(), HRDepartment.name)
        )
    )
    return [DepartmentResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate, principal: CanManageDepartments, database: DatabaseSession
) -> DepartmentResponse:
    context = get_request_context(principal)
    department = HRDepartment(
        company_id=context.company_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
    )
    database.add(department)
    await database.commit()
    await database.refresh(department)
    return DepartmentResponse.model_validate(department, from_attributes=True)


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    principal: CanManageDepartments,
    database: DatabaseSession,
) -> DepartmentResponse:
    context = get_request_context(principal)
    department = await database.scalar(
        select(HRDepartment).where(
            HRDepartment.id == department_id,
            HRDepartment.company_id == context.company_id,
        )
    )
    if department is None:
        raise HTTPException(status_code=404, detail="Departamento nao encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "code" and value:
            value = value.strip().upper()
        if field == "name" and value:
            value = value.strip()
        setattr(department, field, value)
    department.updated_at = utc_now()
    await database.commit()
    await database.refresh(department)
    return DepartmentResponse.model_validate(department, from_attributes=True)


@router.get("/employees", response_model=list[EmployeeResponse])
async def list_employees(
    principal: CanViewHR,
    database: DatabaseSession,
    employee_status: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=120),
) -> list[EmployeeResponse]:
    context = get_request_context(principal)
    statement = select(HREmployee).where(HREmployee.company_id == context.company_id)
    if employee_status:
        statement = statement.where(HREmployee.status == employee_status)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(HREmployee.name.ilike(pattern), HREmployee.employee_code.ilike(pattern))
        )
    rows = list(await database.scalars(statement.order_by(HREmployee.name).limit(500)))
    return [EmployeeResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate, principal: CanManageEmployees, database: DatabaseSession
) -> EmployeeResponse:
    context = get_request_context(principal)
    await _validate_employee_links(
        database,
        company_id=context.company_id,
        department_id=payload.department_id,
        manager_employee_id=payload.manager_employee_id,
    )
    employee = HREmployee(
        company_id=context.company_id,
        created_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    employee.employee_code = employee.employee_code.strip().upper()
    employee.name = employee.name.strip()
    employee.work_email = employee.work_email.strip().lower()
    database.add(employee)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="hr.employee.created",
        target_type="hr_employee",
        target_id=employee.id,
        details={"employee_code": employee.employee_code, "position": employee.position},
    )
    await database.commit()
    await database.refresh(employee)
    return EmployeeResponse.model_validate(employee, from_attributes=True)


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdate,
    principal: CanManageEmployees,
    database: DatabaseSession,
) -> EmployeeResponse:
    context = get_request_context(principal)
    employee = await _employee(database, employee_id=employee_id, company_id=context.company_id)
    await _validate_employee_links(
        database,
        company_id=context.company_id,
        department_id=payload.department_id
        if "department_id" in payload.model_fields_set
        else employee.department_id,
        manager_employee_id=payload.manager_employee_id
        if "manager_employee_id" in payload.model_fields_set
        else employee.manager_employee_id,
        current_employee_id=employee.id,
    )
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") == "terminated" and changes.get("termination_date") is None:
        changes["termination_date"] = date.today()
    if changes.get("status") not in (None, "terminated"):
        changes["termination_date"] = None
    for field, value in changes.items():
        if field == "work_email" and value:
            value = value.strip().lower()
        if field in {"name", "position"} and value:
            value = value.strip()
        setattr(employee, field, value)
    employee.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="hr.employee.updated",
        target_type="hr_employee",
        target_id=employee.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    await database.commit()
    await database.refresh(employee)
    return EmployeeResponse.model_validate(employee, from_attributes=True)


@router.get("/leave-requests", response_model=list[LeaveRequestResponse])
async def list_leave_requests(
    principal: CanViewHR,
    database: DatabaseSession,
    leave_status: str | None = Query(default=None, alias="status"),
) -> list[LeaveRequestResponse]:
    context = get_request_context(principal)
    statement = select(HRLeaveRequest).where(HRLeaveRequest.company_id == context.company_id)
    if leave_status:
        statement = statement.where(HRLeaveRequest.status == leave_status)
    rows = list(
        await database.scalars(statement.order_by(HRLeaveRequest.created_at.desc()).limit(500))
    )
    return [await _leave_response(database, row) for row in rows]


@router.post(
    "/leave-requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    payload: LeaveRequestCreate, principal: CanCreateLeave, database: DatabaseSession
) -> LeaveRequestResponse:
    context = get_request_context(principal)
    employee = await _employee(
        database, employee_id=payload.employee_id, company_id=context.company_id
    )
    if employee.status == "terminated":
        raise HTTPException(status_code=409, detail="Colaborador desligado nao pode ser afastado.")
    overlap = await database.scalar(
        select(HRLeaveRequest.id).where(
            HRLeaveRequest.company_id == context.company_id,
            HRLeaveRequest.employee_id == payload.employee_id,
            HRLeaveRequest.status.in_(("pending", "approved")),
            HRLeaveRequest.start_date <= payload.end_date,
            HRLeaveRequest.end_date >= payload.start_date,
        )
    )
    if overlap is not None:
        raise HTTPException(status_code=409, detail="Ja existe uma solicitacao neste periodo.")
    leave = HRLeaveRequest(
        company_id=context.company_id,
        requested_by_user_id=context.user_id,
        **payload.model_dump(),
    )
    database.add(leave)
    await database.flush()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action="hr.leave.requested",
        target_type="hr_leave_request",
        target_id=leave.id,
        details={"employee_id": str(employee.id), "leave_type": leave.leave_type},
    )
    await database.commit()
    await database.refresh(leave)
    return await _leave_response(database, leave)


@router.post("/leave-requests/{leave_id}/decision", response_model=LeaveRequestResponse)
async def decide_leave_request(
    leave_id: UUID,
    payload: LeaveDecision,
    principal: CanDecideLeave,
    database: DatabaseSession,
) -> LeaveRequestResponse:
    context = get_request_context(principal)
    leave = await database.scalar(
        select(HRLeaveRequest).where(
            HRLeaveRequest.id == leave_id,
            HRLeaveRequest.company_id == context.company_id,
        )
    )
    if leave is None:
        raise HTTPException(status_code=404, detail="Solicitacao de afastamento nao encontrada.")
    if leave.status != "pending":
        raise HTTPException(status_code=409, detail="A solicitacao ja foi decidida.")
    leave.status = payload.decision
    leave.decision_note = payload.note
    leave.decided_by_user_id = context.user_id
    leave.decided_at = utc_now()
    leave.updated_at = utc_now()
    record_authorization_audit(
        database,
        company_id=context.company_id,
        actor_user_id=context.user_id,
        action=f"hr.leave.{payload.decision}",
        target_type="hr_leave_request",
        target_id=leave.id,
        details={"employee_id": str(leave.employee_id)},
    )
    await database.commit()
    await database.refresh(leave)
    return await _leave_response(database, leave)
