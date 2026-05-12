"""
RADAR-EP — Pipeline Completo de Risco
======================================
Executa a análise de risco sobre as emendas carregadas no DuckDB
e salva os alertas gerados.

Uso:
    python scripts/run_risk_pipeline.py
    python scripts/run_risk_pipeline.py --escore-min 0.25 --limite 5000
    python scripts/run_risk_pipeline.py --sem-cnpj --sem-portal
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv()

import duckdb
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("radar_ep.pipeline")


def main():
    parser = argparse.ArgumentParser(description="RADAR-EP — Pipeline de Risco")
    parser.add_argument("--db", default=str(ROOT_DIR / "radar_ep.duckdb"))
    parser.add_argument("--escore-min", type=float, default=0.20,
                        help="Escore mínimo para salvar alerta (padrão: 0.20)")
    parser.add_argument("--limite", type=int, default=10000,
                        help="Máximo de emendas a processar (padrão: 10.000)")
    parser.add_argument("--ano-inicio", type=int, default=2020)
    parser.add_argument("--sem-cnpj", action="store_true",
                        help="Pula verificação BrasilAPI (mais rápido)")
    parser.add_argument("--sem-nlp", action="store_true",
                        help="Pula NLP de similaridade (mais rápido)")
    parser.add_argument("--sem-portal", action="store_true",
                        help="Pula verificação Portal da Transparência")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  RADAR-EP — Pipeline de Análise de Risco")
    print("  13ª SJ MPF Franca/SP | Maio/2026")
    print("═" * 60)

    if not Path(args.db).exists():
        print(f"\n  ✗ Banco não encontrado: {args.db}")
        print("  Execute primeiro: python scripts/setup_db.py")
        sys.exit(1)

    chave_api = os.getenv("PORTAL_TRANSPARENCIA_KEY")

    # ── Carregar emendas ───────────────────────────────────────
    print(f"\n  Carregando emendas (a partir de {args.ano_inicio}, limite {args.limite:,})...")
    con = duckdb.connect(args.db, read_only=True)

    try:
        df = con.execute(f"""
            SELECT * FROM emendas_parlamentares
            WHERE TRY_CAST("Ano da Emenda" AS INTEGER) >= {args.ano_inicio}
              AND "Código Município IBGE" IN (
                '3516200','3503000','3508207','3513207','3517703',
                '3520103','3521309','3523701','3524105','3525409',
                '3536307','3537008','3542701','3543105','3543600',
                '3549409','3549508'
              )
            LIMIT {args.limite}
        """).df()
    except Exception as e:
        print(f"\n  ✗ Erro ao carregar emendas: {e}")
        print("  Verifique se os CSVs foram carregados com setup_db.py")
        con.close()
        sys.exit(1)

    con.close()
    print(f"  ✓ {len(df):,} emendas carregadas\n")

    if df.empty:
        print("  ✗ Nenhuma emenda encontrada para os filtros aplicados.")
        sys.exit(0)

    # ── Executar motor de risco ────────────────────────────────
    from src.risco.risk_engine import processar_lote
    from src.risco.alerta_writer import salvar_lote_alertas

    print(f"  Configurações:")
    print(f"    Verificação CNPJ (BrasilAPI) : {'✗ desativada' if args.sem_cnpj else '✓ ativada'}")
    print(f"    Análise NLP (Sentence-Trans) : {'✗ desativada' if args.sem_nlp else '✓ ativada'}")
    print(f"    Portal da Transparência      : {'✗ desativada' if args.sem_portal else '✓ ativada'}")
    print(f"    Escore mínimo para alerta    : {args.escore_min}")
    print()

    inicio = time.time()
    print("  Processando indicadores de risco...")

    df_resultados = processar_lote(
        df,
        db_path=args.db,
        chave_api=chave_api,
        avaliar_cnpj=not args.sem_cnpj,
        avaliar_nlp=not args.sem_nlp,
        avaliar_portal=not args.sem_portal,
        escore_minimo=args.escore_min,
    )

    elapsed = time.time() - inicio
    print(f"  ✓ Processamento concluído em {elapsed:.1f}s")
    print(f"  ✓ {len(df_resultados):,} registros com escore >= {args.escore_min}")

    if df_resultados.empty:
        print("\n  Nenhum alerta gerado. Tente reduzir --escore-min")
        return

    # ── Distribuição de escores ────────────────────────────────
    altos   = len(df_resultados[df_resultados["escore"] >= 0.6])
    medios  = len(df_resultados[(df_resultados["escore"] >= 0.35) & (df_resultados["escore"] < 0.6)])
    baixos  = len(df_resultados[df_resultados["escore"] < 0.35])

    print(f"\n  Distribuição de risco:")
    print(f"    🔴 Alto (≥ 0.60)    : {altos:>6,}")
    print(f"    🟡 Médio (0.35-0.60): {medios:>6,}")
    print(f"    🟢 Baixo (< 0.35)   : {baixos:>6,}")

    # ── Salvar alertas ─────────────────────────────────────────
    print(f"\n  Salvando alertas no banco...")
    n_salvos = salvar_lote_alertas(df_resultados, args.db, args.escore_min)
    print(f"  ✓ {n_salvos} alertas salvos em radar_ep.duckdb\n")

    print("  Próximos passos:")
    print("    streamlit run src/dashboard.py   → abrir dashboard")
    print("    uvicorn src.api:app --port 8000  → iniciar API REST\n")


if __name__ == "__main__":
    main()
