# 📖 Manual do Usuário — RADAR-EP

> Sistema de Rastreamento Analítico e Detecção de Anomalias em Recursos de Emendas Parlamentares

---

## 🚀 Como Iniciar o Sistema

### 1. Configuração de Ambiente
O sistema utiliza Python 3.11+. Certifique-se de que as dependências estão instaladas:
```bash
pip install -r requirements.txt
```

### 2. Carga Inicial de Dados
Para carregar os dados dos 3 arquivos CSV para o banco de dados DuckDB:
```bash
python scripts/setup_db.py
```
*Nota: Este script limpa o banco anterior e recria as tabelas e views.*

### 3. Execução da Análise de Risco (Pipeline)
Para processar as emendas e gerar alertas de risco:
```bash
# Modo Completo (Requer APIs configuradas no .env)
python scripts/run_risk_pipeline.py

# Modo Rápido (Apenas dados locais)
python scripts/run_risk_pipeline.py --sem-cnpj --sem-portal --sem-nlp
```

### 4. Visualização no Dashboard
Para abrir a interface gráfica interativa:
```bash
streamlit run src/dashboard.py
```

### 5. API de Integração
Para disponibilizar os dados via API REST (FastAPI):
```bash
uvicorn src.api:app --reload
```

---

## 🛠️ Manutenção e Sincronização

### Sincronização Diária
O sistema possui um script para buscar dados novos diretamente do Portal da Transparência:
```bash
python scripts/sync_diario.py
```
*Recomenda-se agendar este script para execução diária via Windows Task Scheduler.*

---

## ⚖️ Regras de Uso e Compliance

1. **Linguagem Condicional**: Conforme diretrizes do MPF e LC 210/2024, o sistema NUNCA deve rotular uma emenda como "fraude" ou "corrupção" de forma automatizada. Os alertas usam termos como "padrão atípico" ou "indício a verificar".
2. **Confirmação Humana**: Alertas com escore abaixo de 0.80 possuem a flag `requer_confirmacao_humana=True`. O analista deve revisar e classificar o alerta no dashboard.
3. **Privacidade (LGPD)**: O sistema mascara CPFs e protege dados sensíveis na camada de visualização.

---

## 📊 Indicadores de Risco (Pesos)

| Indicador | Sigla | Peso |
| :--- | :--- | :--- |
| Concentração Parlamentar | `concentracao` | 18% |
| Divergência de Objeto (NLP) | `divergencia_objeto` | 16% |
| Empresa Jovem (< 24 meses) | `empresa_jovem` | 14% |
| Doação de Campanha | `doacao_parlamentar` | 14% |
| Período Pré-Eleitoral | `pre_eleitoral` | 12% |
| Valor Anômalo (Estatístico) | `valor_anomalo` | 10% |
| Campos Ausentes (Portal) | `campos_ausentes` | 8% |
| Histórico de Sanções | `historico_sancoes` | 4% |
| Prestação de Contas Vencida | `pc_vencida` | 4% |

---

*RADAR-EP | 13ª SJ MPF Franca/SP*
