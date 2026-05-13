import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def buscar_deputados() -> dict:
    """
    Busca todos os deputados ativos e inativos na API da Câmara.
    Retorna um dicionário mapeando o nome (em maiúsculas) para seus dados (partido, UF, foto).
    """
    url = f"{BASE_URL}/deputados"
    deputados_map = {}
    
    try:
        # Busca sem paginação estrita se possível, mas dados abertos geralmente pede paginação.
        # Vamos usar um limite alto (ordem alfabética)
        params = {"ordem": "ASC", "ordenarPor": "nome", "itens": 1000}
        
        while url:
            r = httpx.get(url, params=params, timeout=20)
            if r.status_code != 200:
                logger.warning(f"Erro na API da Câmara: HTTP {r.status_code}")
                break
                
            dados = r.json()
            for dep in dados.get("dados", []):
                nome = dep.get("nome").upper()
                deputados_map[nome] = {
                    "id_camara": dep.get("id"),
                    "partido": dep.get("siglaPartido"),
                    "uf_autor": dep.get("siglaUf"),
                    "foto": dep.get("urlFoto")
                }
            
            # Checar paginação
            links = dados.get("links", [])
            next_link = next((link["href"] for link in links if link["rel"] == "next"), None)
            
            if next_link:
                url = next_link
                params = {} # params já estão na URL do link
            else:
                break
                
        logger.info(f"Dados de {len(deputados_map)} deputados carregados com sucesso da API da Câmara.")
        return deputados_map
        
    except Exception as e:
        logger.error(f"Erro ao acessar API da Câmara: {e}")
        return {}

def cruzar_dados_autor(nome_autor: str, deputados_map: dict) -> dict:
    """
    Tenta encontrar os dados do parlamentar pelo nome.
    Caso seja bancada ou comissão, retorna nulo.
    """
    if not nome_autor:
        return {"partido": None, "uf_autor": None, "foto": None}
        
    nome_upper = nome_autor.upper().strip()
    
    # 1. Tenta correspondência exata
    if nome_upper in deputados_map:
        return deputados_map[nome_upper]
        
    # 2. Tenta correspondência parcial (ex: nome na base do executivo pode ser incompleto)
    # Apenas se for uma emenda individual
    for nome_camara, dados in deputados_map.items():
        if nome_upper in nome_camara or nome_camara in nome_upper:
            return dados
            
    return {"partido": None, "uf_autor": None, "foto": None}
