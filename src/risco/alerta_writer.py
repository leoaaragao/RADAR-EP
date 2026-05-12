"""
RADAR-EP — Escritor de Alertas
================================
Persiste os resultados do motor de risco na tabela 'alertas' do DuckDB.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


def _proximo_id(con: duckdb.DuckDBPyConnection) -> int:
    """Retorna o próximo ID disponível para a tabela alertas."""
    result = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM alertas").fetchone()
    return result[0] if result else 1


def salvar_alerta(
    resultado: dict,
    con: duckdb.DuckDBPyConnection,
    tipo_alerta: Optional[str] = None,
) -> int:
    """
    Salva um resultado do motor de risco como alerta no DuckDB.

    Args:
        resultado: dict retornado por risk_engine.avaliar_emenda()
        con: conexão DuckDB
        tipo_alerta: categoria do alerta (ex: "CNPJ_JOVEM", "VALOR_ANOMALO")

    Returns:
        ID do alerta inserido
    """
    if resultado.get("escore", 0) == 0:
        return -1  # Não salva alertas com escore zero

    # Determinar tipo de alerta principal
    if not tipo_alerta:
        ativados = resultado.get("indicadores_ativados", [])
        if ativados:
            tipo_alerta = max(ativados, key=lambda k: {"concentracao": 9, "divergencia_objeto": 8,
                "empresa_jovem": 7, "doacao_parlamentar": 6, "pre_eleitoral": 5,
                "valor_anomalo": 4, "campos_ausentes": 3, "historico_sancoes": 2,
                "pc_vencida": 1}.get(k, 0)).upper()
        else:
            tipo_alerta = "COMPOSTO"

    id_alerta = _proximo_id(con)

    try:
        con.execute("""
            INSERT INTO alertas (
                id, codigo_emenda, municipio, ibge, parlamentar,
                codigo_parlamentar, tipo_emenda, ano_emenda, tipo_alerta,
                escore, descricao, indicadores_ativados,
                requer_confirmacao_humana, valor_emenda,
                data_geracao, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp, 'aberto')
        """, [
            id_alerta,
            resultado.get("codigo_emenda"),
            resultado.get("municipio"),
            resultado.get("ibge"),
            resultado.get("parlamentar"),
            resultado.get("codigo_parlamentar"),
            resultado.get("tipo_emenda"),
            resultado.get("ano_emenda"),
            tipo_alerta,
            resultado.get("escore"),
            resultado.get("descricao"),
            json.dumps(resultado.get("indicadores_ativados", []), ensure_ascii=False),
            resultado.get("requer_confirmacao_humana", True),
            resultado.get("valor_emenda"),
        ])
        logger.debug("Alerta #%d salvo: escore=%.3f emenda=%s",
                     id_alerta, resultado.get("escore", 0), resultado.get("codigo_emenda"))
        return id_alerta

    except Exception as e:
        logger.error("Erro ao salvar alerta: %s | dados: %s", e, resultado)
        return -1


def salvar_lote_alertas(
    df_resultados: pd.DataFrame,
    db_path: str = "radar_ep.duckdb",
    escore_minimo: float = 0.20,
) -> int:
    """
    Salva um DataFrame de resultados como alertas no DuckDB.

    Args:
        df_resultados: DataFrame retornado por risk_engine.processar_lote()
        db_path: caminho para o banco DuckDB
        escore_minimo: apenas salva alertas acima deste escore

    Returns:
        Número de alertas salvos
    """
    if df_resultados.empty:
        return 0

    con = duckdb.connect(db_path)
    salvos = 0

    df_filtrado = df_resultados[df_resultados["escore"] >= escore_minimo]

    for _, row in df_filtrado.iterrows():
        id_alerta = salvar_alerta(row.to_dict(), con)
        if id_alerta > 0:
            salvos += 1

    con.close()
    logger.info("Salvos %d/%d alertas (escore >= %.2f)",
                salvos, len(df_filtrado), escore_minimo)
    return salvos


def classificar_alerta(
    id_alerta: int,
    classificacao: str,
    classificado_por: str,
    observacoes: Optional[str] = None,
    db_path: str = "radar_ep.duckdb",
) -> bool:
    """
    Registra a classificação humana de um alerta (retroalimentação).

    Args:
        id_alerta: ID do alerta
        classificacao: 'falso_positivo' | 'encaminhado' | 'verificando'
        classificado_por: identificação do analista
        observacoes: texto livre
        db_path: caminho do banco

    Returns:
        True se atualizado com sucesso
    """
    status_validos = {"falso_positivo", "encaminhado", "verificando", "aberto"}
    if classificacao not in status_validos:
        raise ValueError(f"Classificação inválida: {classificacao}. Use: {status_validos}")

    try:
        con = duckdb.connect(db_path)
        con.execute("""
            UPDATE alertas
            SET status = ?,
                classificado_por = ?,
                data_classificacao = current_timestamp,
                observacoes = ?
            WHERE id = ?
        """, [classificacao, classificado_por, observacoes, id_alerta])
        con.close()
        logger.info("Alerta #%d classificado como '%s' por %s",
                    id_alerta, classificacao, classificado_por)
        return True
    except Exception as e:
        logger.error("Erro ao classificar alerta #%d: %s", id_alerta, e)
        return False


def obter_estatisticas(db_path: str = "radar_ep.duckdb") -> dict:
    """Retorna estatísticas dos alertas para o dashboard."""
    try:
        con = duckdb.connect(db_path, read_only=True)

        total = con.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]
        por_status = con.execute("""
            SELECT status, COUNT(*) FROM alertas GROUP BY status
        """).fetchall()
        escore_medio = con.execute("SELECT AVG(escore) FROM alertas").fetchone()[0]
        por_municipio = con.execute("""
            SELECT municipio, COUNT(*), AVG(escore)
            FROM alertas GROUP BY municipio
            ORDER BY 3 DESC LIMIT 10
        """).fetchall()

        con.close()
        return {
            "total": total,
            "por_status": dict(por_status),
            "escore_medio": round(escore_medio or 0, 3),
            "top_municipios": [
                {"municipio": r[0], "alertas": r[1], "escore_medio": round(r[2], 3)}
                for r in por_municipio
            ],
        }
    except Exception as e:
        logger.error("Erro ao obter estatísticas: %s", e)
        return {"total": 0, "por_status": {}, "escore_medio": 0, "top_municipios": []}
