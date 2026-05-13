import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
df = con.execute('SELECT "Município", "Código Município IBGE", "Tipo de Emenda" FROM emendas_parlamentares WHERE UPPER("Município") LIKE \'%FRANCA%\' LIMIT 10').df()
print("Franca:", df)
