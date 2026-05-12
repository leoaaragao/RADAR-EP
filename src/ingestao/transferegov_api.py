"""
RADAR-EP — Transferegov.br API
===============================
Indicador 9: Prestação de contas vencida.
Também verifica: plano de trabalho ausente (LC 210/2024), conta específica.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"

IBGES_FRANCA = (
    "3516200", "3503000", "3508207", "3513207", "3517703",
    "3520103", "3521309", "3523701", "3524105", "3525409",
    "3536307", "3537008", "3542701", "3543105", "3543600",
    "3549409", "3549508",
)


def _ibge_filter(ibges: Optional[list] = None) -> str:
    """Formata filtro PostgREST para lista de IBGEs."""
    lista = ibges or list(IBGES_FRANCA)
    return f"in.({','.join(lista)})"


def verificar_pc_vencida(
    ibges: Optional[list] = None,
    dias_tolerancia: int = 30,
) -> list:
    """
    Indicador 9 — Convênios com prestação de contas vencida.

    Args:
        ibges: lista de códigos IBGE (padrão: 17 municípios da 13ª SJ)
        dias_tolerancia: dias após vencimento para considerar vencido (padrão: 30)

    Returns:
        Lista de planos de ação com PC vencida
    """
    prazo_limite = date.today() - timedelta(days=dias_tolerancia)

    try:
        r = httpx.get(
            f"{BASE_URL}/plano_acao_especial",
            params={
                "municipio_ibge": _ibge_filter(ibges),
                "data_fim_vigencia": f"lt.{prazo_limite.isoformat()}",
                "limit": "1000",
            },
            timeout=30,
        )
        if r.status_code == 200:
            dados = r.json()
            logger.info("PC vencida: %d registros encontrados", len(dados))
            return dados
        logger.warning("Transferegov PC vencida: HTTP %s", r.status_code)
        return []
    except Exception as e:
        logger.error("Erro ao verificar PC vencida: %s", e)
        return []


def buscar_planos_sem_trabalho(ibges: Optional[list] = None) -> list:
    """
    Hard flag LC 210/2024 — transferências especiais sem plano de trabalho.
    """
    try:
        r = httpx.get(
            f"{BASE_URL}/plano_acao_especial",
            params={
                "municipio_ibge": _ibge_filter(ibges),
                "plano_trabalho": "is.null",
                "limit": "1000",
            },
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
        return []
    except Exception as e:
        logger.error("Erro ao buscar planos sem trabalho: %s", e)
        return []


def buscar_executor_especial(ibges: Optional[list] = None, ano: Optional[int] = None) -> list:
    """
    Verifica dados bancários do executor (conta específica por emenda).
    Disponível desde jul/2025 (LC 210/2024).
    """
    params = {
        "municipio_ibge": _ibge_filter(ibges),
        "limit": "1000",
    }
    if ano:
        params["ano"] = f"eq.{ano}"

    try:
        r = httpx.get(f"{BASE_URL}/executor_especial", params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        logger.warning("executor_especial: HTTP %s", r.status_code)
        return []
    except Exception as e:
        logger.error("Erro ao buscar executor_especial: %s", e)
        return []


def buscar_planos_acao(ibges: Optional[list] = None, ano: Optional[int] = None) -> list:
    """
    Busca planos de ação de transferências especiais.
    """
    params = {"municipio_ibge": _ibge_filter(ibges), "limit": "1000"}
    if ano:
        params["ano"] = f"eq.{ano}"

    try:
        r = httpx.get(f"{BASE_URL}/plano_acao_especial", params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception as e:
        logger.error("Erro ao buscar planos de ação: %s", e)
        return []
