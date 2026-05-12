"""
RADAR-EP — Similaridade NLP (Sentence-Transformers)
=====================================================
Indicador 2: Divergência semântica entre objeto do convênio e função orçamentária.
"""

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Carrega o modelo de embeddings (lazy, singleton)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Modelo multilíngue leve, funciona bem com português
            _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            logger.info("Modelo NLP carregado: paraphrase-multilingual-MiniLM-L12-v2")
        except ImportError:
            raise ImportError(
                "sentence-transformers não instalado. "
                "Execute: pip install sentence-transformers"
            )
    return _model


def calcular_similaridade_objeto(texto1: str, texto2: str) -> float:
    """
    Calcula similaridade coseno entre dois textos.

    Args:
        texto1: objeto do convênio
        texto2: nome da função orçamentária

    Returns:
        float entre 0.0 (completamente diferente) e 1.0 (idêntico)
    """
    if not texto1 or not texto2:
        return 1.0  # sem texto, não aciona flag

    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        model = _get_model()
        emb = model.encode([texto1[:512], texto2[:512]])
        sim = cosine_similarity([emb[0]], [emb[1]])[0][0]
        return float(sim)
    except Exception as e:
        logger.error("Erro no cálculo de similaridade: %s", e)
        return 1.0  # em caso de erro, não aciona flag


def verificar_divergencia_lote(
    pares: list,  # list of (objeto, funcao) tuples
    limiar: float = 0.40,
) -> list:
    """
    Verifica divergência para um lote de pares (objeto, função).

    Returns:
        list of dicts com similaridade e flag_divergente
    """
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        model = _get_model()
        textos = []
        for obj, func in pares:
            textos.append(str(obj)[:512])
            textos.append(str(func)[:512])

        embeddings = model.encode(textos)
        resultados = []

        for i, (obj, func) in enumerate(pares):
            emb1 = embeddings[i * 2]
            emb2 = embeddings[i * 2 + 1]
            sim = float(cosine_similarity([emb1], [emb2])[0][0])
            resultados.append({
                "objeto": obj,
                "funcao": func,
                "similaridade": round(sim, 4),
                "flag_divergente": sim < limiar,
            })

        return resultados
    except Exception as e:
        logger.error("Erro na verificação em lote: %s", e)
        return [{"similaridade": 1.0, "flag_divergente": False} for _ in pares]
