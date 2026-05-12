"""
RADAR-EP — Testes do Motor de Risco
=====================================
Testa cada indicador isoladamente com dados mock.
Não requer banco DuckDB nem conexão de API.

Executar: pytest tests/test_risk_engine.py -v
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch


# ── Testes dos indicadores individuais ────────────────────────

class TestIndicadorConcentracao:
    from src.risco.risk_engine import ind_concentracao

    def test_municipio_pequeno_valor_alto(self):
        from src.risco.risk_engine import ind_concentracao
        # R$5M em município de 5.000 hab → R$1.000/hab → deve ativar
        assert ind_concentracao(5_000_000, 5_000, "P") is True

    def test_municipio_grande_valor_normal(self):
        from src.risco.risk_engine import ind_concentracao
        # R$500k em Franca (365k hab) → R$1.37/hab → não ativa
        assert ind_concentracao(500_000, 365_000, "G") is False

    def test_municipio_pequeno_valor_baixo(self):
        from src.risco.risk_engine import ind_concentracao
        # R$50k em município de 5.000 hab → R$10/hab → não ativa
        assert ind_concentracao(50_000, 5_000, "P") is False

    def test_populacao_zero(self):
        from src.risco.risk_engine import ind_concentracao
        assert ind_concentracao(1_000_000, 0, "P") is False


class TestIndicadorPreEleitoral:
    def test_ano_eleitoral_periodo_critico(self):
        from src.risco.risk_engine import ind_pre_eleitoral
        assert ind_pre_eleitoral(2024, mes_emenda=6) is True

    def test_ano_eleitoral_fora_periodo(self):
        from src.risco.risk_engine import ind_pre_eleitoral
        assert ind_pre_eleitoral(2024, mes_emenda=1) is False

    def test_ano_nao_eleitoral(self):
        from src.risco.risk_engine import ind_pre_eleitoral
        assert ind_pre_eleitoral(2021, mes_emenda=7) is False

    def test_ano_eleitoral_2022(self):
        from src.risco.risk_engine import ind_pre_eleitoral
        assert ind_pre_eleitoral(2022, mes_emenda=9) is True


class TestCalculoEscore:
    def test_sem_indicadores(self):
        from src.risco.risk_engine import calcular_escore
        ind = {k: False for k in ["concentracao", "divergencia_objeto", "empresa_jovem",
                                   "doacao_parlamentar", "pre_eleitoral", "valor_anomalo",
                                   "campos_ausentes", "historico_sancoes", "pc_vencida"]}
        assert calcular_escore(ind) == 0.0

    def test_todos_indicadores(self):
        from src.risco.risk_engine import calcular_escore
        ind = {k: True for k in ["concentracao", "divergencia_objeto", "empresa_jovem",
                                   "doacao_parlamentar", "pre_eleitoral", "valor_anomalo",
                                   "campos_ausentes", "historico_sancoes", "pc_vencida"]}
        escore = calcular_escore(ind)
        assert abs(escore - 1.0) < 1e-6

    def test_escore_parcial(self):
        from src.risco.risk_engine import calcular_escore
        ind = {k: False for k in ["concentracao", "divergencia_objeto", "empresa_jovem",
                                   "doacao_parlamentar", "pre_eleitoral", "valor_anomalo",
                                   "campos_ausentes", "historico_sancoes", "pc_vencida"]}
        ind["concentracao"] = True   # 0.18
        ind["empresa_jovem"] = True  # 0.14
        escore = calcular_escore(ind)
        assert abs(escore - 0.32) < 1e-6

    def test_pesos_somam_um(self):
        from src.risco.risk_engine import PESOS
        assert abs(sum(PESOS.values()) - 1.0) < 1e-9


class TestConfirmacaoHumana:
    """Regra crítica: escore < 0.80 → requer_confirmacao_humana = True"""

    def test_escore_baixo_requer_confirmacao(self):
        from src.risco.risk_engine import calcular_escore
        ind = {k: False for k in ["concentracao", "divergencia_objeto", "empresa_jovem",
                                   "doacao_parlamentar", "pre_eleitoral", "valor_anomalo",
                                   "campos_ausentes", "historico_sancoes", "pc_vencida"]}
        ind["concentracao"] = True  # escore = 0.18
        escore = calcular_escore(ind)
        assert escore < 0.80  # deve exigir confirmação humana

    def test_escore_alto_nao_requer_confirmacao(self):
        from src.risco.risk_engine import calcular_escore
        ind = {k: True for k in ["concentracao", "divergencia_objeto", "empresa_jovem",
                                   "doacao_parlamentar", "pre_eleitoral", "valor_anomalo",
                                   "campos_ausentes", "historico_sancoes", "pc_vencida"]}
        escore = calcular_escore(ind)
        assert escore >= 0.80


class TestLinguagemAlertas:
    """Verifica que descrições nunca usam linguagem proibida."""

    PALAVRAS_PROIBIDAS = [
        "fraude", "desvio", "crime", "ilegalidade",
        "irregularidade confirmada", "corrupção", "superfaturamento"
    ]

    def test_descricao_sem_palavras_proibidas(self):
        from src.risco.risk_engine import _gerar_descricao
        ativados = ["concentracao", "empresa_jovem", "valor_anomalo"]
        descricao = _gerar_descricao(ativados, "Ituverava", "Dep. Teste", 500_000)
        descricao_lower = descricao.lower()
        for palavra in self.PALAVRAS_PROIBIDAS:
            assert palavra not in descricao_lower, (
                f"Palavra proibida '{palavra}' encontrada na descrição: {descricao}"
            )

    def test_descricao_vazia_sem_indicadores(self):
        from src.risco.risk_engine import _gerar_descricao
        descricao = _gerar_descricao([], "Franca", "Dep. X", 100_000)
        assert "Sem indicadores" in descricao
