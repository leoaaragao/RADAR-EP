import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print(con.execute('SELECT DISTINCT "Tipo de Emenda" FROM emendas_parlamentares').df())
