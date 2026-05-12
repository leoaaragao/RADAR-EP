import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Verificando emenda 201826760002 ===")
r = con.execute('SELECT * FROM emendas_parlamentares WHERE "Código da Emenda" = \'201826760002\'').df()
print(r)
con.close()
