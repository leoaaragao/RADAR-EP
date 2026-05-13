import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
df = con.execute('SELECT "Código Município IBGE", "Município", "Valor Empenhado" FROM emendas_parlamentares WHERE "Tipo de Emenda" LIKE \'%Especiais%\' AND CAST("Código Município IBGE" AS VARCHAR) LIKE \'35%\' LIMIT 10').df()
print("PIX em SP:", df)
