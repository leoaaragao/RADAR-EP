import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Buscando Franca 2024 no BigQuery (Diversas abordagens) ===")
# 1. Por IBGE 7 dígitos
# 2. Por IBGE 6 dígitos
# 3. Por Nome (localidade)
query = """
    SELECT ano_emenda, id_municipio_gasto, localidade, COUNT(*) as n
    FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE ano_emenda >= 2024
      AND (id_municipio_gasto LIKE '351620%' OR localidade LIKE '%FRANCA%')
    GROUP BY 1, 2, 3
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df)
except Exception as e:
    print(f"Erro: {e}")
