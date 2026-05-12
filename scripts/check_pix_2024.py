import os, sys
sys.path.append(os.getcwd())
from src.ingestao.transferegov_api import buscar_planos_acao

print("=== Transferências Especiais (PIX): Franca (3516200) / 2024 ===")
dados = buscar_planos_acao(ibges=["3516200"], ano=2024)
print(f"Planos encontrados: {len(dados)}")
if dados:
    for d in dados:
        print(f"ID: {d.get('codigo_emenda')} | Valor: {d.get('valor_emenda')} | Objeto: {d.get('objeto')}")
