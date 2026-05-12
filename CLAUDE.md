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

17 municípios do interior paulista. Consultar tabela `municipios_franca` no banco `radar_ep.duckdb`:

| Município | IBGE | Porte | Pop. |
|-----------|------|-------|------|
| Franca | 3516200 | G | 365.494 |
| São Joaquim da Barra | 3548005 | M | 49.885 |
| Ituverava | 3525706 | M | 38.413 |
| Igarapava | 3522901 | M | 26.696 |
| Guará | 3522000 | P | 18.748 |
| Ipuã | 3523008 | P | 15.900 |
| Pedregulho | 3543600 | P | 15.600 |
| Patrocínio Paulista | 3536703 | P | 14.529 |
| São José da Bela Vista | 3548104 | P | 8.895 |
| Cristais Paulista | 3521309 | P | 8.200 |
| Restinga | 3543907 | P | 7.504 |
| Itirapuã | 3524105 | P | 6.453 |
| Aramina | 3503000 | P | 5.535 |
| Ribeirão Corrente | 3544004 | P | 4.682 |
| Buritizal | 3519006 | P | 4.458 |
| Rifaina | 3544608 | P | 4.179 |
| Jeriquara | 3530508 | P | 4.000 |

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
-- Emendas parlamentares (CSV local + BigQuery)
emendas_parlamentares  -- 92.756+ linhas

-- Convênios firmados
convenios              -- 81.977 linhas

-- Pagamentos por favorecido (empresa/pessoa)
por_favorecido         -- 772.371 linhas

-- Municípios monitorados
municipios_franca      -- 17 linhas

-- Alertas gerados pelo motor de risco
alertas                -- dinâmico
```

---

## Contato Institucional

**13ª Subseção Judiciária — MPF Franca/SP**  
Sistema RADAR-EP — Uso interno restrito  
Dados sujeitos à LGPD e sigilo funcional
