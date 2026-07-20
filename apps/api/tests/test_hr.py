from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.hr.schemas import EmployeeCreate, LeaveRequestCreate


def test_leave_request_rejects_invalid_period() -> None:
    with pytest.raises(ValidationError):
        LeaveRequestCreate(
            employee_id="00000000-0000-0000-0000-000000000001",
            leave_type="vacation",
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 9),
        )


def test_employee_professional_data_is_valid() -> None:
    employee = EmployeeCreate(
        employee_code="COL-001",
        name="Maria Silva",
        work_email="maria@empresa.com.br",
        position="Analista",
        hire_date=date(2026, 8, 1),
    )
    assert employee.employee_code == "COL-001"
    assert employee.department_id is None
