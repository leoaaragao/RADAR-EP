import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print(con.execute('SELECT "Ano da Emenda", COUNT(*) FROM emendas_parlamentares WHERE "Tipo de Emenda" LIKE \'%Especiais%\' GROUP BY "Ano da Emenda" ORDER BY "Ano da Emenda"').df())
