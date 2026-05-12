import httpx
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("PORTAL_TRANSPARENCIA_KEY")
headers = {"chave-api-dados": key}

print("=== Detalhando Emendas Portal API: Franca (3516200) / 2024 ===")
r = httpx.get(
    "https://api.portaldatransparencia.gov.br/api-de-dados/emendas",
    headers=headers,
    params={"codigoIbge": "3516200", "anoExercicio": 2024},
    timeout=20
)
if r.status_code == 200:
    dados = r.json()
    for d in dados:
        print(f"Emenda: {d['codigoEmenda']} | Ano: {d['ano']} | Autor: {d['nomeAutor']} | Empenhado: {d['valorEmpenhado']}")
else:
    print(r.text)
