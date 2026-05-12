"""
RADAR-EP — Motor de Risco Principal
=====================================
Fase 2 — Calcula os 9 indicadores de risco e o escore composto.

Indicadores e pesos (versão 1.0, mai/2026):
  1. concentracao       0.18  Concentração parlamentar em município pequeno
  2. divergencia_objeto 0.16  Divergência NLP entre objeto e natureza da emenda
  3. empresa_jovem      0.14  Empresa favorecida com < 24 meses
  4. doacao_parlamentar 0.14  Empresa doou para campanha do parlamentar
  5. pre_eleitoral      0.12  Emenda emitida em ano eleitoral (<6 meses antes)
  6. valor_anomalo      0.10  Valor outlier (z-score > 2.5 no histórico)
  7. campos_ausentes    0.08  Campos obrigatórios ausentes no Portal da Transparência
  8. historico_sancoes  0.04  Empresa no CEIS ou CNEP
  9. pc_vencida         0.04  Prestação de contas vencida há > 30 dias
"""

import logging
import os
from datetime import date
from typing import Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

# ── Pesos dos indicadores ──────────────────────────────────────
PESOS: dict[str, float] = {
    "concentracao":       0.18,
    "divergencia_objeto": 0.16,
    "empresa_jovem":      0.14,
    "doacao_parlamentar": 0.14,
    "pre_eleitoral":      0.12,
    "valor_anomalo":      0.10,
    "campos_ausentes":    0.08,
    "historico_sancoes":  0.04,
    "pc_vencida":         0.04,
}
assert abs(sum(PESOS.values()) - 1.0) < 1e-9, "Pesos devem somar 1.0"

# Anos eleitorais no Brasil (municipais e federais)
ANOS_ELEITORAIS = {2022, 2024, 2026, 2028}

# Porte de município — limiar de concentração (R$ por habitante/ano)
LIMIAR_CONCENTRACAO_POR_HABITANTE = 50.0  # R$50/hab → flag


def calcular_escore(indicadores: dict) -> float:
    """
    Calcula o escore composto de risco (0.0 a 1.0).

    Args:
        indicadores: dict com chaves iguais às de PESOS e valores booleanos

    Returns:
        float entre 0.0 e 1.0
    """
    return round(
        sum(PESOS[k] * (1.0 if v else 0.0)
            for k, v in indicadores.items() if k in PESOS),
        4,
    )


# ── Indicador 1: Concentração parlamentar ─────────────────────
def ind_concentracao(
    valor_empenhado: float,
    populacao: int,
    porte: str,
) -> bool:
    """
    Retorna True se o valor por habitante superar o limiar,
    especialmente crítico para municípios pequenos.
    """
    if populacao <= 0:
        return False
    valor_por_hab = valor_empenhado / populacao
    multiplicador = 1.0 if porte == "G" else (1.5 if porte == "M" else 2.5)
    return valor_por_hab > (LIMIAR_CONCENTRACAO_POR_HABITANTE * multiplicador)


# ── Indicador 2: Divergência de objeto (NLP) ──────────────────
def ind_divergencia_objeto(
    objeto_convenio: str,
    nome_funcao: str,
    limiar_similaridade: float = 0.40,
    db_path: str = "radar_ep.duckdb",
) -> bool:
    """
    Usa NLP (Sentence-Transformers) para verificar se o objeto do convênio
    é semanticamente divergente da função orçamentária.

    Retorna True (flag) se a similaridade for MENOR que o limiar.
    """
    if not objeto_convenio or not nome_funcao:
        return False
    try:
        from src.risco.nlp_similarity import calcular_similaridade_objeto
        sim = calcular_similaridade_objeto(objeto_convenio, nome_funcao)
        return sim < limiar_similaridade
    except ImportError:
        logger.warning("sentence-transformers não disponível — indicador 2 ignorado")
        return False
    except Exception as e:
        logger.error("Erro no indicador de divergência: %s", e)
        return False


# ── Indicador 3: Empresa jovem ─────────────────────────────────
def ind_empresa_jovem(
    cnpj: str,
    data_emenda: Optional[date] = None,
    db_path: str = "radar_ep.duckdb",
) -> bool:
    """
    Retorna True se a empresa tiver menos de 24 meses na data da emenda.
    Usa cache DuckDB para evitar chamadas repetidas à BrasilAPI.
    """
    try:
        from src.ingestao.cnpj_checker import verificar_idade_empresa
        resultado = verificar_idade_empresa(cnpj, data_emenda, db_path)
        return resultado.get("flag_jovem", False)
    except Exception as e:
        logger.error("Erro ao verificar empresa jovem (CNPJ=%s): %s", cnpj, e)
        return False


# ── Indicador 4: Doação ao parlamentar ────────────────────────
def ind_doacao_parlamentar(
    cnpj_favorecido: str,
    codigo_parlamentar: str,
    con: duckdb.DuckDBPyConnection,
) -> bool:
    """
    Verifica se o favorecido (empresa) fez doação ao parlamentar autor da emenda.
    Requer tabela 'doacoes_tse' carregada via BigQuery (Base dos Dados).
    """
    try:
        result = con.execute("""
            SELECT COUNT(*) FROM doacoes_tse
            WHERE cpf_cnpj_doador = ?
              AND codigo_parlamentar = ?
        """, [cnpj_favorecido, codigo_parlamentar]).fetchone()
        return (result[0] or 0) > 0
    except Exception:
        # Tabela doacoes_tse pode não existir ainda
        return False


# ── Indicador 5: Período pré-eleitoral ────────────────────────
def ind_pre_eleitoral(ano_emenda: int, mes_emenda: int = 6) -> bool:
    """
    Retorna True se a emenda foi empenhada em ano eleitoral,
    especialmente nos 6 meses anteriores à eleição (abr-out).
    """
    if ano_emenda not in ANOS_ELEITORAIS:
        return False
    # Eleições municipais: outubro. Federais: outubro também.
    # Período crítico: abril a outubro do ano eleitoral
    return 4 <= mes_emenda <= 10


# ── Indicador 6: Valor anômalo ────────────────────────────────
def ind_valor_anomalo(
    valor: float,
    ibge: str,
    nome_funcao: str,
    con: duckdb.DuckDBPyConnection,
    z_score_limiar: float = 2.5,
) -> bool:
    """
    Calcula z-score do valor em relação ao histórico do município e função.
    Retorna True se o z-score superar o limiar (outlier estatístico).
    """
    try:
        stats = con.execute("""
            SELECT
                AVG("Valor Empenhado") AS media,
                STDDEV("Valor Empenhado") AS dp
            FROM emendas_parlamentares
            WHERE "Código Município IBGE" = ?
              AND "Nome Função" = ?
        """, [ibge, nome_funcao]).fetchone()

        if not stats or stats[1] is None or stats[1] == 0:
            return False

        media, dp = stats
        z = abs(valor - media) / dp
        return z > z_score_limiar

    except Exception as e:
        logger.error("Erro no indicador valor_anomalo: %s", e)
        return False


# ── Indicador 7: Campos obrigatórios ausentes ─────────────────
def ind_campos_ausentes(
    codigo_emenda: str,
    chave_api: Optional[str] = None,
) -> bool:
    """
    Verifica se campos obrigatórios estão ausentes no Portal da Transparência.
    """
    try:
        from src.ingestao.portal_api import verificar_campos_obrigatorios
        resultado = verificar_campos_obrigatorios(
            codigo_emenda, chave_api or os.getenv("PORTAL_TRANSPARENCIA_KEY")
        )
        return resultado.get("flag_incompleto", False)
    except Exception as e:
        logger.error("Erro no indicador campos_ausentes: %s", e)
        return False


# ── Indicador 8: Histórico de sanções ────────────────────────
def ind_historico_sancoes(
    cnpj: str,
    con: duckdb.DuckDBPyConnection,
) -> bool:
    """
    Verifica se o CNPJ consta no CEIS ou CNEP (tabela sancoes_ceis).
    """
    try:
        cnpj_limpo = "".join(c for c in str(cnpj) if c.isdigit())
        result = con.execute("""
            SELECT COUNT(*) FROM sancoes_ceis
            WHERE REGEXP_REPLACE(cnpj_cpf, '[^0-9]', '') = ?
              AND (data_fim IS NULL OR data_fim >= current_date)
        """, [cnpj_limpo]).fetchone()
        return (result[0] or 0) > 0
    except Exception:
        return False


# ── Indicador 9: Prestação de contas vencida ─────────────────
def ind_pc_vencida(
    codigo_emenda: str,
    ibge: str,
    dias_tolerancia: int = 30,
) -> bool:
    """
    Verifica via Transferegov se há PC vencida para a emenda/município.
    """
    try:
        from src.ingestao.transferegov_api import verificar_pc_vencida
        vencidas = verificar_pc_vencida([ibge], dias_tolerancia)
        for item in vencidas:
            if str(item.get("codigo_emenda", "")) == str(codigo_emenda):
                return True
        return len(vencidas) > 0 and codigo_emenda == ""  # flag geral por município
    except Exception as e:
        logger.error("Erro no indicador pc_vencida: %s", e)
        return False


# ── Avaliação completa de uma emenda ──────────────────────────
def avaliar_emenda(
    emenda: dict,
    con: duckdb.DuckDBPyConnection,
    chave_api: Optional[str] = None,
    avaliar_cnpj: bool = True,
    avaliar_nlp: bool = False,
    avaliar_portal: bool = False,
) -> dict:
    """
    Avalia todos os indicadores para uma emenda e retorna o escore composto.

    Args:
        emenda: dict com dados da emenda (colunas do CSV ou BigQuery)
        con: conexão DuckDB
        chave_api: chave Portal da Transparência (opcional)
        avaliar_cnpj: se False, pula verificação BrasilAPI (mais rápido)
        avaliar_nlp: se False, pula NLP (mais rápido)
        avaliar_portal: se False, pula verificação Portal da Transparência

    Returns:
        dict com indicadores, escore, descricao e requer_confirmacao_humana
    """
    # Normalizar campos
    codigo_emenda = str(emenda.get("Código da Emenda", emenda.get("codigo_emenda", "")))
    ibge = str(emenda.get("Código Município IBGE", emenda.get("codigo_municipio_ibge", "")))
    municipio = emenda.get("Município", emenda.get("municipio", ""))
    parlamentar = emenda.get("Nome do Autor da Emenda", emenda.get("nome_autor", ""))
    cod_parlamentar = str(emenda.get("Código do Autor da Emenda", emenda.get("codigo_autor", "")))
    nome_funcao = emenda.get("Nome Função", emenda.get("nome_funcao", ""))
    tipo_emenda = emenda.get("Tipo de Emenda", emenda.get("tipo_emenda", ""))
    objeto = emenda.get("Objeto Convênio", "")
    cnpj_fav = str(emenda.get("Código do Favorecido", emenda.get("cnpj_favorecido", "")))

    # Valor empenhado
    try:
        val_raw = emenda.get("Valor Empenhado", emenda.get("valor_empenhado", 0))
        if isinstance(val_raw, (int, float)):
            valor = float(val_raw)
        else:
            val_str = str(val_raw)
            valor = float(val_str.replace(".", "").replace(",", "."))
    except Exception:
        valor = 0.0

    # Ano/mês
    try:
        ano = int(emenda.get("Ano da Emenda", emenda.get("ano", 0)))
    except Exception:
        ano = 0

    # Dados do município
    mun_info = con.execute(
        "SELECT populacao, porte FROM municipios_franca WHERE ibge = ?", [ibge]
    ).fetchone()
    populacao = mun_info[0] if mun_info else 50000
    porte = mun_info[1] if mun_info else "P"

    # ── Calcular indicadores ──────────────────────────────────
    indicadores = {
        "concentracao":       ind_concentracao(valor, populacao, porte),
        "divergencia_objeto": ind_divergencia_objeto(objeto, nome_funcao) if avaliar_nlp else False,
        "empresa_jovem":      ind_empresa_jovem(cnpj_fav, db_path=con.database) if (avaliar_cnpj and cnpj_fav and len(cnpj_fav) >= 11) else False,
        "doacao_parlamentar": ind_doacao_parlamentar(cnpj_fav, cod_parlamentar, con),
        "pre_eleitoral":      ind_pre_eleitoral(ano),
        "valor_anomalo":      ind_valor_anomalo(valor, ibge, nome_funcao, con),
        "campos_ausentes":    ind_campos_ausentes(codigo_emenda, chave_api) if avaliar_portal else False,
        "historico_sancoes":  ind_historico_sancoes(cnpj_fav, con),
        "pc_vencida":         ind_pc_vencida(codigo_emenda, ibge) if avaliar_portal else False,
    }

    escore = calcular_escore(indicadores)
    ativados = [k for k, v in indicadores.items() if v]

    # Gerar descrição em linguagem condicional — via IA se disponível
    descricao = _gerar_descricao_com_ia(
        ativados, municipio, parlamentar, valor, escore, ano
    )

    return {
        "codigo_emenda": codigo_emenda,
        "ibge": ibge,
        "municipio": municipio,
        "parlamentar": parlamentar,
        "codigo_parlamentar": cod_parlamentar,
        "tipo_emenda": tipo_emenda,
        "ano_emenda": ano,
        "valor_emenda": valor,
        "indicadores": indicadores,
        "indicadores_ativados": ativados,
        "escore": escore,
        "descricao": descricao,
        "requer_confirmacao_humana": escore < 0.80,
    }


def _gerar_descricao(ativados: list, municipio: str, parlamentar: str, valor: float) -> str:
    """Gera descrição em linguagem condicional obrigatória (NUNCA afirma fraude)."""
    if not ativados:
        return "Sem indicadores de risco ativados."

    descricoes = {
        "concentracao":       "concentração elevada de recursos em município de pequeno porte",
        "divergencia_objeto": "divergência entre o objeto do convênio e a natureza da emenda",
        "empresa_jovem":      "empresa favorecida com menos de 24 meses de constituição",
        "doacao_parlamentar": "relação entre favorecido e doação de campanha ao parlamentar autor",
        "pre_eleitoral":      "emenda empenhada em período próximo a eleições",
        "valor_anomalo":      "valor que se afasta do padrão histórico do município",
        "campos_ausentes":    "campos obrigatórios ausentes no Portal da Transparência",
        "historico_sancoes":  "favorecido com histórico de sanções (CEIS/CNEP)",
        "pc_vencida":         "prestação de contas com prazo vencido",
    }
    partes = [descricoes[ind] for ind in ativados if ind in descricoes]
    lista = "; ".join(partes)
    return (
        f"Padrão atípico que merece verificação em emenda de R$ {valor:,.2f} "
        f"para {municipio} (parlamentar: {parlamentar}): {lista}. "
        f"Indício a verificar — não constitui confirmação de irregularidade."
    )


def _gerar_descricao_com_ia(
    ativados: list,
    municipio: str,
    parlamentar: str,
    valor: float,
    escore: float,
    ano: int,
) -> str:
    """
    Tenta gerar narrativa via IA (Gemini/Claude).
    Em caso de falha ou sem ativados, usa descrição local.
    """
    if not ativados:
        return "Sem indicadores de risco ativados."

    # Fallback imediato se IA não disponível
    try:
        from src.ai_provider import gerar_narrativa_alerta
        return gerar_narrativa_alerta({
            "indicadores_ativados": ativados,
            "municipio": municipio,
            "parlamentar": parlamentar,
            "valor_emenda": valor,
            "escore": escore,
            "ano_emenda": ano,
        })
    except Exception as e:
        logger.warning("IA indisponível, usando descrição local: %s", e)
        return _gerar_descricao(ativados, municipio, parlamentar, valor)



# ── Processamento em lote ─────────────────────────────────────
def processar_lote(
    df: pd.DataFrame,
    db_path: str = "radar_ep.duckdb",
    chave_api: Optional[str] = None,
    avaliar_cnpj: bool = True,
    avaliar_nlp: bool = False,
    avaliar_portal: bool = False,
    escore_minimo: float = 0.0,
) -> pd.DataFrame:
    """
    Processa um DataFrame de emendas e retorna resultados de risco.
    """
    con = duckdb.connect(db_path)
    resultados = []

    for _, row in df.iterrows():
        try:
            resultado = avaliar_emenda(
                row.to_dict(), con, chave_api,
                avaliar_cnpj, avaliar_nlp, avaliar_portal
            )
            if resultado["escore"] >= escore_minimo:
                resultados.append(resultado)
        except Exception as e:
            logger.error("Erro ao avaliar emenda %s: %s",
                         row.get("Código da Emenda", "?"), e)

    con.close()
    logger.info("Processadas %d emendas, %d com escore >= %.2f",
                len(df), len(resultados), escore_minimo)
    return pd.DataFrame(resultados) if resultados else pd.DataFrame()
