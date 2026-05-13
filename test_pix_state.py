from src.ingestao.portal_api import buscar_emendas_municipio
import os
from dotenv import load_dotenv
load_dotenv()
# Testar IBGE 35 (Estado de SP)
print("Buscando IBGE 35 (SP) para 2024...")
emendas = buscar_emendas_municipio('35', 2024, os.getenv('PORTAL_TRANSPARENCIA_KEY'))
print(f"Total emendas no estado: {len(emendas)}")
for e in emendas:
    if 'Especiais' in e.get('tipoEmenda', ''):
        print(f"ACHEI PIX! Local: {e.get('localidadeDoGasto')} - Valor: {e.get('valorEmpenhado')}")
        if 'FRANCA' in e.get('localidadeDoGasto', '').upper():
            print(">>> PIX EM FRANCA ENCONTRADA NO IBGE DO ESTADO!")
