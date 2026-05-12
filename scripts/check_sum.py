import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Dados de Franca (3516200) ===")
r = con.execute('SELECT * FROM emendas_parlamentares WHERE "Código Município IBGE" = \'3516200\' LIMIT 2').df()
print(r)
print("\n=== Teste de Soma em Franca ===")
r2 = con.execute("""
    SELECT SUM(TRY_CAST(REPLACE(REPLACE("Valor Empenhado",'.',''),',','.') AS DOUBLE))
    FROM emendas_parlamentares
    WHERE "Código Município IBGE" = '3516200'
""").fetchall()
print(r2)
con.close()
