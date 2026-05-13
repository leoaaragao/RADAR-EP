import pandas as pd
import csv
df = pd.read_csv('data/Emendas CGU ano/2021/EmendasParlamentares.csv', sep=';', encoding='latin1', on_bad_lines='skip', quoting=csv.QUOTE_NONE, nrows=0)
print("Original:", repr(df.columns.tolist()[4]))
df.columns = df.columns.str.replace('"', '', regex=False)
df.columns = df.columns.str.strip()
print("Depois do replace e strip:", repr(df.columns.tolist()[4]))
print("Existe?", 'Nome do Autor da Emenda' in df.columns)
