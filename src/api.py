"""
RADAR-EP — API FastAPI
========================
Fase 4 — Endpoints REST para integração e retroalimentação.

Iniciar com: uvicorn src.api:app --host 0.0.0.0 --port 8000
Documentação: http://localhost:8000/docs
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT_DIR / os.getenv("DUCKDB_PATH", "radar_ep.duckdb"))

app = FastAPI(
    title="RADAR-EP API",
    version="1.0.0",
    description=(
        "API de rastreamento analítico e detecção de anomalias em emendas parlamentares. "
        "13ª Subseção Judiciária do MPF — Franca/SP. "
        "Alertas automáticos não constituem confirmação de irregularidade."
    ),
    contact={"name": "13ª SJ MPF Franca/SP"},
    license_info={"name": "Uso interno restrito"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    if not Path(DB_PATH).exists():
        raise HTTPException(
            status_code=503,
            detail=f"Banco não encontrado: {DB_PATH}. Execute scripts/setup_db.py"
        )
    return duckdb.connect(DB_PATH, read_only=read_only)


def _mask_cpf(texto: str) -> str:
    """Mascara CPFs no texto (LGPD)."""
    import re
    return re.sub(r'\d{3}\.\d{3}\.\d{3}-\d{2}', '***.***.***-**', str(texto or ""))


# ── Modelos Pydantic ──────────────────────────────────────────
class ClassificacaoRequest(BaseModel):
    classificacao: str  # falso_positivo | encaminhado | verificando
    classificado_por: str
    observacoes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health", tags=["Sistema"])
def health():
    """Healthcheck do sistema."""
    db_ok = Path(DB_PATH).exists()
    return {
        "status": "ok" if db_ok else "degraded",
        "timestamp": datetime.now().isoformat(),
        "db_disponivel": db_ok,
        "versao": "1.0.0",
    }


@app.get("/alertas", tags=["Alertas"])
def listar_alertas(
    municipio: Optional[str] = None,
    escore_min: float = Query(0.20, ge=0.0, le=1.0),
    status: Optional[str] = None,
    ano: Optional[int] = None,
    limite: int = Query(50, ge=1, le=500),
    pagina: int = Query(1, ge=1),
):
    """
    Lista alertas com filtros.

    Retorna alertas ordenados por escore decrescente.
    Alertas com escore < 0.80 têm requer_confirmacao_humana=true.
    """
    con = get_db()
    offset = (pagina - 1) * limite

    wheres = [f"escore >= {escore_min}"]
    if municipio:
        wheres.append(f"municipio = '{municipio}'")
    if status:
        wheres.append(f"status = '{status}'")
    if ano:
        wheres.append(f"ano_emenda = {ano}")

    where_str = "WHERE " + " AND ".join(wheres) if wheres else ""

    df = con.execute(f"""
        SELECT id, codigo_emenda, municipio, ibge, parlamentar, tipo_emenda,
               ano_emenda, tipo_alerta, escore, descricao, indicadores_ativados,
               requer_confirmacao_humana, valor_emenda, data_geracao, status
        FROM alertas
        {where_str}
        ORDER BY escore DESC, data_geracao DESC
        LIMIT {limite} OFFSET {offset}
    """).df()

    total = con.execute(
        f"SELECT COUNT(*) FROM alertas {where_str}"
    ).fetchone()[0]
    con.close()

    return {
        "total": total,
        "pagina": pagina,
        "limite": limite,
        "dados": df.to_dict(orient="records"),
    }


@app.get("/alertas/{id_alerta}", tags=["Alertas"])
def detalhe_alerta(id_alerta: int):
    """Detalhes completos de um alerta específico."""
    con = get_db()
    df = con.execute(
        "SELECT * FROM alertas WHERE id = ?", [id_alerta]
    ).df()
    con.close()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Alerta #{id_alerta} não encontrado")

    dados = df.iloc[0].to_dict()
    return dados


@app.post("/alertas/{id_alerta}/classificar", tags=["Alertas"])
def classificar_alerta(id_alerta: int, req: ClassificacaoRequest):
    """
    Registra classificação humana de um alerta (retroalimentação).
    Usado para recalibração trimestral dos pesos dos indicadores.
    """
    status_validos = {"falso_positivo", "encaminhado", "verificando", "aberto"}
    if req.classificacao not in status_validos:
        raise HTTPException(
            status_code=422,
            detail=f"Classificação inválida. Use: {sorted(status_validos)}"
        )

    con = get_db(read_only=False)
    existe = con.execute(
        "SELECT COUNT(*) FROM alertas WHERE id = ?", [id_alerta]
    ).fetchone()[0]

    if not existe:
        con.close()
        raise HTTPException(status_code=404, detail=f"Alerta #{id_alerta} não encontrado")

    con.execute("""
        UPDATE alertas
        SET status = ?,
            classificado_por = ?,
            data_classificacao = current_timestamp,
            observacoes = ?
        WHERE id = ?
    """, [req.classificacao, req.classificado_por, req.observacoes, id_alerta])
    con.close()

    return {
        "id": id_alerta,
        "classificacao": req.classificacao,
        "classificado_por": req.classificado_por,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/municipio/{ibge}", tags=["Municípios"])
def detalhe_municipio(
    ibge: str,
    ano_inicio: int = 2020,
    limite: int = Query(200, ge=1, le=1000),
):
    """Emendas de um município por código IBGE."""
    con = get_db()
    info = con.execute(
        "SELECT * FROM municipios_franca WHERE ibge = ?", [ibge]
    ).df()

    if info.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Município IBGE {ibge} não encontrado nos 17 municípios monitorados"
        )

    df = con.execute(f"""
        SELECT * FROM emendas_parlamentares
        WHERE "Código Município IBGE" = '{ibge}'
          AND TRY_CAST("Ano da Emenda" AS INTEGER) >= {ano_inicio}
        ORDER BY "Ano da Emenda" DESC
        LIMIT {limite}
    """).df()

    alertas_count = con.execute(
        "SELECT COUNT(*), AVG(escore) FROM alertas WHERE ibge = ?", [ibge]
    ).fetchone()
    con.close()

    return {
        "ibge": ibge,
        "municipio": info.iloc[0].to_dict(),
        "total_emendas": len(df),
        "alertas": {
            "total": alertas_count[0] or 0,
            "escore_medio": round(alertas_count[1] or 0, 3),
        },
        "emendas": df.to_dict(orient="records"),
    }


@app.get("/municipios", tags=["Municípios"])
def listar_municipios():
    """Lista os 17 municípios monitorados com estatísticas."""
    con = get_db()
    df = con.execute("""
        SELECT m.*,
               COALESCE(a.n_alertas, 0) as alertas,
               COALESCE(a.escore_medio, 0) as escore_medio
        FROM municipios_franca m
        LEFT JOIN (
            SELECT ibge, COUNT(*) as n_alertas, AVG(escore) as escore_medio
            FROM alertas GROUP BY ibge
        ) a ON m.ibge = a.ibge
        ORDER BY escore_medio DESC
    """).df()
    con.close()
    return df.to_dict(orient="records")


@app.get("/parlamentar/{codigo}", tags=["Parlamentares"])
def detalhe_parlamentar(codigo: str, ano_inicio: int = 2020):
    """Emendas de um parlamentar por código."""
    con = get_db()
    df = con.execute(f"""
        SELECT
            "Nome do Autor da Emenda"  AS parlamentar,
            "Município"                AS municipio,
            "Ano da Emenda"            AS ano,
            "Nome Função"              AS funcao,
            "Tipo de Emenda"           AS tipo,
            COUNT(*)                   AS n_emendas,
            SUM(TRY_CAST(REPLACE(REPLACE("Valor Empenhado",'.',''),',','.') AS DOUBLE))
                                       AS total_empenhado
        FROM emendas_parlamentares
        WHERE "Código do Autor da Emenda" = '{codigo}'
          AND TRY_CAST("Ano da Emenda" AS INTEGER) >= {ano_inicio}
        GROUP BY 1,2,3,4,5
        ORDER BY ano DESC, total_empenhado DESC
    """).df()
    con.close()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Parlamentar {codigo} não encontrado")

    return {
        "codigo": codigo,
        "parlamentar": df["parlamentar"].iloc[0],
        "total_registros": len(df),
        "total_empenhado": float(df["total_empenhado"].sum()),
        "dados": df.to_dict(orient="records"),
    }


@app.get("/estatisticas", tags=["Sistema"])
def estatisticas():
    """Estatísticas gerais do banco e dos alertas."""
    con = get_db()

    stats = {}

    for tabela in ["emendas_parlamentares", "convenios", "por_favorecido", "alertas"]:
        try:
            count = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            stats[tabela] = count
        except Exception:
            stats[tabela] = None

    alertas_status = con.execute("""
        SELECT status, COUNT(*) as n, AVG(escore) as escore_medio
        FROM alertas GROUP BY status
    """).df()

    top_mun = con.execute("""
        SELECT municipio, COUNT(*) as alertas, AVG(escore) as escore
        FROM alertas GROUP BY municipio ORDER BY escore DESC LIMIT 5
    """).df()

    con.close()

    return {
        "contagens": stats,
        "alertas_por_status": alertas_status.to_dict(orient="records"),
        "top_municipios_risco": top_mun.to_dict(orient="records"),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/favorecido/{cnpj}", tags=["Favorecidos"])
def detalhe_favorecido(cnpj: str):
    """
    Pagamentos recebidos por um favorecido (CNPJ).
    CPFs são mascarados conforme LGPD.
    """
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    con = get_db()

    df = con.execute(f"""
        SELECT
            "Nome do Autor da Emenda"  AS parlamentar,
            "Tipo de Emenda"           AS tipo_emenda,
            "Ano/Mês"                  AS ano_mes,
            "Natureza Jurídica"        AS natureza_juridica,
            "UF Favorecido"            AS uf,
            "Município Favorecido"     AS municipio,
            TRY_CAST(
                REPLACE(REPLACE("Valor Recebido",'.',''),',','.') AS DOUBLE
            )                          AS valor_recebido
        FROM por_favorecido
        WHERE REGEXP_REPLACE("Código do Favorecido", '[^0-9]', '') = '{cnpj_limpo}'
        ORDER BY "Ano/Mês" DESC
        LIMIT 500
    """).df()
    con.close()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Favorecido {cnpj} não encontrado")

    return {
        "cnpj": cnpj_limpo,
        "total_registros": len(df),
        "total_recebido": float(df["valor_recebido"].sum()),
        "dados": df.to_dict(orient="records"),
    }


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("src.api:app", host=host, port=port, reload=True)
