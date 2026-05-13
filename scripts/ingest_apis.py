import os
import sys
import logging
from pathlib import Path
import pandas as pd
import duckdb
from dotenv import load_dotenv

# Configurações de importação
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.ingestao.portal_api import buscar_emendas_municipio
from src.ingestao.camara_api import buscar_deputados, cruzar_dados_autor

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = str(ROOT_DIR / "radar_ep.duckdb")

# Lista de IBGEs de Franca (padrão)
IBGES_FRANCA = [
    '3516200','3503000','3508207','3513207','3517703','3520103','3521309',
    '3523701','3524105','3525409','3536307','3537008','3542701','3543105',
    '3543600','3549409','3549508'
]

def ensure_columns_exist(con: duckdb.DuckDBPyConnection):
    """Garante que as novas colunas existam na tabela emendas_parlamentares"""
    cols_to_add = {
        "Partido do Autor": "VARCHAR",
        "UF do Autor": "VARCHAR",
        "Foto do Autor": "VARCHAR"
    }
    
    existing_cols = con.execute("DESCRIBE emendas_parlamentares").df()['column_name'].tolist()
    
    for col_name, col_type in cols_to_add.items():
        if col_name not in existing_cols:
            logger.info(f"Adicionando nova coluna {col_name} ao banco...")
            con.execute(f'ALTER TABLE emendas_parlamentares ADD COLUMN "{col_name}" {col_type}')

def ingest_from_apis(anos=[2024, 2025, 2026], ibges=IBGES_FRANCA):
    chave_cgu = os.getenv("PORTAL_TRANSPARENCIA_KEY")
    if not chave_cgu:
        logger.error("CHAVE NÃO ENCONTRADA! Adicione PORTAL_TRANSPARENCIA_KEY no arquivo .env")
        return

    logger.info("Buscando metadados de deputados na Câmara...")
    deputados_map = buscar_deputados()

    todas_emendas = []
    
    for ano in anos:
        for ibge in ibges:
            logger.info(f"Buscando emendas para o IBGE {ibge} no ano {ano}...")
            emendas = buscar_emendas_municipio(ibge, ano, chave_cgu)
            
            for e in emendas:
                # Cruzamento com Câmara
                nome_autor = e.get("nomeAutor", "")
                dados_camara = cruzar_dados_autor(nome_autor, deputados_map)
                
                # Função para limpar valores monetários que vem como string '0,00'
                def clean_money(val):
                    if isinstance(val, str):
                        return float(val.replace('.', '').replace(',', '.'))
                    return float(val or 0.0)
                
                # Mapeamento do JSON da CGU para a nossa tabela
                registro = {
                    "Código da Emenda": e.get("codigoEmenda"),
                    "Ano da Emenda": e.get("ano"),
                    "Tipo de Emenda": e.get("tipoEmenda"),
                    "Código do Autor da Emenda": e.get("autor"),
                    "Nome do Autor da Emenda": nome_autor,
                    "Número da emenda": e.get("numeroEmenda"),
                    "Localidade de aplicação do recurso": e.get("localidadeDoGasto"),
                    "Código Município IBGE": e.get("municipio", {}).get("codigoIBGE", ibge),
                    "Município": e.get("municipio", {}).get("nomeIBGE", ""),
                    "Código UF IBGE": None,
                    "UF": e.get("municipio", {}).get("uf", {}).get("sigla", ""),
                    "Região": e.get("municipio", {}).get("nomeRegiao", ""),
                    "Código Função": "",
                    "Nome Função": str(e.get("funcao", "")),
                    "Código Subfunção": "",
                    "Nome Subfunção": str(e.get("subfuncao", "")),
                    "Código Programa": "",
                    "Nome Programa": str(e.get("programa", "")),
                    "Código Ação": "",
                    "Nome Ação": str(e.get("acao", "")),
                    "Código Plano Orçamentário": None,
                    "Nome Plano Orçamentário": "",
                    "Valor Empenhado": clean_money(e.get("valorEmpenhado")),
                    "Valor Liquidado": clean_money(e.get("valorLiquidado")),
                    "Valor Pago": clean_money(e.get("valorPago")),
                    "Valor Restos A Pagar Inscritos": clean_money(e.get("valorRestosAPagarInscritos")),
                    "Valor Restos A Pagar Cancelados": clean_money(e.get("valorRestosAPagarCancelados")),
                    "Valor Restos A Pagar Pagos": clean_money(e.get("valorRestosAPagarPagos")),
                    
                    # Novos campos
                    "Partido do Autor": dados_camara["partido"],
                    "UF do Autor": dados_camara["uf_autor"],
                    "Foto do Autor": None  # Removido a pedido do usuário
                }
                todas_emendas.append(registro)

    if not todas_emendas:
        logger.info("Nenhuma emenda nova encontrada.")
        return

    # Gravar no DuckDB
    logger.info(f"Salvando {len(todas_emendas)} registros no banco de dados...")
    df_novas = pd.DataFrame(todas_emendas)
    
    con = duckdb.connect(DB_PATH)
    try:
        ensure_columns_exist(con)
        con.register('df_novas', df_novas)
        
        # Fazendo um UPSERT (Delete + Insert para garantir dados de pagamento atualizados)
        con.execute("""
            DELETE FROM emendas_parlamentares 
            WHERE "Código da Emenda" IN (SELECT "Código da Emenda" FROM df_novas)
        """)
        
        con.execute("""
            INSERT INTO emendas_parlamentares 
            SELECT * FROM df_novas
        """)
        
        logger.info("Banco atualizado com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao salvar no banco: {e}")
    finally:
        con.close()

if __name__ == "__main__":
    logger.info("Iniciando motor de ingestão via APIs...")
    # Executa por padrão para os últimos 3 anos para a região de Franca.
    ingest_from_apis(anos=[2024, 2025, 2026], ibges=IBGES_FRANCA)
