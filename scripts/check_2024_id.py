import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Buscando emendas que começam com 2024 no BigQuery ===")
query = """
    SELECT id_emenda, ano_emenda, nome_autor_emenda, id_municipio_gasto
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE id_emenda LIKE '2024%'
    LIMIT 10
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df)
except Exception as e:
    print(f"Erro: {e}")
