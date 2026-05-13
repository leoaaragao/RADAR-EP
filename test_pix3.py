import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print(con.execute('SELECT "Código Município IBGE", COUNT(*) FROM emendas_parlamentares WHERE "Tipo de Emenda" LIKE \'%Especiais%\' GROUP BY "Código Município IBGE" LIMIT 10').df())
