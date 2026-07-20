import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CalendarClock,
  Check,
  Clock3,
  Plus,
  UserRoundCheck,
  UsersRound,
  X,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";
import "./hr.css";

type Department = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  active: boolean;
};
type Employee = {
  id: string;
  employee_code: string;
  name: string;
  work_email: string;
  phone: string | null;
  position: string;
  department_id: string | null;
  status: "active" | "on_leave" | "terminated";
  hire_date: string;
};
type Leave = {
  id: string;
  employee_id: string;
  employee_name: string;
  leave_type: "vacation" | "sick" | "personal" | "other";
  status: "pending" | "approved" | "rejected" | "cancelled";
  start_date: string;
  end_date: string;
  day_count: number;
  reason: string | null;
};
type Summary = {
  employees_active: number;
  employees_on_leave: number;
  pending_requests: number;
  departments_active: number;
};
const leaveLabels = {
  vacation: "Férias",
  sick: "Afastamento médico",
  personal: "Licença pessoal",
  other: "Outro",
};
function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}
function shortDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
    new Date(`${value}T12:00:00Z`),
  );
}

export function HRPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"employees" | "leave" | "departments">(
    "employees",
  );
  const [showEmployee, setShowEmployee] = useState(false);
  const [showLeave, setShowLeave] = useState(false);
  const [showDepartment, setShowDepartment] = useState(false);
  const [employeeCode, setEmployeeCode] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [position, setPosition] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [hireDate, setHireDate] = useState("");
  const [leaveEmployee, setLeaveEmployee] = useState("");
  const [leaveType, setLeaveType] = useState<Leave["leave_type"]>("vacation");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [departmentCode, setDepartmentCode] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canEmployees = me?.permissions.includes("hr.employees.manage") ?? false;
  const canLeave = me?.permissions.includes("hr.leave.create") ?? false;
  const canDecide = me?.permissions.includes("hr.leave.decide") ?? false;
  const canDepartments =
    me?.permissions.includes("hr.departments.manage") ?? false;
  const summary = useQuery({
    queryKey: ["hr", "summary"],
    queryFn: () => request<Summary>("/hr/summary"),
  });
  const employees = useQuery({
    queryKey: ["hr", "employees"],
    queryFn: () => request<Employee[]>("/hr/employees"),
  });
  const departments = useQuery({
    queryKey: ["hr", "departments"],
    queryFn: () => request<Department[]>("/hr/departments"),
  });
  const leave = useQuery({
    queryKey: ["hr", "leave"],
    queryFn: () => request<Leave[]>("/hr/leave-requests"),
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["hr", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["hr", "employees"] }),
      queryClient.invalidateQueries({ queryKey: ["hr", "leave"] }),
    ]);
  };
  const createEmployee = useMutation({
    mutationFn: () =>
      request<Employee>("/hr/employees", {
        method: "POST",
        body: {
          employee_code: employeeCode,
          name,
          work_email: email,
          position,
          department_id: departmentId || null,
          hire_date: hireDate,
        },
      }),
    onSuccess: async () => {
      setEmployeeCode("");
      setName("");
      setEmail("");
      setPosition("");
      setDepartmentId("");
      setHireDate("");
      setShowEmployee(false);
      setFeedback("Colaborador cadastrado.");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(
        errorMessage(caught, "Não foi possível cadastrar o colaborador."),
      ),
  });
  const createLeave = useMutation({
    mutationFn: () =>
      request<Leave>("/hr/leave-requests", {
        method: "POST",
        body: {
          employee_id: leaveEmployee,
          leave_type: leaveType,
          start_date: startDate,
          end_date: endDate,
          reason: reason || null,
        },
      }),
    onSuccess: async () => {
      setLeaveEmployee("");
      setStartDate("");
      setEndDate("");
      setReason("");
      setShowLeave(false);
      setFeedback("Solicitação enviada para aprovação.");
      setError(null);
      await refresh();
    },
    onError: (caught) =>
      setError(
        errorMessage(caught, "Não foi possível solicitar o afastamento."),
      ),
  });
  const decideLeave = useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: string;
      decision: "approved" | "rejected";
    }) =>
      request<Leave>(`/hr/leave-requests/${id}/decision`, {
        method: "POST",
        body: { decision },
      }),
    onSuccess: async (_, values) => {
      setFeedback(
        values.decision === "approved"
          ? "Afastamento aprovado."
          : "Afastamento rejeitado.",
      );
      await refresh();
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível registrar a decisão.")),
  });
  const createDepartment = useMutation({
    mutationFn: () =>
      request<Department>("/hr/departments", {
        method: "POST",
        body: { code: departmentCode, name: departmentName },
      }),
    onSuccess: async () => {
      setDepartmentCode("");
      setDepartmentName("");
      setShowDepartment(false);
      setFeedback("Departamento criado.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["hr", "departments"] }),
        queryClient.invalidateQueries({ queryKey: ["hr", "summary"] }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Não foi possível criar o departamento.")),
  });
  return (
    <div className="hr-page">
      <section className="hr-hero">
        <div>
          <span className="eyebrow eyebrow--light">Gestão de pessoas</span>
          <h1>Uma visão humana, organizada e responsável.</h1>
          <p>
            Centralize colaboradores, equipes e afastamentos com decisões claras
            e rastreáveis.
          </p>
        </div>
        <UsersRound size={62} />
      </section>
      {feedback ? <Alert variant="success">{feedback}</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <section className="hr-metrics">
        <Card>
          <UserRoundCheck size={21} />
          <strong>{summary.data?.employees_active ?? 0}</strong>
          <span>colaboradores ativos</span>
        </Card>
        <Card>
          <CalendarClock size={21} />
          <strong>{summary.data?.employees_on_leave ?? 0}</strong>
          <span>afastados hoje</span>
        </Card>
        <Card className={summary.data?.pending_requests ? "attention" : ""}>
          <Clock3 size={21} />
          <strong>{summary.data?.pending_requests ?? 0}</strong>
          <span>solicitações pendentes</span>
        </Card>
        <Card>
          <Building2 size={21} />
          <strong>{summary.data?.departments_active ?? 0}</strong>
          <span>departamentos</span>
        </Card>
      </section>
      <div className="hr-tabs">
        <button
          className={tab === "employees" ? "active" : ""}
          onClick={() => setTab("employees")}
          type="button"
        >
          Colaboradores
        </button>
        <button
          className={tab === "leave" ? "active" : ""}
          onClick={() => setTab("leave")}
          type="button"
        >
          Férias e afastamentos
        </button>
        <button
          className={tab === "departments" ? "active" : ""}
          onClick={() => setTab("departments")}
          type="button"
        >
          Departamentos
        </button>
      </div>
      {tab === "employees" ? (
        <>
          <div className="hr-heading">
            <div>
              <span className="eyebrow">Equipe</span>
              <h2>Colaboradores</h2>
            </div>
            {canEmployees ? (
              <Button onClick={() => setShowEmployee((value) => !value)}>
                <Plus size={16} /> Novo colaborador
              </Button>
            ) : null}
          </div>
          {showEmployee ? (
            <Card className="hr-form">
              <label>
                Matrícula
                <input
                  value={employeeCode}
                  onChange={(event) => setEmployeeCode(event.target.value)}
                />
              </label>
              <label>
                Nome
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label>
                E-mail profissional
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label>
                Cargo
                <input
                  value={position}
                  onChange={(event) => setPosition(event.target.value)}
                />
              </label>
              <label>
                Departamento
                <select
                  value={departmentId}
                  onChange={(event) => setDepartmentId(event.target.value)}
                >
                  <option value="">Sem departamento</option>
                  {departments.data
                    ?.filter((department) => department.active)
                    .map((department) => (
                      <option key={department.id} value={department.id}>
                        {department.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Admissão
                <input
                  type="date"
                  value={hireDate}
                  onChange={(event) => setHireDate(event.target.value)}
                />
              </label>
              <Button
                disabled={
                  !employeeCode ||
                  name.trim().length < 2 ||
                  !email ||
                  position.trim().length < 2 ||
                  !hireDate
                }
                loading={createEmployee.isPending}
                onClick={() => createEmployee.mutate()}
              >
                Cadastrar
              </Button>
            </Card>
          ) : null}
          <section className="employee-grid">
            {employees.data?.map((employee) => (
              <Card className={employee.status} key={employee.id}>
                <div className="employee-avatar">
                  {employee.name.slice(0, 1).toUpperCase()}
                </div>
                <span>{employee.employee_code}</span>
                <h3>{employee.name}</h3>
                <p>{employee.position}</p>
                <small>
                  {departments.data?.find(
                    (department) => department.id === employee.department_id,
                  )?.name ?? "Sem departamento"}
                </small>
                <i>
                  {employee.status === "active"
                    ? "Ativo"
                    : employee.status === "on_leave"
                      ? "Afastado"
                      : "Desligado"}
                </i>
              </Card>
            ))}
          </section>
        </>
      ) : null}
      {tab === "leave" ? (
        <>
          <div className="hr-heading">
            <div>
              <span className="eyebrow">Calendário humano</span>
              <h2>Férias e afastamentos</h2>
            </div>
            {canLeave ? (
              <Button onClick={() => setShowLeave((value) => !value)}>
                <Plus size={16} /> Nova solicitação
              </Button>
            ) : null}
          </div>
          {showLeave ? (
            <Card className="leave-form">
              <select
                value={leaveEmployee}
                onChange={(event) => setLeaveEmployee(event.target.value)}
              >
                <option value="">Colaborador</option>
                {employees.data
                  ?.filter((employee) => employee.status !== "terminated")
                  .map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.name}
                    </option>
                  ))}
              </select>
              <select
                value={leaveType}
                onChange={(event) =>
                  setLeaveType(event.target.value as typeof leaveType)
                }
              >
                {Object.entries(leaveLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
              <input
                placeholder="Motivo ou observação"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <Button
                disabled={!leaveEmployee || !startDate || !endDate}
                loading={createLeave.isPending}
                onClick={() => createLeave.mutate()}
              >
                Solicitar
              </Button>
            </Card>
          ) : null}
          <Card className="leave-list">
            {leave.data?.length ? (
              leave.data.map((item) => (
                <article className={item.status} key={item.id}>
                  <CalendarClock size={20} />
                  <span>
                    <strong>{item.employee_name}</strong>
                    <small>
                      {leaveLabels[item.leave_type]} ·{" "}
                      {shortDate(item.start_date)} a {shortDate(item.end_date)}{" "}
                      · {item.day_count} dias
                    </small>
                  </span>
                  <i>
                    {item.status === "pending"
                      ? "Pendente"
                      : item.status === "approved"
                        ? "Aprovado"
                        : item.status === "rejected"
                          ? "Rejeitado"
                          : "Cancelado"}
                  </i>
                  {canDecide && item.status === "pending" ? (
                    <div>
                      <button
                        aria-label="Aprovar"
                        onClick={() =>
                          decideLeave.mutate({
                            id: item.id,
                            decision: "approved",
                          })
                        }
                        type="button"
                      >
                        <Check size={17} />
                      </button>
                      <button
                        aria-label="Rejeitar"
                        onClick={() =>
                          decideLeave.mutate({
                            id: item.id,
                            decision: "rejected",
                          })
                        }
                        type="button"
                      >
                        <X size={17} />
                      </button>
                    </div>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="hr-empty">Nenhuma solicitação registrada.</p>
            )}
          </Card>
        </>
      ) : null}
      {tab === "departments" ? (
        <>
          <div className="hr-heading">
            <div>
              <span className="eyebrow">Estrutura organizacional</span>
              <h2>Departamentos</h2>
            </div>
            {canDepartments ? (
              <Button onClick={() => setShowDepartment((value) => !value)}>
                <Plus size={16} /> Novo departamento
              </Button>
            ) : null}
          </div>
          {showDepartment ? (
            <Card className="department-form">
              <input
                placeholder="Código"
                value={departmentCode}
                onChange={(event) => setDepartmentCode(event.target.value)}
              />
              <input
                placeholder="Nome"
                value={departmentName}
                onChange={(event) => setDepartmentName(event.target.value)}
              />
              <Button
                disabled={!departmentCode || departmentName.trim().length < 2}
                loading={createDepartment.isPending}
                onClick={() => createDepartment.mutate()}
              >
                Criar
              </Button>
            </Card>
          ) : null}
          <section className="department-grid">
            {departments.data?.map((department) => (
              <Card key={department.id}>
                <Building2 size={22} />
                <span>{department.code}</span>
                <h3>{department.name}</h3>
                <p>
                  {employees.data?.filter(
                    (employee) =>
                      employee.department_id === department.id &&
                      employee.status !== "terminated",
                  ).length ?? 0}{" "}
                  colaboradores
                </p>
              </Card>
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
