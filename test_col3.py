import pandas as pd
import csv
df = pd.read_csv('data/EmendasParlamentares.csv', sep=';', encoding='latin1', on_bad_lines='skip', quoting=csv.QUOTE_NONE, nrows=0)
df.columns = df.columns.str.replace('"', '', regex=False).str.strip()
print(df.columns.tolist())
