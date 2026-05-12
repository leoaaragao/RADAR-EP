"""
RADAR-EP — Suporte a múltiplos provedores de IA
=================================================
Abstrai Google Gemini e Anthropic Claude.
Provedor ativo é determinado automaticamente pelo .env:
  - GOOGLE_API_KEY  → usa Gemini (preferido)
  - ANTHROPIC_API_KEY → usa Claude (fallback)
"""

import os
import logging

logger = logging.getLogger(__name__)

# Modelo Gemini padrão
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _usar_gemini() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY"))


def _get_gemini_client():
    """Retorna cliente Gemini configurado."""
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    return genai.GenerativeModel(_GEMINI_MODEL)


def gerar_sql(pergunta: str, schema: str) -> str:
    """Converte pergunta em linguagem natural para SQL DuckDB."""
    prompt = f"""Converta a pergunta abaixo em SQL válido para DuckDB.

Schema disponível:
{schema}

REGRAS OBRIGATÓRIAS:
- Responda APENAS com SQL puro, sem markdown (sem ```) e sem explicação
- Colunas com espaços: usar aspas duplas ex: "Valor Empenhado"
- Valores monetários: TRY_CAST(REPLACE(REPLACE("Valor Empenhado",'.',''),',','.') AS DOUBLE)
- CPFs mascarados: REGEXP_REPLACE(col, '[0-9]{{3}}\\.[0-9]{{3}}\\.', '***.***.') 
- Sempre incluir LIMIT 100

Pergunta: {pergunta}"""

    return _chamar_ia(prompt, max_tokens=600)


def gerar_narrativa(pergunta: str, resultado_str: str) -> str:
    """Gera narrativa analítica em PT-BR sobre resultado de consulta."""
    prompt = f"""Você é um analista do MPF. Interprete o resultado abaixo para o analista.

Pergunta feita: {pergunta}

Resultado da consulta SQL:
{resultado_str}

INSTRUÇÕES:
- Redija um parágrafo em português (máx 150 palavras)
- Linguagem CONDICIONAL e factual: "padrão atípico", "indício a verificar", "merece análise"
- PROIBIDO: fraude, desvio, crime, irregularidade confirmada, ilegalidade
- Mencione valores, municípios e parlamentares relevantes encontrados nos dados"""

    return _chamar_ia(prompt, max_tokens=300)


def gerar_narrativa_alerta(resultado_avaliacao: dict) -> str:
    """Gera narrativa de alerta em linguagem condicional com base nos indicadores ativados."""
    indicadores = resultado_avaliacao.get("indicadores_ativados", [])
    municipio = resultado_avaliacao.get("municipio", "?")
    parlamentar = resultado_avaliacao.get("parlamentar", "?")
    valor = resultado_avaliacao.get("valor_emenda", 0)
    escore = resultado_avaliacao.get("escore", 0)
    ano = resultado_avaliacao.get("ano_emenda", "?")

    desc_indicadores = {
        "concentracao":       "concentração elevada de recursos em município de pequeno porte",
        "divergencia_objeto": "divergência semântica entre objeto do convênio e função orçamentária",
        "empresa_jovem":      "empresa beneficiária com menos de 24 meses de constituição",
        "doacao_parlamentar": "empresa beneficiária com histórico de doação ao parlamentar autor",
        "pre_eleitoral":      "emenda empenhada em ano e período eleitoral",
        "valor_anomalo":      "valor que supera 2,5 desvios-padrão do histórico do município",
        "campos_ausentes":    "campos obrigatórios ausentes no Portal da Transparência",
        "historico_sancoes":  "beneficiário com registro no CEIS ou CNEP",
        "pc_vencida":         "prestação de contas com prazo vencido há mais de 30 dias",
    }

    lista_desc = [desc_indicadores.get(ind, ind) for ind in indicadores]

    prompt = f"""Você é um analista de controle do MPF (Ministério Público Federal).
Redija um alerta analítico (máx 120 palavras) sobre a seguinte emenda parlamentar:

- Município: {municipio}
- Parlamentar autor: {parlamentar}
- Ano: {ano}
- Valor: R$ {valor:,.2f}
- Escore de risco: {escore:.2f}/1.00
- Indicadores ativados: {', '.join(lista_desc) if lista_desc else 'nenhum'}

REGRAS INVIOLÁVEIS:
1. Linguagem sempre condicional: "apresenta características", "merece verificação", "indício a conferir"
2. NUNCA afirmar: fraude, desvio, crime, irregularidade, ilegalidade
3. Finalizar com: "Este alerta requer conferência documental antes de qualquer conclusão."
4. Redija em português formal, terceira pessoa"""

    return _chamar_ia(prompt, max_tokens=250)


def _chamar_ia(prompt: str, max_tokens: int = 400) -> str:
    """Chama o provedor de IA disponível."""
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("IA desativada: chaves ausentes")

    if _usar_gemini():
        return _gemini_request(prompt, max_tokens)
    else:
        return _anthropic_request(prompt, max_tokens)


def _gemini_request(prompt: str, max_tokens: int = 400) -> str:
    """Chama Google Gemini API (novo SDK google-genai 2.x)."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,
            ),
        )
        return response.text.strip()
    except ImportError:
        raise RuntimeError("google-genai não instalado: pip install google-genai")
    except Exception as e:
        logger.error("Erro Gemini: %s", e)
        raise


def _anthropic_request(prompt: str, max_tokens: int = 400) -> str:
    """Chama Anthropic Claude API (fallback)."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except ImportError:
        raise RuntimeError("anthropic não instalado: pip install anthropic")
    except Exception as e:
        logger.error("Erro Anthropic: %s", e)
        raise


def testar_conexao() -> dict:
    """Testa se a IA está respondendo."""
    try:
        resp = _chamar_ia("Responda apenas: OK", max_tokens=10)
        return {"status": "ok", "provedor": "gemini" if _usar_gemini() else "anthropic",
                "modelo": _GEMINI_MODEL if _usar_gemini() else "claude-sonnet-4-5",
                "resposta": resp}
    except Exception as e:
        return {"status": "erro", "detalhe": str(e)}


def prover_disponivel() -> dict:
    return {
        "gemini": bool(os.getenv("GOOGLE_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "ativo": "gemini" if _usar_gemini() else ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else None),
        "modelo": _GEMINI_MODEL if _usar_gemini() else "claude-sonnet-4-5",
    }
