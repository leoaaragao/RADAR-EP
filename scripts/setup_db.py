"""
RADAR-EP — Setup do Banco de Dados DuckDB
==========================================
Fase 1.2 do plano de implementação.

Cria o banco radar_ep.duckdb e carrega os três CSVs locais:
  - EmendasParlamentares.csv
  - EmendasParlamentares_Convenios.csv
  - EmendasParlamentares_PorFavorecido.csv

Uso:
    python scripts/setup_db.py
    python scripts/setup_db.py --data-dir /caminho/para/csvs
    python scripts/setup_db.py --db /caminho/para/radar_ep.duckdb
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import duckdb
from dotenv import load_dotenv

load_dotenv()

# ── Caminhos padrão ────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT_DIR / os.getenv("DUCKDB_PATH", "radar_ep.duckdb")
DEFAULT_DATA = ROOT_DIR / os.getenv("DATA_DIR", "data")

CSV_FILES = {
    "emendas_parlamentares": "EmendasParlamentares.csv",
    "convenios": "EmendasParlamentares_Convenios.csv",
    "por_favorecido": "EmendasParlamentares_PorFavorecido.csv",
}


def criar_tabela_municipios(con: duckdb.DuckDBPyConnection) -> None:
    """Cria e popula a tabela dos 17 municípios monitorados."""
    con.execute("DROP TABLE IF EXISTS municipios_franca")
    con.execute("""
        CREATE TABLE municipios_franca (
            nome       VARCHAR,
            ibge       VARCHAR(7),
            populacao  INTEGER,
            porte      VARCHAR(1),  -- G=Grande, M=Médio, P=Pequeno
            lat        DOUBLE,
            lon        DOUBLE
        )
    """)
    municipios = [
        ("Franca",                  "3516200", 365494, "G", -20.539, -47.401),
        ("São Joaquim da Barra",    "3549409",  49885, "M", -20.578, -47.853),
        ("Ituverava",               "3524105",  38413, "M", -20.339, -47.776),
        ("Igarapava",               "3520103",  26696, "M", -20.035, -47.754),
        ("Guará",                   "3517703",  18748, "P", -20.426, -48.022),
        ("Ipuã",                    "3521309",  15900, "P", -20.444, -48.013),
        ("Pedregulho",              "3537008",  15600, "P", -20.251, -47.479),
        ("Patrocínio Paulista",     "3536307",  14529, "P", -20.636, -47.277),
        ("São José da Bela Vista",  "3549508",   8895, "P", -20.594, -47.621),
        ("Cristais Paulista",       "3513207",   8200, "P", -20.397, -47.419),
        ("Restinga",                "3542701",   7504, "P", -20.537, -47.593),
        ("Itirapuã",                "3523701",   6453, "P", -20.131, -47.358),
        ("Aramina",                 "3503000",   5535, "P", -20.102, -47.703),
        ("Ribeirão Corrente",       "3543105",   4682, "P", -20.241, -47.526),
        ("Buritizal",               "3508207",   4458, "P", -20.200, -47.626),
        ("Rifaina",                 "3543600",   4179, "P", -20.081, -47.418),
        ("Jeriquara",               "3525409",   4000, "P", -20.316, -47.590),
    ]
    con.executemany(
        "INSERT INTO municipios_franca VALUES (?, ?, ?, ?, ?, ?)", municipios
    )
    print(f"  ✓ municipios_franca: {len(municipios)} registros")


def criar_tabela_alertas(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela de alertas gerados pelo motor de risco."""
    con.execute("DROP TABLE IF EXISTS alertas")
    con.execute("""
        CREATE TABLE alertas (
            id                         INTEGER PRIMARY KEY,
            codigo_emenda              VARCHAR,
            municipio                  VARCHAR,
            ibge                       VARCHAR(7),
            parlamentar                VARCHAR,
            codigo_parlamentar         VARCHAR,
            tipo_emenda                VARCHAR,
            ano_emenda                 INTEGER,
            tipo_alerta                VARCHAR,
            escore                     DECIMAL(5, 4),
            descricao                  TEXT,
            indicadores_ativados       VARCHAR,    -- JSON serializado
            requer_confirmacao_humana  BOOLEAN DEFAULT TRUE,
            valor_emenda               DOUBLE,
            data_geracao               TIMESTAMP DEFAULT current_timestamp,
            status                     VARCHAR DEFAULT 'aberto',
            -- status: aberto | verificando | falso_positivo | encaminhado
            classificado_por           VARCHAR,
            data_classificacao         TIMESTAMP,
            observacoes                TEXT
        )
    """)
    print("  ✓ alertas: tabela criada (vazia)")


def criar_tabela_cnpj_cache(con: duckdb.DuckDBPyConnection) -> None:
    """Cache de consultas CNPJ para evitar chamadas repetidas à BrasilAPI."""
    con.execute("DROP TABLE IF EXISTS cnpj_cache")
    con.execute("""
        CREATE TABLE cnpj_cache (
            cnpj              VARCHAR(14) PRIMARY KEY,
            razao_social      VARCHAR,
            situacao          VARCHAR,
            data_abertura     DATE,
            idade_meses       DOUBLE,
            flag_jovem        BOOLEAN,
            cnaes             VARCHAR,   -- JSON serializado
            socios            VARCHAR,   -- JSON serializado
            data_consulta     TIMESTAMP DEFAULT current_timestamp,
            erro              VARCHAR    -- NULL se OK
        )
    """)
    print("  ✓ cnpj_cache: tabela criada (vazia)")


def criar_tabela_sancoes(con: duckdb.DuckDBPyConnection) -> None:
    """Tabela para sanções CEIS/CNEP (carregada do CSV mensal da CGU)."""
    con.execute("DROP TABLE IF EXISTS sancoes_ceis")
    con.execute("""
        CREATE TABLE sancoes_ceis (
            cnpj_cpf          VARCHAR,
            razao_social      VARCHAR,
            tipo_pessoa       VARCHAR,
            tipo_sancao       VARCHAR,
            data_inicio       DATE,
            data_fim          DATE,
            orgao_sancionador VARCHAR,
            uf_orgao          VARCHAR,
            data_carga        TIMESTAMP DEFAULT current_timestamp
        )
    """)
    print("  ✓ sancoes_ceis: tabela criada (vazia — carregar CSV do TCU)")


def carregar_csv(
    con: duckdb.DuckDBPyConnection,
    tabela: str,
    caminho_csv: Path,
    descricao: str,
) -> int:
    """
    Carrega um CSV cp1252 no DuckDB via pandas (compatível com DuckDB 1.5+).
    DuckDB 1.5 removeu o parâmetro encoding do read_csv.
    """
    import pandas as pd

    print(f"  Carregando {descricao}...")
    inicio = time.time()

    # Pandas lida nativamente com cp1252
    df = pd.read_csv(
        caminho_csv,
        sep=";",
        encoding="cp1252",
        low_memory=False,
        on_bad_lines="skip",
        quotechar='"',
    )

    # --- NORMALIZAÇÃO DE COLUNAS ---
    # Remover espaços, aspas extras e corrigir encoding comum
    df.columns = [
        col.replace('"', '').strip()
        .replace('Cdigo', 'Código')
        .replace('Municpio', 'Município')
        .replace('Aplicao', 'Aplicação')
        .replace('Funo', 'Função')
        .replace('Subfuno', 'Subfunção')
        .replace('Ao', 'Ação')
        .replace('Oramentrio', 'Orçamentário')
        .replace('Nmero', 'Número')
        .replace('Regio', 'Região')
        for col in df.columns
    ]
    
    # Mapeamentos específicos para garantir compatibilidade
    name_map = {
        'Cdigo Municpio IBGE': 'Código Município IBGE',
        'Municpio': 'Município',
        'Cdigo da Emenda': 'Código da Emenda',
        'Ano da Emenda': 'Ano da Emenda'
    }
    df = df.rename(columns=name_map)

    con.execute(f"DROP TABLE IF EXISTS {tabela}")
    # Registra o DataFrame e cria tabela
    con.register("_df_tmp", df)
    con.execute(f"CREATE TABLE {tabela} AS SELECT * FROM _df_tmp")
    con.unregister("_df_tmp")

    count = len(df)
    cols  = len(df.columns)
    elapsed = time.time() - inicio
    print(f"    OK {tabela}: {count:,} linhas x {cols} colunas ({elapsed:.1f}s)")
    return count


def criar_view_valores_normalizados(con: duckdb.DuckDBPyConnection) -> None:
    """
    View que normaliza os valores monetários brasileiros
    (ponto como separador de milhar, vírgula como decimal).
    """
    con.execute("DROP VIEW IF EXISTS v_emendas_valores")
    con.execute("""
        CREATE VIEW v_emendas_valores AS
        SELECT
            *,
            TRY_CAST(
                REPLACE(REPLACE("Valor Empenhado",      '.', ''), ',', '.') AS DOUBLE
            ) AS val_empenhado,
            TRY_CAST(
                REPLACE(REPLACE("Valor Liquidado",      '.', ''), ',', '.') AS DOUBLE
            ) AS val_liquidado,
            TRY_CAST(
                REPLACE(REPLACE("Valor Pago",           '.', ''), ',', '.') AS DOUBLE
            ) AS val_pago,
            TRY_CAST(
                REPLACE(REPLACE("Valor Restos A Pagar Inscritos",  '.', ''), ',', '.') AS DOUBLE
            ) AS val_restos_inscrito,
            TRY_CAST(
                REPLACE(REPLACE("Valor Restos A Pagar Cancelados", '.', ''), ',', '.') AS DOUBLE
            ) AS val_restos_cancelado,
            TRY_CAST(
                REPLACE(REPLACE("Valor Restos A Pagar Pagos",      '.', ''), ',', '.') AS DOUBLE
            ) AS val_restos_pagos
        FROM emendas_parlamentares
    """)
    print("  ✓ v_emendas_valores: view criada")


def criar_view_favorecido_normalizada(con: duckdb.DuckDBPyConnection) -> None:
    """View com valores normalizados do arquivo de favorecidos."""
    con.execute("DROP VIEW IF EXISTS v_favorecido_valores")
    con.execute("""
        CREATE VIEW v_favorecido_valores AS
        SELECT
            *,
            TRY_CAST(
                REPLACE(REPLACE("Valor Recebido", '.', ''), ',', '.') AS DOUBLE
            ) AS val_recebido,
            -- Extrai CNPJ limpo (apenas dígitos)
            REGEXP_REPLACE("Código do Favorecido", '[^0-9]', '') AS cnpj_limpo,
            -- Extrai ano e mês do campo "Ano/Mês" (formato 202605)
            CAST(LEFT(CAST("Ano/Mês" AS VARCHAR), 4) AS INTEGER) AS ano_ref,
            CAST(RIGHT(CAST("Ano/Mês" AS VARCHAR), 2) AS INTEGER) AS mes_ref
        FROM por_favorecido
    """)
    print("  ✓ v_favorecido_valores: view criada")


def imprimir_sumario(con: duckdb.DuckDBPyConnection) -> None:
    """Imprime um resumo estatístico do banco carregado."""
    print("\n" + "═" * 60)
    print("  SUMÁRIO DO BANCO RADAR-EP")
    print("═" * 60)

    tabelas = con.execute("""
        SELECT table_name, estimated_size
        FROM duckdb_tables()
        ORDER BY table_name
    """).fetchall()

    for nome, size in tabelas:
        count = con.execute(f"SELECT COUNT(*) FROM {nome}").fetchone()[0]
        print(f"  {nome:<35} {count:>10,} linhas")

    print("─" * 60)

    # Top municípios por valor empenhado
    try:
        top = con.execute("""
            SELECT "Município", 
                   SUM(TRY_CAST(REPLACE(REPLACE("Valor Empenhado",'.',''),',','.') AS DOUBLE)) AS total
            FROM emendas_parlamentares
            GROUP BY "Município"
            ORDER BY total DESC
            LIMIT 5
        """).fetchall()
        print("\n  Top 5 municípios por valor empenhado:")
        for mun, val in top:
            print(f"    {str(mun):<30} R$ {val:>14,.2f}")
    except Exception:
        pass

    print("═" * 60)


def main():
    parser = argparse.ArgumentParser(description="RADAR-EP — Setup do banco DuckDB")
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Caminho para o arquivo .duckdb (padrão: {DEFAULT_DB})"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA,
        help=f"Pasta com os arquivos CSV (padrão: {DEFAULT_DATA})"
    )
    parser.add_argument(
        "--skip-csv", action="store_true",
        help="Pula a carga dos CSVs (útil se já foram carregados)"
    )
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  RADAR-EP — Configuração do Banco de Dados")
    print("  13ª SJ MPF Franca/SP | Maio/2026")
    print("═" * 60)
    print(f"\n  Banco  : {args.db}")
    print(f"  Dados  : {args.data_dir}\n")

    # Verificar se a pasta de dados existe
    if not args.skip_csv and not args.data_dir.exists():
        print(f"  ⚠ AVISO: Pasta '{args.data_dir}' não encontrada.")
        print(f"  Crie a pasta e coloque os CSVs lá, ou use --data-dir para especificar o caminho.")
        print(f"  Prosseguindo apenas com tabelas de estrutura...\n")
        args.skip_csv = True

    # Conectar ao banco (cria se não existir)
    con = duckdb.connect(str(args.db))
    print("  Criando tabelas de estrutura...")

    criar_tabela_municipios(con)
    criar_tabela_alertas(con)
    criar_tabela_cnpj_cache(con)
    criar_tabela_sancoes(con)

    if not args.skip_csv:
        print("\n  Carregando CSVs...")
        total_linhas = 0
        for tabela, arquivo in CSV_FILES.items():
            caminho = args.data_dir / arquivo
            if caminho.exists():
                total_linhas += carregar_csv(con, tabela, caminho, arquivo)
            else:
                print(f"  ⚠ {arquivo} não encontrado em {args.data_dir} — pulando")

        print("\n  Criando views normalizadas...")
        try:
            criar_view_valores_normalizados(con)
        except Exception as e:
            print(f"  ⚠ v_emendas_valores: {e}")
        try:
            criar_view_favorecido_normalizada(con)
        except Exception as e:
            print(f"  ⚠ v_favorecido_valores: {e}")

        imprimir_sumario(con)
    else:
        print("\n  ⚠ Carga de CSVs pulada (--skip-csv ou pasta não encontrada)")
        print("  Adicione os CSVs em data/ e rode novamente sem --skip-csv")

    con.close()
    print(f"\n  ✓ Banco criado em: {args.db}")
    print("  Próximo passo: python scripts/run_risk_pipeline.py\n")


if __name__ == "__main__":
    main()
