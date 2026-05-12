import duckdb
con = duckdb.connect('radar_ep.duckdb', read_only=True)
print("=== Registros por Município (Jurisdição) ===")
ibges = ["3516200", "3549409", "3524105", "3520103", "3517703", "3521309", "3537008", "3536307", "3549508", "3513207", "3542701", "3523701", "3503000", "3543105", "3508207", "3543600", "3525409"]
for ibge in ibges:
    r = con.execute(f'SELECT "Município", COUNT(*) FROM emendas_parlamentares WHERE "Código Município IBGE" = \'{ibge}\' GROUP BY 1').fetchall()
    print(f"IBGE {ibge}: {r}")
con.close()
