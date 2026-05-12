import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Amostra de emendas SP em 2024 ===")
query = """
    SELECT * FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE sigla_uf_gasto = 'SP' AND ano_emenda >= 2024
    LIMIT 10
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df[['ano_emenda', 'nome_autor_emenda', 'localidade', 'id_municipio_gasto']])
except Exception as e:
    print(f"Erro: {e}")
