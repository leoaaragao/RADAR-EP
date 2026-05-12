import pandas as pd
import duckdb
import os
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'radar_ep.duckdb'
CSV_PATH = 'data/br_cgu_emendas_parlamentares_microdados.csv.gz'

def import_new_csv():
    if not os.path.exists(CSV_PATH):
        logger.error(f"Arquivo não encontrado: {CSV_PATH}")
        return

    logger.info(f"Carregando CSV: {CSV_PATH}")
    
    mapping = {
        'id_emenda': 'Código da Emenda',
        'ano_emenda': 'Ano da Emenda',
        'tipo_emenda': 'Tipo de Emenda',
        'id_autor_emenda': 'Código do Autor da Emenda',
        'nome_autor_emenda': 'Nome do Autor da Emenda',
        'numero_emenda': 'Número da emenda',
        'localidade': 'Localidade de aplicação do recurso',
        'id_municipio_gasto': 'Código Município IBGE',
        'id_funcao': 'Código Função',
        'nome_funcao': 'Nome Função',
        'id_subfuncao': 'Código Subfunção',
        'nome_subfuncao': 'Nome Subfunção',
        'id_programa': 'Código Programa',
        'nome_programa': 'Nome Programa',
        'id_acao': 'Código Ação',
        'nome_acao': 'Nome Ação',
        'id_plano_orcamentario': 'Código Plano Orçamentário',
        'nome_plano_orcamentario': 'Nome Plano Orçamentário',
        'valor_empenhado': 'Valor Empenhado',
        'valor_liquidado': 'Valor Liquidado',
        'valor_pago': 'Valor Pago',
        'valor_resto_pagar_inscrito': 'Valor Restos A Pagar Inscritos',
        'valor_resto_pagar_cancelado': 'Valor Restos A Pagar Cancelados',
        'valor_resto_pagar_pagos': 'Valor Restos A Pagar Pagos'
    }

    df = pd.read_csv(CSV_PATH, compression='gzip', low_memory=False)
    df = df.rename(columns=mapping)
    
    # Colunas que faltam no CSV mas existem no banco
    missing_cols = {
        'Município': df['Localidade de aplicação do recurso'], # Usar localidade como nome do município
        'Código UF IBGE': np.nan,
        'UF': df['sigla_uf_gasto'],
        'Região': np.nan
    }
    
    for col, val in missing_cols.items():
        df[col] = val
        
    # Garantir a ordem das colunas igual ao banco
    db_cols = [
        "Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Código do Autor da Emenda",
        "Nome do Autor da Emenda", "Número da emenda", "Localidade de aplicação do recurso",
        "Código Município IBGE", "Município", "Código UF IBGE", "UF", "Região",
        "Código Função", "Nome Função", "Código Subfunção", "Nome Subfunção",
        "Código Programa", "Nome Programa", "Código Ação", "Nome Ação",
        "Código Plano Orçamentário", "Nome Plano Orçamentário", "Valor Empenhado",
        "Valor Liquidado", "Valor Pago", "Valor Restos A Pagar Inscritos",
        "Valor Restos A Pagar Cancelados", "Valor Restos A Pagar Pagos"
    ]
    
    df = df[db_cols]
    
    # Tratar IBGE
    df['Código Município IBGE'] = df['Código Município IBGE'].astype(str).str.replace('.0', '', regex=False)
    
    con = duckdb.connect(DB_PATH)
    con.register('df_new', df)
    
    logger.info("Mesclando dados no banco local...")
    try:
        # Inserir apenas novos
        con.execute("""
            INSERT INTO emendas_parlamentares 
            SELECT * FROM df_new 
            WHERE NOT EXISTS (
                SELECT 1 FROM emendas_parlamentares e 
                WHERE e."Código da Emenda" = df_new."Código da Emenda"
                AND e."Ano da Emenda" = df_new."Ano da Emenda"
            )
        """)
        logger.info(f"✓ Importação concluída!")
    except Exception as e:
        logger.error(f"Erro: {e}")
    finally:
        con.close()

if __name__ == "__main__":
    import_new_csv()
