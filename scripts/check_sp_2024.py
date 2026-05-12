import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Cidades de SP com mais emendas em 2024 (BigQuery) ===")
query = """
    SELECT localidade, id_municipio_gasto, COUNT(*) as n
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE sigla_uf_gasto = 'SP' AND ano_emenda = 2024
    GROUP BY 1, 2
    ORDER BY n DESC
    LIMIT 20
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df)
except Exception as e:
    print(f"Erro: {e}")
