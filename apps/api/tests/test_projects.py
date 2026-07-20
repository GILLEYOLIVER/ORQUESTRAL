from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.projects.schemas import ProjectCreate, ProjectTaskCreate


def test_project_rejects_due_date_before_start_date() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name="Implantacao", start_date=date(2026, 8, 10), due_date=date(2026, 8, 9))


def test_project_and_task_defaults_are_safe() -> None:
    project = ProjectCreate(name="  Portal do cliente  ")
    task = ProjectTaskCreate(title="Preparar ambiente")
    assert project.name == "Portal do cliente"
    assert project.status == "planning"
    assert project.priority == "normal"
    assert task.status == "todo"
    assert task.position == 0
