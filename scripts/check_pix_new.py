import httpx

print("=== Buscando QUALQUER PIX em SP / 2024 (Novo Endpoint) ===")
r = httpx.get(
    "https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial",
    params={"sigla_uf": "eq.SP", "ano": "eq.2024", "limit": "5"},
    timeout=30
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    dados = r.json()
    print(f"Total encontrados: {len(dados)}")
    if dados:
        print(dados[0])
else:
    print(r.text)
