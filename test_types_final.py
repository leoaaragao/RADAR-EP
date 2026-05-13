import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
IBGES_13SJ = ('3516200','3503000','3508207','3513207','3517703','3520103','3521309','3523701','3524105','3525409','3536307','3537008','3542701','3543105','3543600','3549409','3549508')

print("=== DISTRIBUIÇÃO DE TIPOS NA 13 SJ (ULTIMA INGESTAO) ===")
df = con.execute(f"SELECT \"Tipo de Emenda\", COUNT(*) FROM emendas_parlamentares WHERE \"Código Município IBGE\" IN {IBGES_13SJ} GROUP BY 1").df()
print(df)
