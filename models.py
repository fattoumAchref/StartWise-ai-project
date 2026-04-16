"""
Tous les modèles SQLAlchemy — un seul fichier pour rester simple.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, Date,
    DateTime, ForeignKey, ARRAY, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


# ─────────────────────────────────────────────
# TEXTES LÉGISLATIFS (JORT)
# ─────────────────────────────────────────────

class LegalText(Base):
    __tablename__ = "legal_texts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jort_number: Mapped[Optional[str]] = mapped_column(String(50))
    publication_date: Mapped[Optional[str]] = mapped_column(String(20))
    text_type: Mapped[str] = mapped_column(String(20))
    # loi / decret-loi / decret / arrete / circulaire
    domain: Mapped[str] = mapped_column(String(50), default="GENERAL")
    # SOCIETES / TRAVAIL / FISCAL / COMMERCIAL / DONNEES_PERSONNELLES / ...
    title_fr: Mapped[Optional[str]] = mapped_column(Text)
    title_ar: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(15), default="EN_VIGUEUR")
    # EN_VIGUEUR / MODIFIE / ABROGE
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    articles: Mapped[list["Article"]] = relationship("Article", back_populates="legal_text", cascade="all, delete-orphan")


class Article(Base):
    """
    Unité d'embedding pour les textes législatifs.
    Le contexte hiérarchique (hierarchy_path) est injecté dans chaque chunk.
    """
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_text_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_texts.id", ondelete="CASCADE"))
    article_number: Mapped[str] = mapped_column(String(30))
    hierarchy_path: Mapped[Optional[str]] = mapped_column(Text)
    # Ex: "Titre III > Chapitre II > Art. 23"
    parent_title: Mapped[Optional[str]] = mapped_column(Text)
    content_fr: Mapped[Optional[str]] = mapped_column(Text)
    content_ar: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(15), default="EN_VIGUEUR")
    qdrant_id: Mapped[Optional[str]] = mapped_column(String(100))
    # ID dans le vector store Qdrant

    legal_text: Mapped["LegalText"] = relationship("LegalText", back_populates="articles")

    def to_chunk(self) -> str:
        """Chunk enrichi de métadonnées — c'est ce qui est embedé."""
        lt = self.legal_text
        return (
            f"{self.hierarchy_path or ''}\n"
            f"Texte : {lt.title_fr if lt else ''}\n"
            f"Référence : {lt.jort_number if lt else ''} | Date : {lt.publication_date if lt else ''}\n"
            f"Statut : {self.status}\n\n"
            f"{self.content_fr or ''}"
        ).strip()


# ─────────────────────────────────────────────
# MARQUES INNORPI
# ─────────────────────────────────────────────

class Trademark(Base):
    """
    Marque déposée.
    Champ clé : name_phonetic — encodage phonétique pour détecter les similarités sonores.
    """
    __tablename__ = "trademarks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_exact: Mapped[str] = mapped_column(String(500))
    name_phonetic: Mapped[Optional[str]] = mapped_column(String(500))
    name_normalized: Mapped[Optional[str]] = mapped_column(String(500))
    holder_name: Mapped[Optional[str]] = mapped_column(Text)
    nice_classes: Mapped[Optional[list]] = mapped_column(JSONB)
    filing_date: Mapped[Optional[str]] = mapped_column(String(20))
    expiry_date: Mapped[Optional[str]] = mapped_column(String(20))
    registration_number: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(15), default="ACTIF")
    # ACTIF / EXPIRE / ANNULE / EN_COURS
    qdrant_id: Mapped[Optional[str]] = mapped_column(String(100))

    def to_chunk(self) -> str:
        classes_str = ", ".join(str(c) for c in (self.nice_classes or []))
        return (
            f"Marque : {self.name_exact}\n"
            f"Phonétique : {self.name_phonetic or ''}\n"
            f"Normalisé : {self.name_normalized or ''}\n"
            f"Classes Nice : {classes_str}\n"
            f"Titulaire : {self.holder_name or ''}\n"
            f"Statut : {self.status} | Expiration : {self.expiry_date or 'N/A'}"
        ).strip()


# ─────────────────────────────────────────────
# TAUX FISCAUX (DGI)
# ─────────────────────────────────────────────

class TaxRate(Base):
    __tablename__ = "tax_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_type: Mapped[str] = mapped_column(String(30))
    # TVA / IS / IRPP / TFP / FOPROLOS / CNSS_PATRONAL / CNSS_SALARIAL
    rate: Mapped[float] = mapped_column(Numeric(8, 4))
    sector: Mapped[Optional[str]] = mapped_column(String(200))
    income_bracket_min: Mapped[Optional[float]] = mapped_column(Numeric(15, 3))
    income_bracket_max: Mapped[Optional[float]] = mapped_column(Numeric(15, 3))
    effective_from: Mapped[str] = mapped_column(String(20))
    effective_to: Mapped[Optional[str]] = mapped_column(String(20))
    is_preferential: Mapped[bool] = mapped_column(Boolean, default=False)
    preferential_conditions: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class FiscalDeadline(Base):
    __tablename__ = "fiscal_deadlines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_type: Mapped[str] = mapped_column(String(30))
    declaration_type: Mapped[str] = mapped_column(String(20))
    # MENSUELLE / TRIMESTRIELLE / ANNUELLE
    name_fr: Mapped[str] = mapped_column(Text)
    deadline_rule: Mapped[str] = mapped_column(Text)
    deadline_day: Mapped[Optional[int]]
    deadline_month: Mapped[Optional[int]]
    penalty_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    applies_to: Mapped[Optional[dict]] = mapped_column(JSONB)


# ─────────────────────────────────────────────
# JURISPRUDENCE
# ─────────────────────────────────────────────

class CourtDecision(Base):
    __tablename__ = "court_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_number: Mapped[Optional[str]] = mapped_column(String(100))
    decision_date: Mapped[Optional[str]] = mapped_column(String(20))
    court: Mapped[str] = mapped_column(String(50))
    # COUR_CASSATION / TPI_TUNIS / CA_TUNIS / ...
    chamber: Mapped[Optional[str]] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(50))
    # SOCIETES / TRAVAIL / COMMERCIAL / MARQUES / FISCAL
    facts_summary: Mapped[Optional[str]] = mapped_column(Text)
    legal_issue: Mapped[Optional[str]] = mapped_column(Text)
    ruling: Mapped[Optional[str]] = mapped_column(Text)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    is_landmark: Mapped[bool] = mapped_column(Boolean, default=False)
    qdrant_id: Mapped[Optional[str]] = mapped_column(String(100))

    def to_chunk(self) -> str:
        return (
            f"Tribunal : {self.court} | {self.chamber or ''}\n"
            f"Date : {self.decision_date} | N° {self.decision_number}\n"
            f"Domaine : {self.domain}\n\n"
            f"FAITS : {self.facts_summary or ''}\n\n"
            f"QUESTION : {self.legal_issue or ''}\n\n"
            f"DÉCISION : {self.ruling or ''}\n\n"
            f"MOTIFS : {self.reasoning or ''}"
        ).strip()


# ─────────────────────────────────────────────
# LICENCES LOGICIELLES
# ─────────────────────────────────────────────

class SoftwareLicense(Base):
    __tablename__ = "software_licenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spdx_id: Mapped[str] = mapped_column(String(50), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    permissions: Mapped[Optional[list]] = mapped_column(JSONB)
    # commercial-use / modifications / distribution / patent-use / private-use
    conditions: Mapped[Optional[list]] = mapped_column(JSONB)
    # include-copyright / disclose-source / same-license / network-use-disclose
    limitations: Mapped[Optional[list]] = mapped_column(JSONB)
    # liability / warranty / trademark-use
    copyleft_level: Mapped[Optional[str]] = mapped_column(String(20))
    # none / weak / strong / network
    full_text: Mapped[Optional[str]] = mapped_column(Text)
    summary_fr: Mapped[Optional[str]] = mapped_column(Text)
    osi_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    compatible_with: Mapped[Optional[list]] = mapped_column(JSONB)
    incompatible_with: Mapped[Optional[list]] = mapped_column(JSONB)
    qdrant_id: Mapped[Optional[str]] = mapped_column(String(100))


class LicenseCompatibility(Base):
    __tablename__ = "license_compatibility"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_a: Mapped[str] = mapped_column(String(50))
    license_b: Mapped[str] = mapped_column(String(50))
    compatible: Mapped[bool] = mapped_column(Boolean)
    direction: Mapped[str] = mapped_column(String(20), default="both")
    notes: Mapped[Optional[str]] = mapped_column(Text)


# ─────────────────────────────────────────────
# CLAUSES DE CONTRATS
# ─────────────────────────────────────────────

class ContractClause(Base):
    __tablename__ = "contract_clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    semantic_label: Mapped[str] = mapped_column(String(100))
    # "clause de non-concurrence" / "clause de confidentialité" / ...
    contract_type: Mapped[Optional[str]] = mapped_column(String(40))
    # CDI / CDD / NDA / PRESTATION_SERVICES / ...
    language: Mapped[str] = mapped_column(String(5), default="fr")
    title: Mapped[Optional[str]] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(10), default="FAIBLE")
    # FAIBLE / MOYEN / ELEVE / CRITIQUE
    risk_explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_dangerous: Mapped[bool] = mapped_column(Boolean, default=False)
    legally_valid_in_tunisia: Mapped[bool] = mapped_column(Boolean, default=True)
    legal_limit: Mapped[Optional[str]] = mapped_column(Text)
    legal_basis: Mapped[Optional[str]] = mapped_column(Text)
    qdrant_id: Mapped[Optional[str]] = mapped_column(String(100))

    def to_chunk(self) -> str:
        return (
            f"Type de clause : {self.semantic_label}\n"
            f"Contrat : {self.contract_type or 'Général'} | Risque : {self.risk_level}\n"
            f"Droit applicable : Tunisie\n\n"
            f"{self.content}"
        ).strip()


# ─────────────────────────────────────────────
# UTILISATEURS & SESSIONS
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    preferred_language: Mapped[str] = mapped_column(String(5), default="fr")
    expertise_level: Mapped[str] = mapped_column(String(20), default="NOVICE")
    # NOVICE / INTERMEDIATE / ADVANCED / EXPERT
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    companies: Mapped[list["UserCompany"]] = relationship("UserCompany", back_populates="owner")


class UserCompany(Base):
    """Entreprise rattachée à un compte utilisateur (contexte de session)."""
    __tablename__ = "user_companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    legal_form: Mapped[Optional[str]] = mapped_column(String(20))
    rne_id: Mapped[Optional[str]] = mapped_column(String(20))
    tax_id: Mapped[Optional[str]] = mapped_column(String(20))
    sector: Mapped[Optional[str]] = mapped_column(String(200))
    capital: Mapped[Optional[float]]
    nice_classes: Mapped[Optional[list]] = mapped_column(JSONB)
    startup_label: Mapped[bool] = mapped_column(Boolean, default=False)
    context_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    owner: Mapped["User"] = relationship("User", back_populates="companies")


class ChatSession(Base):
    """Historique de conversation."""
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("user_companies.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="fr")
    messages: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # [{role: user|assistant, content: str, timestamp: str, sources: [...]}]
    active_module: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
