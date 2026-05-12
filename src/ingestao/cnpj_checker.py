"""
RADAR-EP — Módulo de Consulta CNPJ (BrasilAPI / Receita Federal)
================================================================
Indicador 3: Empresa com menos de 24 meses na data do contrato/convênio.
"""

import json
import logging
import time
from datetime import date
from typing import Optional

import duckdb
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)
BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

CNAES_ALTO_RISCO = {
    "4120400", "4211101", "4221904",
    "8610101", "5611201", "4711301",
}


def limpar_cnpj(cnpj: str) -> str:
    return "".join(c for c in str(cnpj) if c.isdigit())


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
)
def _consultar_brasilapi(cnpj_limpo: str) -> dict:
    url = BRASILAPI_URL.format(cnpj=cnpj_limpo)
    r = httpx.get(url, timeout=12)
    r.raise_for_status()
    return r.json()


def verificar_idade_empresa(
    cnpj: str,
    data_referencia: Optional[date] = None,
    db_path: str = "radar_ep.duckdb",
) -> dict:
    """
    Verifica idade e situação cadastral de empresa via BrasilAPI.
    Usa cache local no DuckDB para evitar chamadas repetidas.
    """
    cnpj_limpo = limpar_cnpj(cnpj)
    data_ref = data_referencia or date.today()

    resultado = {
        "cnpj": cnpj_limpo,
        "razao_social": None,
        "situacao": None,
        "data_abertura": None,
        "idade_meses": None,
        "flag_jovem": False,
        "flag_inativa": False,
        "flag_cnae_risco": False,
        "cnaes": None,
        "socios": None,
        "erro": None,
    }

    # ── 1. Verificar cache ─────────────────────────────────────
    try:
        con = duckdb.connect(db_path)
        cached = con.execute(
            "SELECT * FROM cnpj_cache WHERE cnpj = ?", [cnpj_limpo]
        ).fetchone()
        if cached:
            cols = [d[0] for d in con.description]
            row = dict(zip(cols, cached))
            if row.get("data_abertura"):
                delta = (data_ref - row["data_abertura"]).days / 30
                row["idade_meses"] = round(delta, 1)
                row["flag_jovem"] = delta < 24
            con.close()
            return row
        con.close()
    except Exception as e:
        logger.warning("Erro ao consultar cache CNPJ: %s", e)

    # ── 2. Consultar BrasilAPI ─────────────────────────────────
    try:
        dados = _consultar_brasilapi(cnpj_limpo)

        resultado["razao_social"] = dados.get("razao_social", "")
        resultado["situacao"] = dados.get("descricao_situacao_cadastral", "")
        resultado["flag_inativa"] = resultado["situacao"].upper() not in ("ATIVA",)

        data_str = dados.get("data_inicio_atividade", "")
        if data_str:
            data_abertura = date.fromisoformat(data_str)
            resultado["data_abertura"] = data_abertura
            idade = (data_ref - data_abertura).days / 30
            resultado["idade_meses"] = round(idade, 1)
            resultado["flag_jovem"] = idade < 24

        cnae_cod = str(dados.get("cnae_fiscal", ""))
        cnaes_sec = [str(c.get("codigo", "")) for c in dados.get("cnaes_secundarios", [])]
        cnaes_list = [cnae_cod] + cnaes_sec
        resultado["cnaes"] = json.dumps(cnaes_list)
        resultado["flag_cnae_risco"] = any(c in CNAES_ALTO_RISCO for c in cnaes_list)

        socios = dados.get("qsa", [])
        resultado["socios"] = json.dumps([
            {"nome": s.get("nome_socio"), "qualificacao": s.get("qualificacao_socio")}
            for s in socios
        ])

        # Salvar no cache
        try:
            con = duckdb.connect(db_path)
            con.execute("""
                INSERT OR REPLACE INTO cnpj_cache
                    (cnpj, razao_social, situacao, data_abertura,
                     idade_meses, flag_jovem, cnaes, socios, data_consulta, erro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp, NULL)
            """, [
                cnpj_limpo, resultado["razao_social"], resultado["situacao"],
                resultado["data_abertura"], resultado["idade_meses"],
                resultado["flag_jovem"], resultado["cnaes"], resultado["socios"],
            ])
            con.close()
        except Exception as e:
            logger.warning("Erro ao salvar cache CNPJ: %s", e)

    except httpx.HTTPStatusError as e:
        resultado["erro"] = f"HTTP {e.response.status_code}"
    except Exception as e:
        resultado["erro"] = str(e)
        logger.error("Erro ao verificar CNPJ %s: %s", cnpj_limpo, e)

    return resultado


def verificar_lote_cnpjs(
    cnpjs: list,
    data_referencia: Optional[date] = None,
    db_path: str = "radar_ep.duckdb",
    delay_segundos: float = 0.5,
) -> list:
    resultados = []
    for i, cnpj in enumerate(cnpjs):
        if i > 0:
            time.sleep(delay_segundos)
        resultado = verificar_idade_empresa(cnpj, data_referencia, db_path)
        resultados.append(resultado)
    return resultados
