# RADAR-EP — Contexto Normativo para Agentes de IA
**Versão 1.0 | Maio/2026 | 13ª Subseção Judiciária do MPF — Franca/SP**

---

## Propósito deste arquivo

Este arquivo fornece contexto normativo, legal e operacional para agentes de IA que interagem com o sistema RADAR-EP. Leia-o antes de gerar qualquer código, alerta, consulta SQL ou narrativa.

---

## Legislação Vigente (Maio/2026)

| Norma | Descrição |
|-------|-----------|
| **EC 105/2019** | Criou as transferências especiais (emendas PIX) — sem vinculação de objeto na transferência |
| **LC 210/2024** | Exige plano de trabalho, conta-corrente específica por emenda e rastreabilidade dos pagamentos |
| **ADPF 854** (STF, rel. Min. Flávio Dino) | Decisões de ago/2024 a mar/2026 sobre transparência e bloqueio de emendas |
| **IN-TCU 93/2024** | Transparência ativa obrigatória das emendas parlamentares |

---

## Decisões Recentes Relevantes

- **Janeiro/2026**: Vedação de repasse a OSCs (Organizações da Sociedade Civil) com parentes de 1º e 2º grau do parlamentar autor
- **Março/2026**: Proibição de saques em espécie; pagamentos exclusivamente por meios eletrônicos rastreáveis
- **Setembro/2025**: Suspensão de repasses a municípios sem rastreabilidade de gastos das emendas

---

## Municípios Monitorados — 13ª SJ Franca/SP

17 municípios do interior paulista. Fonte autoritativa: tabela `municipios_franca` no banco `radar_ep.duckdb` (criada por `scripts/setup_db.py`).

| Município | IBGE | Porte | Pop. |
|-----------|------|-------|------|
| Franca | 3516200 | G | 365.494 |
| São Joaquim da Barra | 3549409 | M | 49.885 |
| Ituverava | 3524105 | M | 38.413 |
| Igarapava | 3520103 | M | 26.696 |
| Guará | 3517703 | P | 18.748 |
| Ipuã | 3521309 | P | 15.900 |
| Pedregulho | 3537008 | P | 15.600 |
| Patrocínio Paulista | 3536307 | P | 14.529 |
| São José da Bela Vista | 3549508 | P | 8.895 |
| Cristais Paulista | 3513207 | P | 8.200 |
| Restinga | 3542701 | P | 7.504 |
| Itirapuã | 3523701 | P | 6.453 |
| Aramina | 3503000 | P | 5.535 |
| Ribeirão Corrente | 3543105 | P | 4.682 |
| Buritizal | 3508207 | P | 4.458 |
| Rifaina | 3543600 | P | 4.179 |
| Jeriquara | 3525409 | P | 4.000 |

---

## Pesos dos Indicadores de Risco (Versão 1.0 — Maio/2026)

```
concentracao       : 0.18  # Concentração parlamentar em município pequeno
divergencia_objeto : 0.16  # Divergência NLP entre objeto e natureza
empresa_jovem      : 0.14  # Empresa favorecida com < 24 meses
doacao_parlamentar : 0.14  # Empresa doou para campanha do parlamentar autor
pre_eleitoral      : 0.12  # Emenda emitida em ano eleitoral (período < 6 meses antes)
valor_anomalo      : 0.10  # Valor outlier (z-score > 2.5 no histórico do município)
campos_ausentes    : 0.08  # Campos obrigatórios ausentes no Portal da Transparência
historico_sancoes  : 0.04  # Empresa/pessoa no CEIS ou CNEP
pc_vencida         : 0.04  # Prestação de contas vencida há > 30 dias
                     ────
TOTAL              : 1.00
```

---

## Regras Invioláveis de Linguagem

### ❌ NUNCA usar em alertas automáticos:
- "fraude", "desvio", "crime", "ilegalidade", "irregularidade confirmada"
- "corrupção", "superfaturamento" (sem sentença judicial)
- Qualquer afirmação categórica sobre intenção dolosa

### ✅ SEMPRE usar linguagem condicional:
- "padrão atípico que merece verificação"
- "indício a verificar"
- "merece análise aprofundada"
- "apresenta características que se afastam do padrão histórico"
- "requer conferência documental"

---

## Regras de Negócio Críticas

1. **Alertas com escore < 0.80**: sempre incluir `"requer_confirmacao_humana": true`
2. **CPFs no frontend**: sempre mascarados (`***.***.***-**`). Dados completos apenas em endpoints autenticados com token MPF
3. **Retroalimentação**: analistas podem classificar alertas como `falso_positivo` ou `encaminhado`. Essa classificação alimenta a recalibração trimestral dos pesos
4. **LC 210/2024** — verificar SEMPRE:
   - Plano de trabalho presente antes do empenho
   - Conta-corrente específica por emenda (endpoint `executor_especial`)
   - Pagamentos exclusivamente eletrônicos (vedação saques, mar/2026)
   - Ausência de parentes do parlamentar em OSCs beneficiadas (jan/2026)

---

## Fontes de Dados

| Fonte | Uso | Autenticação |
|-------|-----|-------------|
| Base dos Dados (BigQuery) | Histórico 2013-2026 | OAuth Google |
| Portal Transparência API | Execução em tempo real | Header `chave-api-dados` |
| Transferegov API | Planos de trabalho e relatórios | Pública (PostgREST) |
| BrasilAPI (CNPJ) | Dados cadastrais de empresas | Pública |
| TSE (Base dos Dados) | Doações de campanha | OAuth Google |
| CEIS/CNEP | Sanções a empresas | Download CSV mensal |

---

## Schema do Banco DuckDB (radar_ep.duckdb)

```sql
-- Emendas parlamentares (CSV local + BigQuery br_cgu_emendas_parlamentares.microdados)
-- Colunas principais (BigQuery): ano_emenda, id_emenda, numero_emenda, tipo_emenda,
--   id_autor_emenda, nome_autor_emenda, localidade, sigla_uf_gasto, id_municipio_gasto,
--   id_funcao, nome_funcao, id_subfuncao, nome_subfuncao, id_programa, nome_programa,
--   id_acao, nome_acao, id_plano_orcamentario, nome_plano_orcamentario,
--   valor_empenhado, valor_liquidado, valor_pago,
--   valor_resto_pagar_inscrito, valor_resto_pagar_cancelado, valor_resto_pagar_pagos
emendas_parlamentares  -- 92.756+ linhas (CGU, cobertura 2013-2026)

-- Convênios firmados
convenios              -- 81.977 linhas

-- Pagamentos por favorecido (empresa/pessoa)
por_favorecido         -- 772.371 linhas

-- Municípios monitorados (17 municípios — fonte autoritativa de IBGEs)
municipios_franca      -- 17 linhas

-- Cache de consultas CNPJ (BrasilAPI) — evita chamadas repetidas
cnpj_cache             -- dinâmico

-- Sanções CEIS/CNEP (CSV mensal CGU)
sancoes_ceis           -- dinâmico

-- Alertas gerados pelo motor de risco
alertas                -- dinâmico
```

### Views normalizadas
```sql
-- Valores monetários convertidos de formato BR ("10.000,00") para DOUBLE
v_emendas_valores      -- SELECT * FROM emendas_parlamentares + colunas val_*
v_favorecido_valores   -- SELECT * FROM por_favorecido + val_recebido, cnpj_limpo, ano_ref, mes_ref
```

---

## Contato Institucional

**13ª Subseção Judiciária — MPF Franca/SP**  
Sistema RADAR-EP — Uso interno restrito  
Dados sujeitos à LGPD e sigilo funcional
