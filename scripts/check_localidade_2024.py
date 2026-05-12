import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Verificando LOCALIDADE para emendas 2024 (BigQuery) ===")
query = """
    SELECT id_emenda, localidade, sigla_uf_gasto
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE id_emenda LIKE '2024%'
    LIMIT 20
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df)
except Exception as e:
    print(f"Erro: {e}")
