import duckdb
con = duckdb.connect('radar_ep.duckdb')
cols = [
    'Valor Empenhado', 'Valor Liquidado', 'Valor Pago', 
    'Valor Restos A Pagar Inscritos', 'Valor Restos A Pagar Cancelados', 'Valor Restos A Pagar Pagos'
]
print("=== Convertendo colunas para DOUBLE ===")
for col in cols:
    print(f"Limpando e convertendo {col}...")
    # 1. Tratar formato brasileiro (1.000,00)
    con.execute(f'UPDATE emendas_parlamentares SET "{col}" = REPLACE(REPLACE("{col}", \'.\', \'\'), \',\', \'.\') WHERE "{col}" LIKE \'%,%\'')
    # 2. Tentar converter para DOUBLE
    try:
        con.execute(f'ALTER TABLE emendas_parlamentares ALTER "{col}" TYPE DOUBLE')
    except Exception as e:
        print(f"  ⚠ Erro em {col}: {e}. Tentando limpeza forçada...")
        # Se falhar, tenta cast forçado limpando caracteres não numéricos
        con.execute(f'UPDATE emendas_parlamentares SET "{col}" = \'0\' WHERE "{col}" = \'Sem informação\' OR "{col}" IS NULL')
        con.execute(f'ALTER TABLE emendas_parlamentares ALTER "{col}" TYPE DOUBLE')

con.close()
print("✓ Concluído!")
