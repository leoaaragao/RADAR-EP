# Manual do Usuário — RADAR-EP

> Sistema de Rastreamento Analítico e Detecção de Anomalias em Recursos de Emendas Parlamentares
> **Versão 1.0 | Maio/2026 | 13ª SJ MPF Franca/SP**

---

## Início Rápido

### 1. Pré-requisitos

- Python 3.11+
- Os 3 arquivos CSV na pasta `data/` (baixados do Portal da Transparência/CGU)
- Chaves de API configuradas no arquivo `.env`

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

**Pacotes principais instalados:**

| Pacote | Função |
|--------|--------|
| `streamlit` | Dashboard interativo |
| `duckdb` | Banco de dados local |
| `basedosdados` | Acesso ao BigQuery via Base dos Dados |
| `httpx` + `tenacity` | Chamadas HTTP com retry automático |
| `anthropic` | IA Claude para narrativas |
| `google-genai` | IA Gemini (alternativa) |
| `scikit-learn` | Cálculos estatísticos (z-score) |

### 3. Carga inicial de dados (CSV locais)

```bash
python scripts/setup_db.py
```

Este script:
- Cria o banco `radar_ep.duckdb`
- Carrega os 3 CSVs (~946 MB total) — pode levar 2-5 minutos
- Cria tabelas de estrutura (municipios_franca, alertas, cnpj_cache, sancoes_ceis)
- Cria views normalizadas (v_emendas_valores, v_favorecido_valores)

### 4. Carga histórica via BigQuery (opcional, recomendado)

Carrega o histórico completo 2013-2026 diretamente da Base dos Dados:

```bash
python src/ingestao/bigquery_loader.py --ano-inicio 2020
```

**Pré-requisitos:**
1. Conta Google com acesso ao projeto `nice-stack-440319-c6`
2. `GCP_PROJECT_ID=nice-stack-440319-c6` no `.env`
3. Na primeira execução, o browser abrirá para autenticação OAuth

**Tabela consultada:** `basedosdados.br_cgu_emendas_parlamentares.microdados`
- Organização: CGU | Cobertura: 2013-2026 | Atualização: a cada 15 dias
- Colunas carregadas: 25 campos (identificação, classificação orçamentária e valores financeiros completos)

### 5. Executar análise de risco (Pipeline)

```bash
# Modo Completo (requer APIs configuradas no .env)
python scripts/run_risk_pipeline.py

# Modo Rápido (apenas dados locais — sem chamadas externas)
python scripts/run_risk_pipeline.py --sem-cnpj --sem-portal --sem-nlp

# Opções disponíveis:
#   --ano-inicio 2022    → processar apenas emendas a partir de 2022
#   --escore-min 0.30    → salvar alertas com escore >= 0.30 (padrão: 0.20)
#   --limite 5000        → processar no máximo 5.000 emendas
```

### 6. Visualização no Dashboard

```bash
streamlit run src/dashboard.py
```

Acesse em: http://localhost:8501

### 7. API de Integração (FastAPI)

```bash
uvicorn src.api:app --reload --port 8000
```

Documentação interativa: http://localhost:8000/docs

---

## Sincronização e Manutenção

### Sincronização Diária

Busca dados novos do Portal da Transparência e Transferegov:

```bash
python scripts/sync_diario.py
```

Recomenda-se agendar via Windows Task Scheduler para execução diária (ex: 07h00).

### Atualização BigQuery

A Base dos Dados atualiza a tabela de emendas a cada 15 dias. Para sincronizar:

```bash
python src/ingestao/bigquery_loader.py --ano-inicio 2024
```

---

## Configuração de APIs (arquivo `.env`)

```env
# Portal da Transparência (CGU)
PORTAL_TRANSPARENCIA_KEY=sua_chave_aqui

# BigQuery / Base dos Dados
GCP_PROJECT_ID=nice-stack-440319-c6

# IA Generativa (escolha UMA):
ANTHROPIC_API_KEY=sua_chave_claude_aqui
# GOOGLE_API_KEY=sua_chave_gemini_aqui

# Banco de dados (padrão)
DUCKDB_PATH=radar_ep.duckdb
DATA_DIR=data
```

### Como obter as chaves

| API | Onde obter |
|-----|------------|
| Portal da Transparência | portaldatransparencia.gov.br → Acesso à API |
| Google Gemini | aistudio.google.com/apikey → projeto nice-stack-440319-c6 |
| Anthropic Claude | console.anthropic.com → API Keys |

---

## Regras de Uso e Compliance

### Linguagem Condicional (obrigatória)

Conforme diretrizes do MPF e LC 210/2024, os alertas do sistema **NUNCA** devem afirmar categoricamente a existência de fraude ou irregularidade. Use sempre linguagem condicional:

| Proibido | Use em vez disso |
|----------|-----------------|
| "fraude confirmada" | "padrão atípico que merece verificação" |
| "desvio de recursos" | "indício a verificar" |
| "corrupção" | "apresenta características que se afastam do padrão" |
| "ilegalidade" | "requer conferência documental" |

### Confirmação Humana

Alertas com **escore abaixo de 0.80** possuem `requer_confirmacao_humana = True`. O analista deve revisar e classificar o alerta no dashboard antes de qualquer ação.

### Privacidade (LGPD)

CPFs e dados pessoais são mascarados na camada de visualização. Dados completos disponíveis apenas em endpoints autenticados com token MPF.

### Verificações LC 210/2024 (obrigatórias)

- Plano de trabalho presente antes do empenho
- Conta-corrente específica por emenda (`endpoint executor_especial`)
- Pagamentos exclusivamente eletrônicos (vedação saques desde mar/2026)
- Ausência de parentes do parlamentar em OSCs beneficiadas (jan/2026)

---

## Indicadores de Risco (9 Indicadores — Pesos v1.0)

| # | Indicador | Sigla | Peso | Fonte |
|---|-----------|-------|------|-------|
| 1 | Concentração Parlamentar em município pequeno | `concentracao` | 18% | CSV local |
| 2 | Divergência de Objeto vs. Função (NLP) | `divergencia_objeto` | 16% | CSV + Sentence-Transformers |
| 3 | Empresa Favorecida com menos de 24 meses | `empresa_jovem` | 14% | BrasilAPI |
| 4 | Doação de Campanha ao Parlamentar autor | `doacao_parlamentar` | 14% | Base dos Dados (TSE) |
| 5 | Emenda em Período Pré-Eleitoral | `pre_eleitoral` | 12% | CSV local |
| 6 | Valor Anômalo (z-score > 2.5) | `valor_anomalo` | 10% | DuckDB stats |
| 7 | Campos Obrigatórios Ausentes no Portal | `campos_ausentes` | 8% | Portal da Transparência |
| 8 | Histórico de Sanções CEIS/CNEP | `historico_sancoes` | 4% | CSV mensal CGU |
| 9 | Prestação de Contas Vencida | `pc_vencida` | 4% | Transferegov.br |

**Escore = soma ponderada dos indicadores ativados (0.0 a 1.0)**

---

## Municípios Monitorados (13ª SJ Franca/SP)

| Município | IBGE | Pop. | Porte |
|-----------|------|------|-------|
| Franca | 3516200 | 365.494 | G |
| São Joaquim da Barra | 3549409 | 49.885 | M |
| Ituverava | 3524105 | 38.413 | M |
| Igarapava | 3520103 | 26.696 | M |
| Guará | 3517703 | 18.748 | P |
| Ipuã | 3521309 | 15.900 | P |
| Pedregulho | 3537008 | 15.600 | P |
| Patrocínio Paulista | 3536307 | 14.529 | P |
| São José da Bela Vista | 3549508 | 8.895 | P |
| Cristais Paulista | 3513207 | 8.200 | P |
| Restinga | 3542701 | 7.504 | P |
| Itirapuã | 3523701 | 6.453 | P |
| Aramina | 3503000 | 5.535 | P |
| Ribeirão Corrente | 3543105 | 4.682 | P |
| Buritizal | 3508207 | 4.458 | P |
| Rifaina | 3543600 | 4.179 | P |
| Jeriquara | 3525409 | 4.000 | P |

*Porte: G=Grande, M=Médio, P=Pequeno*

---

## Fontes de Dados

| Fonte | Endpoint/Tabela | Autenticação |
|-------|----------------|-------------|
| Base dos Dados (BigQuery) | `basedosdados.br_cgu_emendas_parlamentares.microdados` | OAuth Google |
| Portal da Transparência | `api.portaldatransparencia.gov.br/api-de-dados/emendas` | `chave-api-dados` (header) |
| Transferegov.br | `api.transferegov.gestao.gov.br/transferenciasespeciais` | Pública (PostgREST) |
| BrasilAPI | `brasilapi.com.br/api/cnpj/v1/{cnpj}` | Pública |

---

*RADAR-EP v1.0 | 13ª SJ MPF Franca/SP | Uso interno restrito | LGPD aplicável*
