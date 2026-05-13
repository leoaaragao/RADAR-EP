# 📡 RADAR-EP

**Sistema de Rastreamento Analítico e Detecção de Anomalias em Recursos de Emendas Parlamentares**

> Projeto Piloto — 13ª Subseção Judiciária do MPF — Franca/SP | Versão 1.0 | Maio/2026

---

## 🎯 O que é o RADAR-EP?

O RADAR-EP monitora emendas parlamentares executadas nos **17 municípios** da área de atribuição da 13ª SJ Franca/SP, combinando dados de 3 fontes locais (CSV), 4 APIs governamentais e IA generativa para:

- Calcular **escores de risco** por emenda (9 indicadores, pesos calibrados)
- Gerar **alertas automáticos** com linguagem condicional (LC 210/2024)
- Exibir um **dashboard interativo** com mapa, KPIs e gráficos
- Responder **perguntas em linguagem natural** via NL→SQL (Claude/Gemini)
- Prover uma **API REST** para integração com outros sistemas MPF

---

## 🗂️ Estrutura do Projeto

```
RADAR EP (Py)/
├── .env                         # 🔐 Credenciais (NÃO versionar)
├── .env.example                 # Template público
├── .gitignore
├── requirements.txt
├── CLAUDE.md                    # Contexto normativo para agentes IA
├── radar_ep.duckdb              # Banco local (gerado pelos scripts)
│
├── data/                        # 📂 Dados brutos (não versionar)
│   ├── EmendasParlamentares.csv            (46 MB, 92.756 linhas)
│   ├── EmendasParlamentares_Convenios.csv  (24 MB, 81.977 linhas)
│   └── EmendasParlamentares_PorFavorecido.csv (169 MB, 772.371 linhas)
│
├── src/
│   ├── ingestao/
│   │   ├── bigquery_loader.py   # Carga via Base dos Dados (BigQuery)
│   │   ├── portal_api.py        # Portal da Transparência (CGU)
│   │   ├── transferegov_api.py  # Transferegov.br
│   │   └── cnpj_checker.py      # BrasilAPI / Receita Federal
│   ├── risco/
│   │   ├── risk_engine.py       # 9 indicadores + escore composto
│   │   ├── nlp_similarity.py    # Divergência NLP (Sentence-Transformers)
│   │   └── alerta_writer.py     # Persistência e classificação de alertas
│   ├── ai_provider.py           # Abstração Claude / Gemini
│   ├── dashboard.py             # Interface Streamlit
│   └── api.py                   # API REST FastAPI
│
├── scripts/
│   ├── setup_db.py              # Cria banco e carrega CSVs
│   └── run_risk_pipeline.py     # Executa análise de risco
│
├── prompts/
│   ├── narrativa_alerta.md      # Prompt para narrativas
│   └── sql_query.md             # Prompt para NL→SQL
│
└── tests/
    ├── test_risk_engine.py      # Testes dos indicadores
    └── test_api.py              # Testes dos endpoints
```

---

## ⚡ Início Rápido

### 1. Pré-requisitos
- Python 3.11+
- Os 3 CSVs na pasta `data/`
- Chave do Portal da Transparência (já configurada no `.env`)

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Criar o banco de dados
```bash
python scripts/setup_db.py
```
> Isso carrega os 3 CSVs (~946 MB total) no DuckDB. Pode levar 2–5 minutos.

### 4. Executar análise de risco
```bash
# Modo rápido (sem BrasilAPI, sem Portal, sem NLP):
python scripts/run_risk_pipeline.py --sem-cnpj --sem-portal --sem-nlp

# Modo completo (requer chaves de API):
python scripts/run_risk_pipeline.py
```

### 5. Abrir o dashboard
```bash
streamlit run src/dashboard.py
```
> Acesse em: http://localhost:8501

### 6. Iniciar a API REST (opcional)
```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000
```
> Documentação automática: http://localhost:8000/docs

---

## 🔑 Configuração de APIs

### Arquivo `.env` (já criado)

```env
# Portal da Transparência (CGU) — CONFIGURADO ✅
PORTAL_TRANSPARENCIA_KEY=4b2b8fb73f25493279cdf11345ea8009

# BigQuery / Base dos Dados — CONFIGURADO ✅
GCP_PROJECT_ID=nice-stack-440319-c6

# IA Generativa — escolha UMA das opções abaixo:

# Opção A: Anthropic Claude
ANTHROPIC_API_KEY=sua_chave_claude_aqui

# Opção B: Google Gemini (mesma conta GCP — mais simples)
# GOOGLE_API_KEY=sua_chave_gemini_aqui
```

### Como obter a chave do Google Gemini (recomendado)
1. Acesse: https://aistudio.google.com/apikey
2. Clique em "Create API Key"
3. Selecione o projeto `nice-stack-440319-c6`
4. Copie a chave e cole no `.env` como `GOOGLE_API_KEY=...`
5. Descomente a linha `GOOGLE_API_KEY=` e comente `ANTHROPIC_API_KEY=`

### Autenticação BigQuery (Base dos Dados)
```bash
python src/ingestao/bigquery_loader.py
```
> Na primeira execução, abrirá o browser para login OAuth com sua conta Google.

---

## 📊 Os 9 Indicadores de Risco

| # | Indicador | Peso | Fonte |
|---|-----------|------|-------|
| 1 | Concentração parlamentar em município pequeno | **0.18** | CSV local |
| 2 | Divergência objeto × função (NLP) | **0.16** | CSV + Sentence-Transformers |
| 3 | Empresa favorecida com < 24 meses | **0.14** | BrasilAPI |
| 4 | Empresa doou para campanha do parlamentar | **0.14** | Base dos Dados (TSE) |
| 5 | Emenda em período pré-eleitoral | **0.12** | CSV local |
| 6 | Valor anômalo (z-score > 2.5) | **0.10** | CSV local |
| 7 | Campos obrigatórios ausentes | **0.08** | Portal da Transparência |
| 8 | Histórico de sanções (CEIS/CNEP) | **0.04** | CSV mensal CGU |
| 9 | Prestação de contas vencida | **0.04** | Transferegov |

**Escore = soma ponderada dos indicadores ativados (0.0 a 1.0)**

---

## ⚖️ Regras de Conformidade (OBRIGATÓRIAS)

| Regra | Detalhes |
|-------|----------|
| **Linguagem condicional** | Nunca usar: fraude, desvio, crime, ilegalidade. Sempre usar: padrão atípico, indício a verificar |
| **Confirmação humana** | Alertas com escore < 0.80 exigem `requer_confirmacao_humana=true` |
| **LGPD** | CPFs mascarados no frontend (`***.***.***-**`) |
| **LC 210/2024** | Verificar plano de trabalho, conta específica, pagamento eletrônico |
| **Retroalimentação** | Analistas classificam alertas → recalibração trimestral dos pesos |

---

## 🗺️ Municípios Monitorados

| Município | IBGE | Pop. | Porte |
|-----------|------|------|-------|
| Franca | 3516200 | 365.494 | Grande |
| São Joaquim da Barra | 3549409 | 49.885 | Médio |
| Ituverava | 3524105 | 38.413 | Médio |
| Igarapava | 3520103 | 26.696 | Médio |
| Guará | 3517703 | 18.748 | Pequeno |
| Ipuã | 3521309 | 15.900 | Pequeno |
| Pedregulho | 3537008 | 15.600 | Pequeno |
| Patrocínio Paulista | 3536307 | 14.529 | Pequeno |
| São José da Bela Vista | 3549508 | 8.895 | Pequeno |
| Cristais Paulista | 3513207 | 8.200 | Pequeno |
| Restinga | 3542701 | 7.504 | Pequeno |
| Itirapuã | 3523701 | 6.453 | Pequeno |
| Aramina | 3503000 | 5.535 | Pequeno |
| Ribeirão Corrente | 3543105 | 4.682 | Pequeno |
| Buritizal | 3508207 | 4.458 | Pequeno |
| Rifaina | 3543600 | 4.179 | Pequeno |
| Jeriquara | 3525409 | 4.000 | Pequeno |

---

## 🔗 APIs Integradas

| API | Tabela/Endpoint | Auth |
|-----|-----------------|------|
| Base dos Dados (BigQuery) | `basedosdados.br_cgu_emendas_parlamentares.microdados` — histórico 2013-2026 | OAuth Google (`pip install basedosdados`) |
| Portal da Transparência | `/emendas`, `/emendas/{codigo}` — execução em tempo real | Header `chave-api-dados` |
| Transferegov.br | `/transferenciasespeciais/plano_acao_especial`, `/executor_especial` | Pública (PostgREST) |
| BrasilAPI | `/api/cnpj/v1/{cnpj}` — dados cadastrais | Pública |

---

## 🧪 Testes

```bash
pytest tests/ -v
```

---

## 📋 Referências Normativas

- **EC 105/2019** — Transferências especiais (emendas PIX)
- **LC 210/2024** — Plano de trabalho, conta específica, rastreabilidade
- **ADPF 854 (STF)** — Transparência das emendas (rel. Min. Flávio Dino)
- **IN-TCU 93/2024** — Transparência ativa obrigatória

---

*RADAR-EP v1.0 | 13ª SJ MPF Franca/SP | Uso interno restrito | LGPD aplicável*
