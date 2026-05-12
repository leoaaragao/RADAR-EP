"""
RADAR-EP — Portal da Transparência (CGU) API
=============================================
Indicador 7: Campos obrigatórios ausentes.
Também fornece: busca de emendas por município e ano.
"""

import logging
import os
import time
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
RATE_LIMIT_POR_MIN = 90   # Das 6h às 23h59
MAX_POR_PAGINA = 200


def _get_headers(chave_api: Optional[str] = None) -> dict:
    chave = chave_api or os.getenv("PORTAL_TRANSPARENCIA_KEY", "")
    if not chave:
        raise ValueError(
            "Chave da API do Portal da Transparência não encontrada. "
            "Configure PORTAL_TRANSPARENCIA_KEY no .env"
        )
    return {"chave-api-dados": chave}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def verificar_campos_obrigatorios(
    codigo_emenda: str,
    chave_api: Optional[str] = None,
) -> dict:
    """
    Indicador 7 — verifica se os campos obrigatórios estão presentes.

    Retorna:
        dict com flags: tem_autor, tem_objeto, tem_plano_trabalho, flag_incompleto
    """
    headers = _get_headers(chave_api)
    try:
        r = httpx.get(
            f"{BASE_URL}/emendas/{codigo_emenda}",
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            dados = r.json()
            tem_autor = bool(dados.get("autor") or dados.get("nomeAutor"))
            tem_objeto = bool(dados.get("objeto") or dados.get("descricaoObjeto"))
            tem_plano = bool(dados.get("planoTrabalho") or dados.get("numeroPlanoTrabalho"))
            return {
                "codigo_emenda": codigo_emenda,
                "tem_autor": tem_autor,
                "tem_objeto": tem_objeto,
                "tem_plano_trabalho": tem_plano,
                "flag_incompleto": not (tem_autor and tem_objeto),
                "flag_sem_plano_trabalho": not tem_plano,
                "status_http": 200,
            }
        return {"codigo_emenda": codigo_emenda, "erro": r.status_code, "status_http": r.status_code}
    except Exception as e:
        logger.error("Erro ao verificar emenda %s: %s", codigo_emenda, e)
        return {"codigo_emenda": codigo_emenda, "erro": str(e)}


def buscar_emendas_municipio(
    ibge: str,
    ano: int,
    chave_api: Optional[str] = None,
    max_paginas: int = 50,
) -> list:
    """
    Busca todas as emendas de um município em um ano via Portal da Transparência.
    Implementa paginação automática e controle de rate limit.
    """
    headers = _get_headers(chave_api)
    todos = []
    pagina = 1
    intervalo = 60 / RATE_LIMIT_POR_MIN  # ~0.67s entre chamadas

    while pagina <= max_paginas:
        try:
            r = httpx.get(
                f"{BASE_URL}/emendas",
                headers=headers,
                params={
                    "codigoIbge": ibge,
                    "anoExercicio": ano,
                    "pagina": pagina,
                },
                timeout=20,
            )
            if r.status_code == 404 or r.status_code == 204:
                break
            if r.status_code != 200:
                logger.warning("HTTP %s para ibge=%s ano=%s pág=%s", r.status_code, ibge, ano, pagina)
                break

            dados = r.json()
            if not dados:
                break

            if isinstance(dados, list):
                todos.extend(dados)
                if len(dados) < MAX_POR_PAGINA:
                    break
            else:
                todos.append(dados)
                break

            pagina += 1
            time.sleep(intervalo)

        except Exception as e:
            logger.error("Erro ao buscar emendas ibge=%s ano=%s: %s", ibge, ano, e)
            break

    logger.info("ibge=%s ano=%s: %d emendas encontradas", ibge, ano, len(todos))
    return todos


def buscar_todos_municipios_ano(
    ibges: list,
    anos: list,
    chave_api: Optional[str] = None,
) -> list:
    """
    Busca emendas para todos os municípios e anos fornecidos.
    """
    todos = []
    for ibge in ibges:
        for ano in anos:
            emendas = buscar_emendas_municipio(ibge, ano, chave_api)
            todos.extend(emendas)
            logger.info("Total acumulado: %d", len(todos))
    return todos
