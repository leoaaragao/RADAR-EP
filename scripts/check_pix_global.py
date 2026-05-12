import httpx
print("=== Listando TODAS as Transferências Especiais (PIX) / 2024 ===")
r = httpx.get(
    "https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_de_acao",
    params={"ano": "eq.2024", "limit": "10"},
    timeout=30
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    dados = r.json()
    print(f"Total: {len(dados)}")
    if dados:
        print(dados[0])
else:
    print(r.text)
