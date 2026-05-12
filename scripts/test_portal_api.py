import httpx
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("PORTAL_TRANSPARENCIA_KEY")
headers = {"chave-api-dados": key}

print("=== Consultando Portal da Transparência: Franca (3516200) / 2024 ===")
r = httpx.get(
    "https://api.portaldatransparencia.gov.br/api-de-dados/emendas",
    headers=headers,
    params={"codigoIbge": "3516200", "anoExercicio": 2024},
    timeout=20
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    dados = r.json()
    print(f"Registros encontrados: {len(dados)}")
    if dados:
        print(dados[0])
else:
    print(r.text)
