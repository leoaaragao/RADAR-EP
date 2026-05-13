import pandas as pd
import csv
import traceback

def test():
    try:
        df = pd.read_csv('data/EmendasParlamentares.csv', sep=';', encoding='utf-8', on_bad_lines='skip', quoting=csv.QUOTE_NONE, nrows=0)
        df.columns = df.columns.str.replace('"', '', regex=False).str.strip()
        print("UTF-8 DEU CERTO!")
        print(df.columns.tolist())
        print("Tem nome?", 'Nome do Autor da Emenda' in df.columns)
    except Exception as e:
        print("UTF-8 FALHOU!")
        traceback.print_exc()

test()
