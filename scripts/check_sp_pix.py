import os, sys
sys.path.append(os.getcwd())
from src.ingestao.transferegov_api import buscar_planos_acao

print("=== Transferências Especiais (PIX): SP / 2024 ===")
# Vou buscar sem filtro de IBGE, mas a API requer um filtro.
# Vou tentar buscar por UF se possível, mas minha função usa IBGEs.
# Vou usar o IBGE de São Paulo (3550308) como teste.
dados = buscar_planos_acao(ibges=["3550308"], ano=2024)
print(f"Planos encontrados em SP (Capital) 2024: {len(dados)}")
if dados:
    print(dados[0])
