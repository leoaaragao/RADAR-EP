"""
RADAR-EP — Carga via Base dos Dados (BigQuery)
===============================================
Fase 1.3 — carga histórica da tabela br_cgu_emendas_parlamentares.microdados.

Requer autenticação OAuth Google com acesso ao projeto nice-stack-440319-c6.
Na primeira execução, abre o browser para login.

Uso:
    python scripts/bigquery_loader.py
    python scripts/bigquery_loader.py --ano-inicio 2020
"""

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()

IBGES_FRANCA = (
    "3516200", "3503000", "3508207", "3513207", "3517703",
    "3520103", "3521309", "3523701", "3524105", "3525409",
    "3536307", "3537008", "3542701", "3543105", "3543600",
    "3549409", "3549508",
)


def carregar_bigquery(ano_inicio: int = 2020, db_path: str = "radar_ep.duckdb"):
    """
    Carrega dados históricos do BigQuery e salva no DuckDB.
    """
    try:
        import basedosdados as bd
        import duckdb
    except ImportError as e:
        print(f"Dependência não instalada: {e}")
        print("Execute: pip install basedosdados duckdb")
        sys.exit(1)

    project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
    bd.config.project_id = project_id

    ibge_str = "','".join(IBGES_FRANCA)

    print(f"\nConsultando BigQuery — Base dos Dados")
    print(f"Projeto: {project_id}")
    print(f"Período: {ano_inicio} a 2026")
    print(f"Municípios: {len(IBGES_FRANCA)} (13ª SJ Franca/SP)")
    print("\n⚠ Se for a primeira execução, o browser será aberto para autenticação OAuth.\n")

    query = f"""
        SELECT
            ano_emenda,
            id_emenda,
            tipo_emenda,
            id_autor_emenda,
            nome_autor_emenda,
            numero_emenda,
            localidade,
            id_municipio_gasto,
            nome_funcao,
            nome_subfuncao,
            nome_programa,
            nome_acao,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            valor_resto_pagar_inscrito,
            valor_resto_pagar_pagos
        FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
        WHERE id_municipio_gasto IN ('{ibge_str}')
          AND ano_emenda >= {ano_inicio}
    """

    try:
        df = bd.read_sql(query, billing_project_id=project_id)
        print(f"✓ BigQuery retornou {len(df):,} registros")

        if len(df) > 0:
            # Mapeamento de colunas para o padrão do dashboard
            mapping = {
                'ano_emenda': 'Ano da Emenda',
                'id_emenda': 'Código da Emenda',
                'tipo_emenda': 'Tipo de Emenda',
                'id_autor_emenda': 'Código do Autor da Emenda',
                'nome_autor_emenda': 'Nome do Autor da Emenda',
                'numero_emenda': 'Número da Emenda',
                'localidade': 'Localidade do Gasto',
                'id_municipio_gasto': 'Código Município IBGE',
                'nome_funcao': 'Função',
                'nome_subfuncao': 'Subfunção',
                'nome_programa': 'Programa',
                'nome_acao': 'Ação',
                'valor_empenhado': 'Valor Empenhado',
                'valor_liquidado': 'Valor Liquidado',
                'valor_pago': 'Valor Pago',
                'valor_resto_pagar_inscrito': 'Valor Restos A Pagar Inscritos',
                'valor_resto_pagar_pagos': 'Valor Restos A Pagar Pagos'
            }
            df = df.rename(columns=mapping)
            
            # Converter colunas de ano para string
            df['Ano da Emenda'] = df['Ano da Emenda'].astype(str)
            
            # Formatar valores monetários como string com vírgula para compatibilidade
            cols_valor = ['Valor Empenhado', 'Valor Liquidado', 'Valor Pago', 
                         'Valor Restos A Pagar Inscritos', 'Valor Restos A Pagar Pagos']
            for col in cols_valor:
                df[col] = df[col].apply(lambda x: str(x).replace('.', ','))

            con = duckdb.connect(db_path)
            tab_exists = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'emendas_parlamentares'").fetchone()[0]
            
            if tab_exists:
                anos_carregados = df["Ano da Emenda"].unique().tolist()
                anos_str = "','".join(anos_carregados)
                con.execute(f"DELETE FROM emendas_parlamentares WHERE \"Ano da Emenda\" IN ('{anos_str}') AND \"Código Município IBGE\" IN ('{ibge_str}')")
                con.execute("INSERT INTO emendas_parlamentares SELECT * FROM df")
            else:
                con.execute("CREATE TABLE emendas_parlamentares AS SELECT * FROM df")
            
            con.close()
            print(f"✓ Dados integrados na tabela 'emendas_parlamentares'")
        else:
            print("! Nenhum dado novo encontrado no BigQuery para este período/municípios.")

    except Exception as e:
        print(f"✗ Erro na consulta BigQuery: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RADAR-EP — Carga via BigQuery")
    parser.add_argument("--ano-inicio", type=int, default=2020)
    parser.add_argument("--db", default="radar_ep.duckdb")
    args = parser.parse_args()
    carregar_bigquery(args.ano_inicio, args.db)
