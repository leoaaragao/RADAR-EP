import pandas as pd
import duckdb
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'radar_ep.duckdb'
CSV_PATH = 'data/EmendasParlamentares_PorFavorecido.csv'

# Mapeamento de Cidades para IBGE
MAP_MUNICIPIOS = {
    'FRANCA': '3516200', 'BATATAIS': '3505906', 'ARAMINA': '3503000',
    'CRISTAIS PAULISTA': '3513207', 'GUARA': '3518209', 'IGARAPAVA': '3518803',
    'IPUA': '3521309', 'ITIRAPUA': '3523701', 'ITUVERAVA': '3524105',
    'JERIQUARA': '3525409', 'NUPORANGA': '3533403', 'ORLANDIA': '3534302',
    'PATROCINIO PAULISTA': '3536307', 'RESTINGA': '3542701', 'RIBEIRAO CORRENTE': '3543105',
    'RIFAINA': '3543600', 'SAO JOAQUIM DA BARRA': '3549409', 'SAO JOSE DA BELA VISTA': '3549508',
    'BURITIZAL': '3508207'
}

def import_pix():
    if not os.path.exists(CSV_PATH):
        logger.error(f"Arquivo não encontrado: {CSV_PATH}")
        return

    logger.info("Lendo arquivo de Favorecidos com Pandas (usando índices)...")
    
    try:
        df = pd.read_csv(CSV_PATH, sep=';', encoding='latin1', dtype=str)
        cols = df.columns.tolist()
        df = df.rename(columns={
            cols[0]: 'cod',
            cols[2]: 'autor',
            cols[4]: 'tipo',
            cols[10]: 'uf',
            cols[11]: 'mun',
            cols[12]: 'valor'
        })
        
        logger.info(f"Arquivo lido. Total de linhas: {len(df)}")
        
        df_sj = df[
            (df['mun'].isin(MAP_MUNICIPIOS.keys())) & 
            (df['uf'] == 'SP') & 
            (df['tipo'].str.contains('Especiais', na=False, case=False))
        ].copy()
        
        if df_sj.empty:
            logger.warning("Nenhuma emenda PIX encontrada para as cidades da SJ no arquivo.")
            return

        logger.info(f"Encontradas {len(df_sj)} linhas de emendas PIX para a região.")
        
        def clean_val(x):
            if pd.isna(x): return 0.0
            return float(str(x).replace('.', '').replace(',', '.'))
        
        df_sj['valor_num'] = df_sj['valor'].apply(clean_val)
        df_sj['ano'] = df_sj['cod'].str[:4].astype(int)
        df_sj['ibge'] = df_sj['mun'].map(MAP_MUNICIPIOS)
        
        con = duckdb.connect(DB_PATH)
        
        logger.info("Limpando duplicatas e inserindo dados no DuckDB...")
        
        con.execute("CREATE OR REPLACE TEMPORARY TABLE temp_pix AS SELECT * FROM df_sj")
        
        # Remover o que já existe para evitar duplicatas sem PK
        con.execute('DELETE FROM emendas_parlamentares WHERE "Código da Emenda" IN (SELECT cod FROM temp_pix)')
        
        sql_insert = """
            INSERT INTO emendas_parlamentares (
                "Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Nome do Autor da Emenda",
                "Município", "Código Município IBGE", "UF", "Valor Pago", "Valor Empenhado"
            )
            SELECT 
                cod, ano, tipo, autor,
                mun, ibge, uf, valor_num, valor_num
            FROM temp_pix
        """
        con.execute(sql_insert)
        con.close()
        
        logger.info("✓ Importação de emendas PIX concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro na importação: {e}")

if __name__ == "__main__":
    import_pix()
