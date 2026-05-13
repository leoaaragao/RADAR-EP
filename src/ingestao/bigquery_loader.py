"""
RADAR-EP — Carga via Base dos Dados (BigQuery)
===============================================
Fase 1.3 — carga histórica da tabela br_cgu_emendas_parlamentares.microdados.

Tabela BD: basedosdados.br_cgu_emendas_parlamentares.microdados
Cobertura: 2013-2026 | Organização: CGU | Atualização: a cada 15 dias
Última atualização verificada: 2026-05-12

Requer autenticação OAuth Google com acesso ao projeto nice-stack-440319-c6.
Na primeira execução, abre o browser para login.

Instalação: pip install basedosdados

Uso:
    python src/ingestao/bigquery_loader.py
    python src/ingestao/bigquery_loader.py --ano-inicio 2020
"""

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()

# IBGEs dos 17 municípios — sincronizados com setup_db.py (fonte autoritativa)
IBGES_FRANCA = (
    "3516200",  # Franca
    "3549409",  # São Joaquim da Barra
    "3524105",  # Ituverava
    "3520103",  # Igarapava
    "3517703",  # Guará
    "3521309",  # Ipuã
    "3537008",  # Pedregulho
    "3536307",  # Patrocínio Paulista
    "3549508",  # São José da Bela Vista
    "3513207",  # Cristais Paulista
    "3542701",  # Restinga
    "3523701",  # Itirapuã
    "3503000",  # Aramina
    "3543105",  # Ribeirão Corrente
    "3508207",  # Buritizal
    "3543600",  # Rifaina
    "3525409",  # Jeriquara
)

# Mapeamento completo: colunas BigQuery → colunas internas RADAR-EP
# Fonte: basedosdados.org/dataset/br_cgu_emendas_parlamentares (Microdados)
COLUNA_MAPPING = {
    "ano_emenda":                   "Ano da Emenda",
    "id_emenda":                    "Código da Emenda",
    "numero_emenda":                "Número da Emenda",
    "tipo_emenda":                  "Tipo de Emenda",
    "id_autor_emenda":              "Código do Autor da Emenda",
    "nome_autor_emenda":            "Nome do Autor da Emenda",
    "localidade":                   "Localidade do Gasto",
    "sigla_uf_gasto":               "UF do Gasto",
    "id_municipio_gasto":           "Código Município IBGE",
    "id_funcao":                    "Código Função",
    "nome_funcao":                  "Função",
    "id_subfuncao":                 "Código Subfunção",
    "nome_subfuncao":               "Subfunção",
    "id_programa":                  "Código Programa",
    "nome_programa":                "Programa",
    "id_acao":                      "Código Ação",
    "nome_acao":                    "Ação",
    "id_plano_orcamentario":        "Código Plano Orçamentário",
    "nome_plano_orcamentario":      "Plano Orçamentário",
    "valor_empenhado":              "Valor Empenhado",
    "valor_liquidado":              "Valor Liquidado",
    "valor_pago":                   "Valor Pago",
    "valor_resto_pagar_inscrito":   "Valor Restos A Pagar Inscritos",
    "valor_resto_pagar_cancelado":  "Valor Restos A Pagar Cancelados",
    "valor_resto_pagar_pagos":      "Valor Restos A Pagar Pagos",
}

COLUNAS_VALOR = [
    "Valor Empenhado",
    "Valor Liquidado",
    "Valor Pago",
    "Valor Restos A Pagar Inscritos",
    "Valor Restos A Pagar Cancelados",
    "Valor Restos A Pagar Pagos",
]


def carregar_bigquery(ano_inicio: int = 2020, db_path: str = "radar_ep.duckdb"):
    """
    Carrega dados históricos do BigQuery e salva no DuckDB.

    Busca a tabela completa de microdados de emendas parlamentares (CGU/BD)
    filtrando pelos 17 municípios da 13ª SJ Franca/SP e pelo período solicitado.
    """
    try:
        import basedosdados as bd
        import duckdb
    except ImportError as e:
        print(f"Dependência não instalada: {e}")
        print("Execute: pip install basedosdados duckdb")
        sys.exit(1)

    project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
    ibge_str = "','".join(IBGES_FRANCA)

    print(f"\nConsultando BigQuery — Base dos Dados")
    print(f"  Tabela : basedosdados.br_cgu_emendas_parlamentares.microdados")
    print(f"  Projeto: {project_id}")
    print(f"  Período: {ano_inicio} a 2026")
    print(f"  Municípios: {len(IBGES_FRANCA)} (13ª SJ Franca/SP)")
    print("\n  Se for a primeira execução, o browser será aberto para autenticação OAuth.\n")

    colunas_select = ",\n            ".join(COLUNA_MAPPING.keys())

    query = f"""
        SELECT
            {colunas_select}
        FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
        WHERE id_municipio_gasto IN ('{ibge_str}')
          AND ano_emenda >= {ano_inicio}
    """

    try:
        df = bd.read_sql(query, billing_project_id=project_id)
        print(f"  ✓ BigQuery retornou {len(df):,} registros")

        if len(df) == 0:
            print("  ! Nenhum dado encontrado para este período/municípios.")
            return

        # Renomear colunas para padrão interno
        df = df.rename(columns=COLUNA_MAPPING)

        # Garantir ano como string (compatibilidade com CSV)
        df["Ano da Emenda"] = df["Ano da Emenda"].astype(str)

        # Converter valores monetários para string no formato brasileiro
        # (compatível com a view v_emendas_valores que usa TRY_CAST + REPLACE)
        for col in COLUNAS_VALOR:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if x is not None and str(x) != "nan"
                    else "0,00"
                )

        con = duckdb.connect(db_path)

        tab_exists = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'emendas_parlamentares'"
        ).fetchone()[0]

        if tab_exists:
            anos_carregados = df["Ano da Emenda"].unique().tolist()
            anos_str = "','".join(anos_carregados)
            con.execute(
                f"DELETE FROM emendas_parlamentares "
                f"WHERE \"Ano da Emenda\" IN ('{anos_str}') "
                f"AND \"Código Município IBGE\" IN ('{ibge_str}')"
            )
            con.execute("INSERT INTO emendas_parlamentares SELECT * FROM df")
        else:
            con.execute("CREATE TABLE emendas_parlamentares AS SELECT * FROM df")

        con.close()
        print(f"  ✓ Dados integrados na tabela 'emendas_parlamentares' ({len(df):,} linhas)")

    except Exception as e:
        print(f"  ✗ Erro na consulta BigQuery: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RADAR-EP — Carga via BigQuery (Base dos Dados)")
    parser.add_argument("--ano-inicio", type=int, default=2020,
                        help="Ano de início da carga (padrão: 2020)")
    parser.add_argument("--db", default=str(ROOT_DIR / "radar_ep.duckdb"),
                        help="Caminho para o banco DuckDB")
    args = parser.parse_args()
    carregar_bigquery(args.ano_inicio, args.db)
