import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Verificando o ano mais recente na tabela (BigQuery) ===")
query = "SELECT MAX(ano_emenda) as max_ano FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`"
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(f"Último ano na tabela: {df['max_ano'].iloc[0]}")
except Exception as e:
    print(f"Erro: {e}")
