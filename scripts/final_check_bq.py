import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Últimos registros de Franca (3516200) no BigQuery ===")
query = """
    SELECT *
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE id_municipio_gasto = '3516200'
    ORDER BY ano_emenda DESC
    LIMIT 10
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df[['ano_emenda', 'nome_autor_emenda', 'valor_empenhado']])
except Exception as e:
    print(f"Erro: {e}")
