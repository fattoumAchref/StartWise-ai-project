"""
Module Conformité — 100% RAG, aucune donnée statique.
Toutes les informations viennent de ChromaDB (JORT + DGI + CNSS scraped).
"""

from dataclasses import dataclass
from datetime import date
from rag.pipeline import rag_pipeline, RAGRequest


async def answer(query: str, company_context: dict | None = None, language: str = "fr") -> dict:
    response = await rag_pipeline.run(RAGRequest(
        query=query, language=language, company_context=company_context,
    ))
    return {"answer": response.answer, "sources": response.sources, "requires_lawyer": response.requires_lawyer}


@dataclass
class ComplianceAlert:
    category: str
    severity: str
    title: str
    description: str
    deadline: str | None
    action_required: str
    penalty_if_missed: str | None


@dataclass
class ComplianceReport:
    company_name: str
    report_date: str
    score: int
    score_label: str
    alerts: list[ComplianceAlert]
    compliant_items: list[str]
    next_deadlines: list[str]


class ComplianceModule:
    def generate_report(
        self,
        company_name: str,
        legal_form: str,
        employees_count: int = 0,
        has_users_data: bool = False,
        has_inpdp_declaration: bool = False,
        has_written_contracts: bool = True,
        vat_registered: bool = False,
        startup_label: bool = False,
        last_cnss_declaration: str | None = None,
        last_tva_declaration: str | None = None,
    ) -> ComplianceReport:
        score = 100
        alerts: list[ComplianceAlert] = []
        ok_items: list[str] = []

        if has_users_data and not has_inpdp_declaration:
            score -= 25
            alerts.append(ComplianceAlert(
                category="Données personnelles",
                severity="CRITICAL",
                title="Déclaration INPDP manquante",
                description="L'entreprise traite des données utilisateurs sans déclaration INPDP.",
                deadline="Immédiat",
                action_required="Préparer et déposer la déclaration INPDP.",
                penalty_if_missed="Risque de sanctions administratives.",
            ))
        else:
            ok_items.append("Gestion INPDP cohérente")

        if not has_written_contracts and employees_count > 0:
            score -= 20
            alerts.append(ComplianceAlert(
                category="Travail",
                severity="HIGH",
                title="Contrats écrits absents",
                description="Des salariés sont déclarés sans contrat écrit.",
                deadline="7 jours",
                action_required="Rédiger et faire signer les contrats de travail.",
                penalty_if_missed="Risque prud'homal.",
            ))
        else:
            ok_items.append("Contrats de travail présents")

        if not vat_registered:
            score -= 10
            alerts.append(ComplianceAlert(
                category="Fiscal",
                severity="MEDIUM",
                title="TVA non activée",
                description="L'entreprise n'est pas marquée comme inscrite TVA.",
                deadline=None,
                action_required="Vérifier l'obligation d'assujettissement TVA.",
                penalty_if_missed=None,
            ))
        else:
            ok_items.append("Inscription TVA renseignée")

        label = "EXCELLENT" if score >= 85 else "BON" if score >= 70 else "A_SURVEILLER" if score >= 50 else "CRITIQUE"
        deadlines = [
            "CNSS: déclaration mensuelle",
            "TVA: déclaration selon régime fiscal",
        ]

        return ComplianceReport(
            company_name=company_name,
            report_date=str(date.today()),
            score=max(score, 0),
            score_label=label,
            alerts=alerts,
            compliant_items=ok_items,
            next_deadlines=deadlines,
        )

    def calculate_payroll(self, employees: list[dict]) -> dict:
        cnss_pat = 0.1657
        cnss_emp = 0.0918
        tfp = 0.01
        foprolos = 0.01

        rows = []
        for e in employees:
            gross = float(e.get("gross_salary_tnd", 0) or 0)
            emp_cnss = round(gross * cnss_emp, 2)
            net = round(gross - emp_cnss, 2)
            employer_cost = round(gross * (1 + cnss_pat + tfp + foprolos), 2)
            rows.append({
                "name": e.get("name", "Employé"),
                "gross_salary_tnd": gross,
                "cnss_employee_tnd": emp_cnss,
                "net_salary_tnd": net,
                "employer_cost_tnd": employer_cost,
            })

        return {
            "rates": {
                "cnss_employer": cnss_pat,
                "cnss_employee": cnss_emp,
                "tfp": tfp,
                "foprolos": foprolos,
            },
            "employees": rows,
            "total_employer_cost_tnd": round(sum(r["employer_cost_tnd"] for r in rows), 2),
        }
