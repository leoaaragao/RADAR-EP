"""
RADAR-EP — Sincronização Diária (CGU + Transferegov PIX)
=============================================================
Versão 2026 — Sincroniza emendas orçamentárias e PIX para a 13ª SJ.
"""

import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
import duckdb
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("radar_ep.sync")

IBGES_FRANCA = [
    "3516200", "3503000", "3508207", "3513207", "3517703",
    "3520103", "3521309", "3523701", "3524105", "3525409",
    "3536307", "3537008", "3542701", "3543105", "3543600",
    "3549409", "3549508",
]

MUNICIPIOS_NOMES = {
    "3516200": "Franca",               "3503000": "Aramina",
    "3508207": "Buritizal",            "3513207": "Cristais Paulista",
    "3517703": "Guará",                "3520103": "Igarapava",
    "3521309": "Ipuã",                 "3523701": "Itirapuã",
    "3524105": "Ituverava",            "3525409": "Jeriquara",
    "3536307": "Patrocínio Paulista",  "3537008": "Pedregulho",
    "3542701": "Restinga",             "3543105": "Ribeirão Corrente",
    "3543600": "Rifaina",              "3549409": "São Joaquim da Barra",
    "3549508": "São José da Bela Vista",
}

def _parse_float(val) -> float:
    if not val: return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        v = str(val).replace(".", "").replace(",", ".")
        return float(v)
    except Exception: return 0.0

def normalizar_para_principal(dados: dict, municipio: str, ibge: str, ano: int) -> dict:
    """Mapeia campos da API para as 28 colunas da tabela principal."""
    return {
        "Código da Emenda": str(dados.get("codigoEmenda") or dados.get("codigo_emenda", "")),
        "Ano da Emenda": int(ano),
        "Tipo de Emenda": dados.get("tipoEmenda") or dados.get("tipo_emenda", "Emenda PIX" if "objeto" in dados else "S/I"),
        "Código do Autor da Emenda": str(dados.get("codigoAutor") or dados.get("autor_codigo", "")),
        "Nome do Autor da Emenda": dados.get("nomeAutor") or dados.get("autor_nome", ""),
        "Número da emenda": str(dados.get("numeroEmenda") or ""),
        "Localidade de aplicação do recurso": municipio,
        "Código Município IBGE": ibge,
        "Município": municipio,
        "Código UF IBGE": 35, # SP
        "UF": "SP",
        "Região": "SUDESTE",
        "Código Função": "",
        "Nome Função": dados.get("nomeFuncao") or ("Transferências Especiais" if "objeto" in dados else ""),
        "Código Subfunção": "",
        "Nome Subfunção": dados.get("nomeSubfuncao") or "",
        "Código Programa": "",
        "Nome Programa": "",
        "Código Ação": "",
        "Nome Ação": dados.get("nomeAcao") or dados.get("objeto") or "",
        "Código Plano Orçamentário": "",
        "Nome Plano Orçamentário": "",
        "Valor Empenhado": _parse_float(dados.get("valorEmpenhado") or dados.get("valor_emenda")),
        "Valor Liquidado": _parse_float(dados.get("valorLiquidado") or dados.get("valor_emenda")),
        "Valor Pago": _parse_float(dados.get("valorPago") or dados.get("valor_emenda")),
        "Valor Restos A Pagar Inscritos": _parse_float(dados.get("valorRestoInscrito") or 0),
        "Valor Restos A Pagar Cancelados": _parse_float(dados.get("valorRestoCancelado") or 0),
        "Valor Restos A Pagar Pagos": _parse_float(dados.get("valorRestoPago") or 0),
    }

def sincronizar_tudo(con, ibges, anos, chave_api):
    from src.ingestao.portal_api import buscar_emendas_municipio
    from src.ingestao.transferegov_api import buscar_planos_acao
    
    novos_total = 0
    for ibge in ibges:
        mun_nome = MUNICIPIOS_NOMES.get(ibge, ibge)
        for ano in anos:
            logger.info(f"Sincronizando {mun_nome} / {ano}...")
            
            # 1. Portal da Transparência
            emendas_cgu = buscar_emendas_municipio(ibge, ano, chave_api)
            # 2. Transferegov (PIX)
            emendas_pix = buscar_planos_acao(ibges=[ibge], ano=ano)
            
            combined = emendas_cgu + emendas_pix
            if not combined: continue
            
            registros = [normalizar_para_principal(e, mun_nome, ibge, ano) for e in combined]
            df = pd.DataFrame(registros)
            
            # Evitar duplicatas
            try:
                existentes = con.execute(f"SELECT \"Código da Emenda\" FROM emendas_parlamentares WHERE \"Código Município IBGE\" = '{ibge}' AND \"Ano da Emenda\" = {ano}").df()["Código da Emenda"].tolist()
                df = df[~df["Código da Emenda"].isin(existentes)]
            except: pass
            
            if not df.empty:
                con.register("_sync_tmp", df)
                con.execute("INSERT INTO emendas_parlamentares SELECT * FROM _sync_tmp")
                con.unregister("_sync_tmp")
                novos_total += len(df)
                logger.info(f"  → {len(df)} novos registros salvos.")
            
            time.sleep(0.5)
    return novos_total

def main():
    db_path = "radar_ep.duckdb"
    chave_api = os.getenv("PORTAL_TRANSPARENCIA_KEY", "")
    anos = [2024, 2025, 2026]
    
    con = duckdb.connect(db_path)
    novos = sincronizar_tudo(con, IBGES_FRANCA, anos, chave_api)
    con.close()
    
    print(f"\n✓ Sincronização finalizada. {novos} registros adicionados.")

if __name__ == "__main__":
    main()
