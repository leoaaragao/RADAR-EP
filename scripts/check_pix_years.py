import os, sys
sys.path.append(os.getcwd())
from src.ingestao.transferegov_api import buscar_planos_acao

print("=== Buscando Transferências Especiais (PIX) para Franca - Todos os Anos ===")
for ano in [2022, 2023, 2024, 2025, 2026]:
    dados = buscar_planos_acao(ibges=["3516200"], ano=ano)
    print(f"Ano {ano}: {len(dados)} planos")
    if dados:
        for d in dados:
            print(f"  - {d.get('codigo_emenda')} | {d.get('objeto')}")
