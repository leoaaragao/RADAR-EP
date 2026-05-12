import logging
import os
import sys
from pathlib import Path
import duckdb
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.risco.risk_engine import processar_lote
from src.risco.alerta_writer import salvar_lote_alertas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("radar_ep.score")

def score_recent_data():
    db_path = "radar_ep.duckdb"
    con = duckdb.connect(db_path)
    
    logger.info("Buscando dados de 2024-2026 para análise de risco (apenas 13ª SJ)...")
    ibges = ('3516200','3503000','3508207','3513207','3517703','3520103','3521309','3523701','3524105','3525409','3536307','3537008','3542701','3543105','3543600','3549409','3549508')
    df = con.execute(f"""
        SELECT * FROM emendas_parlamentares 
        WHERE "Ano da Emenda" >= 2024
          AND "Código Município IBGE" IN {ibges}
    """).df()
    
    if df.empty:
        logger.info("Nenhuma emenda encontrada para análise.")
        con.close()
        return

    logger.info(f"Analisando {len(df)} emendas...")
    
    # Processar risco (escore_minimo=0.01 para pegar qualquer sinal)
    alertas_df = processar_lote(df, db_path=db_path, escore_minimo=0.01)
    
    if not alertas_df.empty:
        logger.info(f"Gerados {len(alertas_df)} alertas potenciais. Salvando...")
        salvar_lote_alertas(alertas_df, db_path, escore_minimo=0.01)
        logger.info("✓ Alertas salvos com sucesso!")
    else:
        logger.info("Nenhum alerta gerado para os dados recentes.")
        
    con.close()

if __name__ == "__main__":
    score_recent_data()
