import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

print("=== Buscando tabelas de Emendas no BigQuery (Base dos Dados) ===")
query = """
    SELECT table_id, dataset_id
    FROM `basedosdados.information_schema.tables`
    WHERE table_id LIKE '%emenda%' OR table_id LIKE '%plano_acao%'
    LIMIT 20
"""
try:
    df = bd.read_sql(query, billing_project_id=project_id)
    print(df)
except Exception as e:
    # Se não tiver acesso ao information_schema, tentamos listar alguns conhecidos
    print(f"Erro ao acessar schemas: {e}")
    print("Tentando buscar na br_me_transferegov...")
    query2 = "SELECT * FROM `basedosdados.br_me_transferegov.plano_acao_especial` LIMIT 1"
    try:
        df2 = bd.read_sql(query2, billing_project_id=project_id)
        print("✓ Tabela br_me_transferegov.plano_acao_especial existe!")
    except:
        print("✗ Tabela br_me_transferegov.plano_acao_especial não encontrada.")
