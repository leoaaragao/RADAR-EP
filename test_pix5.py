import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
df = con.execute('SELECT "Código Município IBGE", "Município", "Valor Empenhado", "Localidade de aplicação do recurso" FROM emendas_parlamentares WHERE "Tipo de Emenda" LIKE \'%Especiais%\' AND (UPPER("Município") LIKE \'%FRANCA%\' OR UPPER("Localidade de aplicação do recurso") LIKE \'%FRANCA%\')').df()
print("Franca PIX:", df)
