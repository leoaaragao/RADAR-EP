import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Anos disponíveis para Franca (3516200) no BigQuery ===")
query = """
    SELECT ano_emenda, COUNT(*) as n
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE id_municipio_gasto = '3516200'
    GROUP BY 1
    ORDER BY 1 DESC
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df)
except Exception as e:
    print(f"Erro: {e}")
