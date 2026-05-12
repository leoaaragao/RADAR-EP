import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)

ibges = [
    '3516200','3503000','3508207','3513207','3517703',
    '3520103','3521309','3523701','3524105','3525409',
    '3536307','3537008','3542701','3543105','3543600',
    '3549409','3549508'
]
ibge_str = "','".join(ibges)

print("=== Emendas de Bancadas nos 17 municipios da 13a SJ ===")
r = con.execute(f"""
    SELECT "Nome do Autor da Emenda", "Município", COUNT(*) as n,
           SUM(TRY_CAST(REPLACE(REPLACE("Valor Empenhado",'.',''),',','.') AS DOUBLE)) as total
    FROM emendas_parlamentares
    WHERE "Código Município IBGE" IN ('{ibge_str}')
      AND "Nome do Autor da Emenda" LIKE '%BANCADA%'
    GROUP BY 1, 2 ORDER BY total DESC
""").fetchall()

if not r:
    print("Nenhuma emenda de bancada encontrada para estes municipios.")
else:
    for row in r:
        print(f"{row[0]} -> {row[1]} | {row[2]} emendas | R$ {row[3]:,.2f}")

con.close()
