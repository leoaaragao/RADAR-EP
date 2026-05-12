import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

query = "SELECT * FROM `basedosdados.br_cgu_emendas_parlamentares.microdados` LIMIT 1"
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print("=== Colunas no BigQuery ===")
    print(df.columns.tolist())
except Exception as e:
    print(f"Erro: {e}")
