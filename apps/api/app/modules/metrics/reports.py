from __future__ import annotations

import csv
from io import BytesIO, StringIO

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.modules.metrics.schemas import DashboardResponse

TOTAL_LABELS = {
    "automation_executions": "Automacoes executadas",
    "automation_success": "Automacoes com sucesso",
    "automation_failure": "Automacoes com falha",
    "time_saved_minutes": "Tempo economizado (min)",
    "agent_uses": "Usos de agentes",
    "tokens": "Tokens de IA",
    "ai_cost_usd": "Custo de IA (USD)",
    "integration_failures": "Falhas de integracao",
    "active_users": "Usuarios ativos",
    "documents_processed": "Documentos processados",
    "pending_approvals": "Aprovacoes pendentes",
}


def csv_report(data: DashboardResponse) -> bytes:
    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Relatorio Orkestral", f"{data.period.start} a {data.period.end}"])
    writer.writerow([])
    writer.writerow(["Metrica", "Valor"])
    totals = data.totals.model_dump()
    for key, label in TOTAL_LABELS.items():
        writer.writerow([label, totals[key]])
    writer.writerow([])
    writer.writerow(["Data", *TOTAL_LABELS.values()])
    for point in data.series:
        values = point.model_dump()
        writer.writerow([point.date.isoformat(), *[values[key] for key in TOTAL_LABELS]])
    return output.getvalue().encode("utf-8-sig")


def xlsx_report(data: DashboardResponse) -> bytes:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Resumo"
    summary.append(["Relatorio Orkestral", f"{data.period.start} a {data.period.end}"])
    summary.append([])
    summary.append(["Metrica", "Valor"])
    totals = data.totals.model_dump()
    for key, label in TOTAL_LABELS.items():
        summary.append([label, totals[key]])
    agents = workbook.create_sheet("Agentes")
    agents.append(["Agente", "Usos", "Tokens", "Custo USD"])
    for agent in data.top_agents:
        agents.append([agent.name, agent.uses, agent.tokens, agent.cost_usd])
    daily = workbook.create_sheet("Serie diaria")
    daily.append(["Data", *TOTAL_LABELS.values()])
    for point in data.series:
        values = point.model_dump()
        daily.append([point.date.isoformat(), *[values[key] for key in TOTAL_LABELS]])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def pdf_report(data: DashboardResponse) -> bytes:
    buffer = BytesIO()
    document = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    document.setTitle("Relatorio Orkestral")
    document.setFont("Helvetica-Bold", 18)
    document.drawString(42, height - 54, "Relatorio executivo Orkestral")
    document.setFont("Helvetica", 10)
    document.drawString(42, height - 72, f"Periodo: {data.period.start} a {data.period.end}")
    y = height - 108
    totals = data.totals.model_dump()
    for key, label in TOTAL_LABELS.items():
        document.setFont("Helvetica", 10)
        document.drawString(48, y, label)
        document.setFont("Helvetica-Bold", 10)
        document.drawRightString(width - 48, y, str(totals[key]))
        y -= 22
    if data.top_agents:
        y -= 12
        document.setFont("Helvetica-Bold", 13)
        document.drawString(42, y, "Agentes mais utilizados")
        y -= 22
        for agent in data.top_agents[:8]:
            document.setFont("Helvetica", 9)
            document.drawString(48, y, agent.name[:55])
            document.drawRightString(width - 48, y, f"{agent.uses} usos | {agent.tokens} tokens")
            y -= 18
    document.setFont("Helvetica-Oblique", 8)
    document.drawString(
        42, 32, "Gerado pela Orkestral a partir de resumos diarios isolados por empresa."
    )
    document.save()
    return buffer.getvalue()
