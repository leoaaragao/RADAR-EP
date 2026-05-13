from src.ingestao.portal_api import buscar_emendas_municipio
import os
from dotenv import load_dotenv
load_dotenv()
emendas = buscar_emendas_municipio('3516200', 2024, os.getenv('PORTAL_TRANSPARENCIA_KEY'))
if emendas:
    e = emendas[0]
    print(f"valorEmpenhado: {e.get('valorEmpenhado')} (type: {type(e.get('valorEmpenhado'))})")
    print(f"valorLiquidado: {e.get('valorLiquidado')} (type: {type(e.get('valorLiquidado'))})")
    print(f"valorPago: {e.get('valorPago')} (type: {type(e.get('valorPago'))})")
