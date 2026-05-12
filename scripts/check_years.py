import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Anos disponíveis ===")
r = con.execute('SELECT "Ano da Emenda", COUNT(*) FROM emendas_parlamentares GROUP BY 1 ORDER BY 1 DESC').fetchall()
for row in r:
    print(f"Ano {row[0]}: {row[1]} registros")

print("\n=== Amostra de IBGEs em 2019 ===")
r2 = con.execute('SELECT "Código Município IBGE", COUNT(*) FROM emendas_parlamentares WHERE "Ano da Emenda" = 2019 GROUP BY 1 LIMIT 5').fetchall()
for row in r2:
    print(row)
con.close()
