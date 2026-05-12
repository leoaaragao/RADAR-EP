import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Investigando nomes de municípios de SP em 2024 (BigQuery) ===")
query = """
    SELECT localidade, id_municipio_gasto, COUNT(*) as n
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE sigla_uf_gasto = 'SP' AND ano_emenda >= 2024
    GROUP BY 1, 2
    ORDER BY n DESC
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df.head(50))
    # Procurar por Franca no DataFrame retornado
    franca = df[df['localidade'].str.contains('FRANCA', na=False, case=False)]
    print("\nBusca por FRANCA no resultado:")
    print(franca)
except Exception as e:
    print(f"Erro: {e}")
