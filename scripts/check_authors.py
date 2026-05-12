import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Autores com 'ALAGOAS' ou 'AL' no nome ===")
r = con.execute("""
    SELECT "Nome do Autor da Emenda", COUNT(*) as n,
           SUM(TRY_CAST(REPLACE(REPLACE("Valor Empenhado",'.',''),',','.') AS DOUBLE)) as total
    FROM emendas_parlamentares
    WHERE "Nome do Autor da Emenda" LIKE '%BANCADA%'
       OR "Nome do Autor da Emenda" LIKE '%ALAGOAS%'
    GROUP BY 1 ORDER BY total DESC
""").fetchall()
for row in r:
    print(f"{row[0]} | {row[1]} emendas | R$ {row[2]:,.2f}")
con.close()
