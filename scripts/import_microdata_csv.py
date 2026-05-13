import pandas as pd
import duckdb
import os
import sys
from pathlib import Path
import logging
import numpy as np

# Configurações de importação
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.ingestao.camara_api import buscar_deputados, cruzar_dados_autor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'radar_ep.duckdb'
DATA_DIR = 'data/'

# Mapeamento manual para emendas que vem sem IBGE (comum em PIX)
MAP_MUNICIPIOS_SJ = {
    'FRANCA': '3516200', 'BATATAIS': '3505906', 'ARAMINA': '3503000',
    'CRISTAIS PAULISTA': '3513207', 'GUARA': '3518209', 'IGARAPAVA': '3518803',
    'IPUA': '3521309', 'ITIRAPUA': '3523701', 'ITUVERAVA': '3524105',
    'JERIQUARA': '3525409', 'NUPORANGA': '3533403', 'ORLANDIA': '3534302',
    'PATROCINIO PAULISTA': '3536307', 'RESTINGA': '3542701', 'RIBEIRAO CORRENTE': '3543105',
    'RIFAINA': '3543600', 'SAO JOAQUIM DA BARRA': '3549409', 'SAO JOSE DA BELA VISTA': '3549508',
    'BURITIZAL': '3508207'
}

def import_new_csv():
    if not os.path.exists(DATA_DIR):
        logger.error(f"Pasta não encontrada: {DATA_DIR}")
        return

    # Busca em qualquer subpasta o arquivo EmendasParlamentares.csv
    arquivos = list(Path(DATA_DIR).rglob("EmendasParlamentares*.csv*"))
    
    # Filtrar para não pegar os arquivos de convenios/favorecidos que tem schema diferente
    arquivos = [a for a in arquivos if "convenios" not in str(a).lower() and "favorecido" not in str(a).lower()]
    
    # Aceitar também br_cgu_emendas_parlamentares_microdados.csv.gz (o nome original)
    arquivos.extend(list(Path(DATA_DIR).rglob("br_cgu_emendas*.csv*")))
    
    if not arquivos:
        logger.error(f"Nenhum arquivo CSV de emendas encontrado na pasta {DATA_DIR} e suas subpastas.")
        return
        
    logger.info(f"Encontrados {len(arquivos)} arquivos CSV para processar.")
    logger.info("Buscando metadados de deputados na Câmara (Partido, UF, Foto)...")
    deputados_map = buscar_deputados()

    for arquivo_path in arquivos:
        logger.info(f"Carregando CSV: {arquivo_path}")
        
        mapping = {
            'id_emenda': 'Código da Emenda',
            'ano_emenda': 'Ano da Emenda',
            'tipo_emenda': 'Tipo de Emenda',
            'id_autor_emenda': 'Código do Autor da Emenda',
            'nome_autor_emenda': 'Nome do Autor da Emenda',
            'numero_emenda': 'Número da emenda',
            'localidade': 'Localidade de aplicação do recurso',
            'id_municipio_gasto': 'Código Município IBGE',
            'id_funcao': 'Código Função',
            'nome_funcao': 'Nome Função',
            'id_subfuncao': 'Código Subfunção',
            'nome_subfuncao': 'Nome Subfunção',
            'id_programa': 'Código Programa',
            'nome_programa': 'Nome Programa',
            'id_acao': 'Código Ação',
            'nome_acao': 'Nome Ação',
            'id_plano_orcamentario': 'Código Plano Orçamentário',
            'nome_plano_orcamentario': 'Nome Plano Orçamentário',
            'valor_empenhado': 'Valor Empenhado',
            'valor_liquidado': 'Valor Liquidado',
            'valor_pago': 'Valor Pago',
            'valor_resto_pagar_inscrito': 'Valor Restos A Pagar Inscritos',
            'valor_resto_pagar_cancelado': 'Valor Restos A Pagar Cancelados',
            'valor_resto_pagar_pagos': 'Valor Restos A Pagar Pagos'
        }

        import csv
        try:
            df = pd.read_csv(arquivo_path, sep=';', encoding='utf-8', low_memory=False, on_bad_lines='skip', quoting=csv.QUOTE_NONE)
        except Exception:
            try:
                df = pd.read_csv(arquivo_path, sep=';', encoding='latin1', low_memory=False, on_bad_lines='skip', quoting=csv.QUOTE_NONE)
            except Exception as e:
                logger.error(f"Erro fatal ao ler {arquivo_path}: {e}")
                continue
        
        # Limpar aspas das colunas caso QUOTE_NONE tenha deixado elas
        df.columns = df.columns.str.replace('"', '', regex=False).str.strip()
        
        # Limpar aspas de todos os valores string no dataframe inteiro
        logger.info("Limpando aspas dos valores...")
        df = df.replace('"', '', regex=True)

        # Renomear colunas baseadas nas que existirem no mapping
        renames = {k: v for k, v in mapping.items() if k in df.columns}
        df = df.rename(columns=renames)
        
        # Colunas que faltam no CSV mas existem no banco
        missing_cols = {
            'Código Município IBGE': np.nan,
            'Localidade de aplicação do recurso': df.get('localidade_do_gasto', np.nan),
            'Código UF IBGE': np.nan,
            'UF': df.get('sigla_uf_gasto', np.nan),
            'Região': np.nan
        }
    
        for col, val in missing_cols.items():
            if col not in df.columns:
                df[col] = val
                
        # Consertar Município se não existir
        if 'Município' not in df.columns:
            df['Município'] = df.get('Localidade de aplicação do recurso', np.nan)
            
        # Criar colunas para os dados da câmara
        partidos = []
        ufs_autor = []
        fotos = []
        
        logger.info("Limpando colunas numéricas...")
        colunas_valores = [
            "Valor Empenhado", "Valor Liquidado", "Valor Pago", 
            "Valor Restos A Pagar Inscritos", "Valor Restos A Pagar Cancelados", 
            "Valor Restos A Pagar Pagos"
        ]
        
        for col in colunas_valores:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'[^0-9,-]', '', regex=True).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        logger.info(f"Colunas disponíveis antes do loop: {df.columns.tolist()}")
        logger.info("Cruzando dados dos autores...")
        if 'Nome do Autor da Emenda' not in df.columns:
            logger.error("COLUNA 'Nome do Autor da Emenda' SUMIU! Abortando este arquivo.")
            continue
            
        for nome in df['Nome do Autor da Emenda']:
            dados_camara = cruzar_dados_autor(str(nome), deputados_map)
            partidos.append(dados_camara["partido"])
            ufs_autor.append(dados_camara["uf_autor"])
            fotos.append(None)
            
        df["Partido do Autor"] = partidos
        df["UF do Autor"] = ufs_autor
        df["Foto do Autor"] = fotos

        # Garantir a ordem das colunas igual ao banco
        db_cols = [
            "Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Código do Autor da Emenda",
            "Nome do Autor da Emenda", "Número da emenda", "Localidade de aplicação do recurso",
            "Código Município IBGE", "Município", "Código UF IBGE", "UF", "Região",
            "Código Função", "Nome Função", "Código Subfunção", "Nome Subfunção",
            "Código Programa", "Nome Programa", "Código Ação", "Nome Ação",
            "Código Plano Orçamentário", "Nome Plano Orçamentário", "Valor Empenhado",
            "Valor Liquidado", "Valor Pago", "Valor Restos A Pagar Inscritos",
            "Valor Restos A Pagar Cancelados", "Valor Restos A Pagar Pagos",
            "Partido do Autor", "UF do Autor", "Foto do Autor"
        ]
        
        # Manter apenas as colunas necessárias e na ordem certa
        df = df[[col for col in db_cols if col in df.columns]]
        for missing in [c for c in db_cols if c not in df.columns]:
            df[missing] = np.nan
        df = df[db_cols]
        
        # Consertar IBGEs ausentes ou "Sem informação" usando a coluna de Localidade
        if 'Código Município IBGE' in df.columns and 'Localidade de aplicação do recurso' in df.columns:
            def fix_ibge(row):
                curr = str(row['Código Município IBGE']).strip()
                if curr == 'Sem informação' or curr == 'nan' or curr == '' or 'MÚLTIPLO' in str(row['Localidade de aplicação do recurso']).upper():
                    loc = str(row['Localidade de aplicação do recurso']).upper()
                    for mun, ibge in MAP_MUNICIPIOS_SJ.items():
                        if mun in loc:
                            return ibge
                return curr
        # Consertar IBGEs ausentes ou "Sem informação" usando a coluna de Localidade
        if 'Código Município IBGE' in df.columns and 'Localidade de aplicação do recurso' in df.columns:
            def fix_ibge(row):
                curr = str(row['Código Município IBGE']).strip()
                if curr == 'Sem informação' or curr == 'nan' or curr == '' or 'MÚLTIPLO' in str(row['Localidade de aplicação do recurso']).upper():
                    loc = str(row['Localidade de aplicação do recurso']).upper()
                    for mun, ibge in MAP_MUNICIPIOS_SJ.items():
                        if mun in loc:
                            return ibge
                return curr
            df['Código Município IBGE'] = df.apply(fix_ibge, axis=1)

        # Tratar IBGE para remover .0 se existir
        df['Código Município IBGE'] = df['Código Município IBGE'].astype(str).str.replace('.0', '', regex=False)
        
        con = duckdb.connect(DB_PATH)
        con.register('df_new', df)
        
        logger.info(f"Mesclando dados do {arquivo_path.name} no banco local...")
        try:
            # Tenta criar as novas colunas se não existirem
            try:
                con.execute('ALTER TABLE emendas_parlamentares ADD COLUMN "Partido do Autor" VARCHAR')
                con.execute('ALTER TABLE emendas_parlamentares ADD COLUMN "UF do Autor" VARCHAR')
                con.execute('ALTER TABLE emendas_parlamentares ADD COLUMN "Foto do Autor" VARCHAR')
            except:
                pass # As colunas já existem
                
            # Deletar os antigos para atualizar caso tenham mudado
            con.execute("""
                DELETE FROM emendas_parlamentares 
                WHERE "Código da Emenda" IN (SELECT "Código da Emenda" FROM df_new)
            """)
            
            # Inserir tudo atualizado com os partidos
            con.execute("""
                INSERT INTO emendas_parlamentares 
                SELECT * FROM df_new 
            """)
            logger.info(f"✓ Importação de {arquivo_path.name} concluída!")
        except Exception as e:
            logger.error(f"Erro ao inserir {arquivo_path.name}: {e}")
        finally:
            con.close()

if __name__ == "__main__":
    import_new_csv()
