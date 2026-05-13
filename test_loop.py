import pandas as pd
import csv

arquivo_path = 'data/EmendasParlamentares.csv'
print(f"Carregando {arquivo_path}")
df = pd.read_csv(arquivo_path, sep=';', encoding='latin1', low_memory=False, on_bad_lines='skip', quoting=csv.QUOTE_NONE, nrows=10)
df.columns = df.columns.str.replace('"', '', regex=False).str.strip()
print("Colunas:", df.columns.tolist())
print("Tem nome autor?", 'Nome do Autor da Emenda' in df.columns)

if 'Nome do Autor da Emenda' in df.columns:
    df['Nome do Autor da Emenda'] = df['Nome do Autor da Emenda'].astype(str).str.replace('"', '', regex=False)

try:
    for nome in df['Nome do Autor da Emenda']:
        print(f"Nome: {nome}")
        break
except Exception as e:
    print("ERRO no loop!")
    import traceback
    traceback.print_exc()

