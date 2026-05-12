"""
RADAR-EP — Testes da API FastAPI
==================================
Testa os endpoints REST com um banco DuckDB temporário.

Executar: pytest tests/test_api.py -v
"""

import pytest
import duckdb
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def db_temp():
    """Cria banco DuckDB temporário com dados mínimos para os testes."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name

    con = duckdb.connect(db_path)

    # Tabelas mínimas para os testes
    con.execute("""
        CREATE TABLE municipios_franca (
            nome VARCHAR, ibge VARCHAR, populacao INTEGER, porte VARCHAR,
            lat DOUBLE, lon DOUBLE
        )
    """)
    con.execute("""
        INSERT INTO municipios_franca VALUES
        ('Franca', '3516200', 365494, 'G', -20.539, -47.401),
        ('Ituverava', '3525706', 38413, 'M', -20.339, -47.776)
    """)

    con.execute("""
        CREATE TABLE alertas (
            id INTEGER PRIMARY KEY,
            codigo_emenda VARCHAR, municipio VARCHAR, ibge VARCHAR,
            parlamentar VARCHAR, codigo_parlamentar VARCHAR,
            tipo_emenda VARCHAR, ano_emenda INTEGER, tipo_alerta VARCHAR,
            escore DECIMAL(5,4), descricao TEXT, indicadores_ativados VARCHAR,
            requer_confirmacao_humana BOOLEAN, valor_emenda DOUBLE,
            data_geracao TIMESTAMP DEFAULT current_timestamp,
            status VARCHAR DEFAULT 'aberto',
            classificado_por VARCHAR, data_classificacao TIMESTAMP,
            observacoes TEXT
        )
    """)
    con.execute("""
        INSERT INTO alertas VALUES
        (1, 'EM-2024-001', 'Franca', '3516200', 'Dep. Teste', 'DT001',
         'Emenda Individual', 2024, 'CONCENTRACAO', 0.32,
         'Padrão atípico que merece verificação', '["concentracao"]',
         TRUE, 500000.0, current_timestamp, 'aberto', NULL, NULL, NULL),
        (2, 'EM-2024-002', 'Ituverava', '3525706', 'Sen. Exemplo', 'SE002',
         'Emenda Individual', 2024, 'EMPRESA_JOVEM', 0.72,
         'Indício a verificar', '["empresa_jovem","concentracao"]',
         TRUE, 1200000.0, current_timestamp, 'aberto', NULL, NULL, NULL)
    """)

    con.execute("""
        CREATE TABLE emendas_parlamentares ("Código Município IBGE" VARCHAR,
            "Município" VARCHAR, "Ano da Emenda" VARCHAR,
            "Nome do Autor da Emenda" VARCHAR, "Código do Autor da Emenda" VARCHAR,
            "Valor Empenhado" VARCHAR, "Tipo de Emenda" VARCHAR, "Nome Função" VARCHAR)
    """)
    con.execute("""
        INSERT INTO emendas_parlamentares VALUES
        ('3516200','Franca','2024','Dep. Teste','DT001','500.000,00','Emenda Individual','Saúde'),
        ('3525706','Ituverava','2024','Sen. Exemplo','SE002','1.200.000,00','Emenda Individual','Educação')
    """)

    con.execute("CREATE TABLE por_favorecido (\"Código do Favorecido\" VARCHAR)")
    con.close()

    yield db_path
    os.unlink(db_path)


@pytest.fixture(scope="module")
def client(db_temp, monkeypatch=None):
    """TestClient com banco temporário."""
    import src.api as api_module
    api_module.DB_PATH = db_temp
    return TestClient(api_module.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_listar_alertas(client):
    r = client.get("/alertas")
    assert r.status_code == 200
    data = r.json()
    assert "dados" in data
    assert data["total"] >= 2


def test_listar_alertas_filtro_municipio(client):
    r = client.get("/alertas?municipio=Franca&escore_min=0.0")
    assert r.status_code == 200
    data = r.json()
    for alerta in data["dados"]:
        assert alerta["municipio"] == "Franca"


def test_listar_alertas_filtro_escore(client):
    r = client.get("/alertas?escore_min=0.5")
    assert r.status_code == 200
    data = r.json()
    for alerta in data["dados"]:
        assert float(alerta["escore"]) >= 0.5


def test_detalhe_alerta(client):
    r = client.get("/alertas/1")
    assert r.status_code == 200
    assert r.json()["id"] == 1


def test_detalhe_alerta_nao_encontrado(client):
    r = client.get("/alertas/9999")
    assert r.status_code == 404


def test_classificar_alerta(client):
    r = client.post("/alertas/1/classificar", json={
        "classificacao": "verificando",
        "classificado_por": "analista_teste",
        "observacoes": "Verificando documentação"
    })
    assert r.status_code == 200
    assert r.json()["classificacao"] == "verificando"


def test_classificar_alerta_invalido(client):
    r = client.post("/alertas/1/classificar", json={
        "classificacao": "fraude_confirmada",  # inválido
        "classificado_por": "analista_teste"
    })
    assert r.status_code == 422


def test_listar_municipios(client):
    r = client.get("/municipios")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 2
    nomes = [m["nome"] for m in data]
    assert "Franca" in nomes


def test_detalhe_municipio(client):
    r = client.get("/municipio/3516200")
    assert r.status_code == 200
    data = r.json()
    assert data["ibge"] == "3516200"
    assert "municipio" in data


def test_detalhe_municipio_nao_monitorado(client):
    r = client.get("/municipio/9999999")
    assert r.status_code == 404


def test_estatisticas(client):
    r = client.get("/estatisticas")
    assert r.status_code == 200
    data = r.json()
    assert "contagens" in data
    assert "timestamp" in data
