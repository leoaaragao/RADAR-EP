import httpx

print("=== Buscando PIX em SP / 2024 (Global) ===")
# Vou tentar buscar os primeiros 1000 planos de 2024 em SP
r = httpx.get(
    "https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_de_acao",
    params={"sigla_uf": "eq.SP", "ano": "eq.2024", "limit": "1000"},
    timeout=30
)
if r.status_code == 200:
    dados = r.json()
    print(f"Total em SP 2024: {len(dados)}")
    franca = [d for d in dados if "FRANCA" in str(d).upper()]
    print(f"Encontrados com texto 'FRANCA': {len(franca)}")
    if franca:
        for f in franca:
            print(f)
else:
    print(f"Erro {r.status_code}: {r.text}")
