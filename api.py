"""
API FastAPI — routes de l'agent légal.
Auth JWT + toutes les fonctionnalités exposées via REST et WebSocket.
"""

from datetime import datetime, timedelta
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from config import cfg
from database import get_db
from rag.pipeline import rag_pipeline, RAGRequest
from modules.creation import recommend_legal_form, generate_statuts
from modules.ip_protection import IPProtectionModule
from modules.contracts import ContractModule
from modules.fundraising import FundraisingModule
from modules.compliance import ComplianceModule
from scrapers.dgi_cnss import get_all_data, calculate_employer_cost
from scrapers.spdx import check_saas_risk, check_stack_compatibility

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ip_module = IPProtectionModule()
contract_module = ContractModule()
fundraising_module = FundraisingModule()
compliance_module = ComplianceModule()


# ─────────────────────────────────────────────
# SCHÉMAS PYDANTIC
# ─────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""
    preferred_language: str = "fr"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ChatMessage(BaseModel):
    query: str
    language: str = "fr"
    company_context: dict | None = None
    session_id: str | None = None

class TrademarkCheckRequest(BaseModel):
    name: str
    nice_classes: list[int]

class LicenseAuditRequest(BaseModel):
    stack: list[str]
    business_model: str = "saas"

class ContractAnalyzeRequest(BaseModel):
    contract_text: str
    contract_type: str = "unknown"

class ContractGenerateRequest(BaseModel):
    contract_type: str
    variables: dict
    language: str = "fr"

class LegalFormRequest(BaseModel):
    nb_founders: int
    has_fundraising_plans: bool
    sector: str = ""
    capital_available_tnd: float = 1000

class DilutionRequest(BaseModel):
    pre_money_tnd: float
    investment_tnd: float
    cap_table: dict  # {founder_name: pct}

class ComplianceReportRequest(BaseModel):
    company_name: str
    legal_form: str
    employees_count: int = 0
    has_users_data: bool = False
    has_inpdp_declaration: bool = False
    has_written_contracts: bool = True
    vat_registered: bool = False
    startup_label: bool = False
    last_cnss_declaration: str | None = None
    last_tva_declaration: str | None = None

class PayrollRequest(BaseModel):
    employees: list[dict]  # [{name: str, gross_salary_tnd: float}]


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=cfg.jwt_expire_minutes)
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token invalide")
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")


@router.post("/auth/register", tags=["Auth"])
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    hashed = pwd_context.hash(body.password)
    # TODO : insérer en base avec SQLAlchemy
    return {"message": "Compte créé avec succès", "email": body.email}


@router.post("/auth/login", response_model=Token, tags=["Auth"])
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # TODO : vérifier en base
    # Pour la démo, on génère directement le token
    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id, "email": form.username})
    return Token(access_token=token)


# ─────────────────────────────────────────────
# CHAT — Question générale
# ─────────────────────────────────────────────

@router.post("/chat", tags=["Chat"])
async def chat(
    body: ChatMessage,
    current_user: dict = Depends(get_current_user),
):
    """Point d'entrée principal — toutes les questions juridiques."""
    response = await rag_pipeline.run(
        RAGRequest(
            query=body.query,
            language=body.language,
            company_context=body.company_context,
        )
    )
    return {
        "answer": response.answer,
        "sources": response.sources,
        "intent": response.intent,
        "requires_lawyer": response.requires_lawyer,
        "session_id": body.session_id or str(uuid.uuid4()),
    }


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Chat en temps réel via WebSocket."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")
            language = data.get("language", "fr")
            company_context = data.get("company_context")

            if not query:
                continue

            response = await rag_pipeline.run(
                RAGRequest(query=query, language=language, company_context=company_context)
            )
            await websocket.send_json({
                "answer": response.answer,
                "sources": response.sources,
                "requires_lawyer": response.requires_lawyer,
            })
    except WebSocketDisconnect:
        pass


# ─────────────────────────────────────────────
# MODULE 1 — CRÉATION D'ENTREPRISE
# ─────────────────────────────────────────────

@router.post("/creation/recommend-form", tags=["Création"])
async def recommend_form(body: LegalFormRequest, _: dict = Depends(get_current_user)):
    """Recommande la forme juridique optimale."""
    result = recommend_legal_form(
        nb_founders=body.nb_founders,
        has_fundraising_plans=body.has_fundraising_plans,
        sector=body.sector,
        capital_available_tnd=body.capital_available_tnd,
    )
    return result


@router.post("/creation/generate-statuts", tags=["Création"])
async def gen_statuts(
    form: str, variables: dict, language: str = "fr", _: dict = Depends(get_current_user)
):
    """Génère les statuts de la société."""
    content = await generate_statuts(form, variables, language)
    return {"statuts": content, "requires_lawyer": True}


# ─────────────────────────────────────────────
# MODULE 2 — PROTECTION IP
# ─────────────────────────────────────────────

@router.post("/ip/check-trademark", tags=["IP"])
async def check_trademark(body: TrademarkCheckRequest, _: dict = Depends(get_current_user)):
    """Vérifie la disponibilité d'un nom de marque (similarité phonétique + classes Nice)."""
    result = await ip_module.check_trademark(body.name, body.nice_classes)
    return {
        "candidate": result.candidate_name,
        "risk_level": result.risk_level,
        "can_register": result.can_register,
        "conflicts": result.conflicts,
        "phonetic_matches": result.phonetic_matches,
        "recommendation": result.recommendation,
        "legal_basis": result.legal_basis,
    }


@router.post("/ip/audit-licenses", tags=["IP"])
async def audit_licenses(body: LicenseAuditRequest, _: dict = Depends(get_current_user)):
    """Audite la stack logicielle (compatibilité SaaS, copyleft)."""
    result = await ip_module.audit_software_licenses(body.stack, body.business_model)
    return {
        "stack": result.stack,
        "overall_risk": result.overall_risk,
        "saas_compatible": result.saas_compatible,
        "conflicts": result.conflicts,
        "dangerous_licenses": result.dangerous_licenses,
        "recommendations": result.recommendations,
    }


# ─────────────────────────────────────────────
# MODULE 3 — CONTRATS
# ─────────────────────────────────────────────

@router.post("/contracts/analyze", tags=["Contrats"])
async def analyze_contract(body: ContractAnalyzeRequest, _: dict = Depends(get_current_user)):
    """Analyse un contrat reçu et détecte les clauses dangereuses."""
    result = await contract_module.analyze(body.contract_text, body.contract_type)
    return {
        "overall_risk": result.overall_risk,
        "dangerous_clauses": result.dangerous_clauses,
        "missing_mandatory_clauses": result.missing_mandatory_clauses,
        "recommendations": result.recommendations,
        "requires_lawyer": result.requires_lawyer,
    }


@router.post("/contracts/generate", tags=["Contrats"])
async def generate_contract(body: ContractGenerateRequest, _: dict = Depends(get_current_user)):
    """Génère un contrat conforme au droit tunisien."""
    result = await contract_module.generate(body.contract_type, body.variables, body.language)
    return {
        "contract_type": result.contract_type,
        "content": result.content,
        "requires_lawyer_validation": result.requires_lawyer_validation,
        "warnings": result.warnings,
    }


# ─────────────────────────────────────────────
# MODULE 4 — LEVÉE DE FONDS
# ─────────────────────────────────────────────

@router.post("/fundraising/dilution", tags=["Levée de fonds"])
async def calculate_dilution(body: DilutionRequest, _: dict = Depends(get_current_user)):
    """Calcule l'impact d'un tour de table sur la participation des fondateurs."""
    scenario = fundraising_module.calculate_dilution(
        body.pre_money_tnd, body.investment_tnd, body.cap_table
    )
    return {
        "pre_money_tnd": scenario.pre_money_tnd,
        "investment_tnd": scenario.investment_tnd,
        "post_money_tnd": scenario.post_money_tnd,
        "investor_pct": scenario.investor_pct,
        "founders_before": scenario.founders_before,
        "founders_after": scenario.founders_after,
    }


@router.post("/fundraising/translate-term", tags=["Levée de fonds"])
async def translate_term_sheet(term_sheet: str, _: dict = Depends(get_current_user)):
    """Traduit un term sheet en langage clair."""
    return fundraising_module.translate_term_sheet(term_sheet)


# ─────────────────────────────────────────────
# MODULE 5 — CONFORMITÉ
# ─────────────────────────────────────────────

@router.post("/compliance/report", tags=["Conformité"])
async def compliance_report(body: ComplianceReportRequest, _: dict = Depends(get_current_user)):
    """Génère le rapport de conformité légale de la startup."""
    report = compliance_module.generate_report(
        company_name=body.company_name,
        legal_form=body.legal_form,
        employees_count=body.employees_count,
        has_users_data=body.has_users_data,
        has_inpdp_declaration=body.has_inpdp_declaration,
        has_written_contracts=body.has_written_contracts,
        vat_registered=body.vat_registered,
        startup_label=body.startup_label,
        last_cnss_declaration=body.last_cnss_declaration,
        last_tva_declaration=body.last_tva_declaration,
    )
    return {
        "company": report.company_name,
        "date": report.report_date,
        "score": report.score,
        "score_label": report.score_label,
        "alerts": [
            {
                "category": a.category,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "deadline": a.deadline,
                "action": a.action_required,
                "penalty": a.penalty_if_missed,
            }
            for a in report.alerts
        ],
        "compliant_items": report.compliant_items,
        "next_deadlines": report.next_deadlines,
    }


@router.post("/compliance/payroll", tags=["Conformité"])
async def calculate_payroll(body: PayrollRequest, _: dict = Depends(get_current_user)):
    """Calcule la masse salariale et les charges sociales."""
    return compliance_module.calculate_payroll(body.employees)


# ─────────────────────────────────────────────
# DONNÉES DE RÉFÉRENCE
# ─────────────────────────────────────────────

@router.get("/data/tax-rates", tags=["Données"])
async def get_tax_rates():
    """Retourne les taux fiscaux en vigueur (DGI + CNSS)."""
    return get_all_data()


@router.get("/data/license/{spdx_id}", tags=["Données"])
async def get_license_info(spdx_id: str):
    """Retourne l'analyse d'une licence logicielle."""
    return check_saas_risk(spdx_id)
