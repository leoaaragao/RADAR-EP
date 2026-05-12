import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Top IBGEs no banco ===")
r = con.execute('SELECT "Código Município IBGE", COUNT(*) as n FROM emendas_parlamentares GROUP BY 1 ORDER BY n DESC LIMIT 20').fetchall()
for row in r:
    print(row)
con.close()
