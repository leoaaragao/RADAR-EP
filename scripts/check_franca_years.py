import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Anos em Franca (3516200) ===")
r = con.execute("""
    SELECT "Ano da Emenda", COUNT(*)
    FROM emendas_parlamentares
    WHERE "Código Município IBGE" = '3516200'
    GROUP BY 1 ORDER BY 1 DESC
""").fetchall()
for row in r:
    print(row)
con.close()
