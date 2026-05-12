import basedosdados as bd
import os
from dotenv import load_dotenv
load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID", "nice-stack-440319-c6")
bd.config.project_id = project_id

mun_names = ["FRANCA", "SÃO JOAQUIM DA BARRA", "ITUVERAVA", "IGARAPAVA", "GUARÁ", "IPUÃ", "PEDREGULHO", "PATROCÍNIO PAULISTA", "SÃO JOSÉ DA BELA VISTA", "CRISTAIS PAULISTA", "RESTINGA", "ITIRAPUÃ", "ARAMINA", "RIBEIRÃO CORRENTE", "BURITIZAL", "RIFAINA", "JERIQUARA"]
mun_filter = " OR ".join([f"localidade LIKE '%{name}%'" for name in mun_names])

query = f"""
    SELECT * FROM `basedosdados.br_cgu_emendas_parlamentares.microdados`
    WHERE ({mun_filter}) AND ano_emenda >= 2024
"""
try:
    print(f"Executando query por localidade...")
    df = bd.read_sql(query, billing_project_id=project_id)
    print(f"Encontrados: {len(df)}")
    if len(df) > 0:
        print(df[['ano_emenda', 'nome_autor_emenda', 'localidade', 'id_municipio_gasto']].head())
except Exception as e:
    print(f"Erro: {e}")
