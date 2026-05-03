"""
Stratégie d'embedding — trois populations de chunks avec des traitements différents.

1. Textes de loi  → article + contexte hiérarchique injecté
2. Marques        → nom après normalisation phonétique
3. Clauses        → clause + label sémantique

Le normaliseur phonétique est la pièce critique pour la détection de marques similaires.
"""

import re
import asyncio
import os
import unicodedata
import jellyfish
import numpy as np
from config import cfg
import structlog

log = structlog.get_logger(__name__)


# ─────────────────────────────────────────────
# NORMALISATION PHONÉTIQUE
# ─────────────────────────────────────────────

class PhoneticNormalizer:
    """
    Normalise et encode phonétiquement un nom de marque.
    Supporte l'arabe tunisien translittéré, le français et l'anglais.
    """

    # Correspondances phonétiques pour l'arabe translittéré
    ARABIC_PHONETIC_MAP = {
        "kh": "K", "gh": "G", "sh": "S", "ch": "S",
        "th": "T", "dh": "D", "ph": "F",
        "ou": "U", "eu": "E", "ei": "I", "ai": "E",
        "ck": "K", "qu": "K", "x": "KS",
    }

    def normalize(self, name: str) -> str:
        """Normalise : minuscule, sans diacritiques, sans espaces."""
        name = name.lower().strip()
        # Supprime les diacritiques
        name = unicodedata.normalize("NFD", name)
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")
        # Supprime caractères non alphanumériques
        name = re.sub(r"[^a-z0-9]", "", name)
        return name

    def encode(self, name: str) -> str:
        """
        Encode phonétiquement le nom pour la détection de similarité sonore.
        Ex: "Takwin" → "TKWN", "Takween" → "TKWN" (même code)
        """
        normalized = self.normalize(name)

        # Application des substitutions phonétiques arabe/français
        for pattern, replacement in self.ARABIC_PHONETIC_MAP.items():
            normalized = normalized.replace(pattern, replacement)

        # Soundex sur le résultat normalisé
        try:
            soundex = jellyfish.soundex(normalized)
        except Exception:
            soundex = normalized[:4].upper()

        # Metaphone pour compléter
        try:
            metaphone = jellyfish.metaphone(normalized)
        except Exception:
            metaphone = ""

        # Combinaison des deux représentations
        return f"{soundex}_{metaphone}"

    def generate_variants(self, name: str) -> list[str]:
        """Génère des variantes phonétiques d'un nom pour la recherche élargie."""
        variants = [name]
        norm = self.normalize(name)

        # Variantes orthographiques communes
        replacements = [
            ("ou", "u"), ("ee", "i"), ("ck", "k"),
            ("ph", "f"), ("w", "v"), ("y", "i"),
        ]
        for old, new in replacements:
            if old in norm:
                variants.append(norm.replace(old, new))

        return list(set(variants))

    def similarity_score(self, name_a: str, name_b: str) -> float:
        """
        Score de similarité phonétique entre deux noms (0.0 à 1.0).
        Combine Jaro-Winkler + correspondance des codes phonétiques.
        """
        norm_a = self.normalize(name_a)
        norm_b = self.normalize(name_b)

        # Similarité de chaîne
        jaro = jellyfish.jaro_winkler_similarity(norm_a, norm_b)

        # Correspondance des codes phonétiques
        phonetic_match = 1.0 if self.encode(name_a) == self.encode(name_b) else 0.0

        # Score combiné (phonétique pondéré plus fort)
        return 0.4 * jaro + 0.6 * phonetic_match


# ─────────────────────────────────────────────
# EMBEDDINGS
# ─────────────────────────────────────────────

class EmbeddingService:
    """
    Service d'embedding local — intfloat/multilingual-e5-base.
    Gratuit, tourne en local, supporte arabe / français / anglais.
    Dimension : 768.

    Le modèle est chargé une seule fois au démarrage (singleton).
    Les appels sont synchrones côté SentenceTransformer mais wrappés
    dans asyncio.to_thread pour ne pas bloquer la boucle FastAPI.
    """

    def __init__(self):
        log.info("loading_embedding_model", model=cfg.embedding_model)
        # Evite les imports optionnels TF/Flax qui peuvent casser certains environnements Windows.
        os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
        os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(cfg.embedding_model)
        except Exception as e:
            raise RuntimeError(
                "Echec du chargement sentence-transformers. "
                "Verifier la compatibilite des versions torch/torchvision/transformers. "
                f"Erreur: {e}"
            ) from e
        self.phonetizer = PhoneticNormalizer()
        log.info("embedding_model_ready", dim=cfg.embedding_dim)

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """
        Encodage synchrone.
        multilingual-e5-base préfère le préfixe "query: " pour les requêtes
        et "passage: " pour les documents — améliore la qualité du retrieval.
        """
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    async def embed(self, text: str) -> list[float]:
        """Embedding générique async d'un texte."""
        vecs = await asyncio.to_thread(self._encode_sync, [f"passage: {text[:512]}"])
        return vecs[0]

    async def embed_query(self, query: str, context: str = "") -> list[float]:
        """
        Embedding d'une requête utilisateur.
        Préfixe "query: " recommandé par multilingual-e5-base pour les requêtes.
        """
        full = f"{context}\n\n{query}".strip() if context else query
        vecs = await asyncio.to_thread(self._encode_sync, [f"query: {full[:512]}"])
        return vecs[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embedding de plusieurs textes en une seule passe (plus rapide)."""
        passages = [f"passage: {t[:512]}" for t in texts]
        return await asyncio.to_thread(self._encode_sync, passages)

    async def embed_legal_article(self, article) -> list[float]:
        """Stratégie 1 : Article de loi avec contexte hiérarchique injecté."""
        return await self.embed(article.to_chunk())

    async def embed_trademark(self, trademark) -> list[float]:
        """Stratégie 2 : Marque — embedding sur la représentation phonétique."""
        return await self.embed(trademark.to_chunk())

    async def embed_trademark_query(self, name: str, nice_classes: list[int]) -> list[float]:
        """Embedding d'une requête de vérification de marque."""
        phonetic = self.phonetizer.encode(name)
        normalized = self.phonetizer.normalize(name)
        classes_str = ", ".join(str(c) for c in nice_classes)
        chunk = (
            f"Marque : {name}\n"
            f"Phonétique : {phonetic}\n"
            f"Normalisé : {normalized}\n"
            f"Classes Nice : {classes_str}"
        )
        vecs = await asyncio.to_thread(self._encode_sync, [f"query: {chunk}"])
        return vecs[0]

    async def embed_contract_clause(self, clause) -> list[float]:
        """Stratégie 3 : Clause de contrat avec label sémantique."""
        return await self.embed(clause.to_chunk())


# Singletons
phonetizer = PhoneticNormalizer()
embedding_service = EmbeddingService()
