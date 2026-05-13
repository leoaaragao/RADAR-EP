import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
df = con.execute('SELECT "Código Município IBGE" FROM emendas_parlamentares WHERE UPPER("Município") = \'FRANCA\' LIMIT 5').df()
print("IBGE Franca:", df)
