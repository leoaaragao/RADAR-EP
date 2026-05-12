"""
RADAR-EP — Dashboard Streamlit
================================
Fase 3 — Interface principal do sistema.

Iniciar com: streamlit run src/dashboard.py
"""

import os
import json
import logging
from pathlib import Path

import duckdb
import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import folium_static

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ── Configuração da página ────────────────────────────────────
st.set_page_config(
    page_title="RADAR-EP | 13ª SJ Franca/SP",
    layout="wide",
    page_icon="📡",
    initial_sidebar_state="expanded",
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT_DIR / os.getenv("DUCKDB_PATH", "radar_ep.duckdb"))

# ── CSS customizado ───────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0f1117; }
    .block-container { padding-top: 1.5rem; }

    .kpi-card {
        background: linear-gradient(135deg, #1e2130, #252a3d);
        border: 1px solid #2d3250;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .kpi-value { font-size: 2.4rem; font-weight: 700; color: #e2e8f0; }
    .kpi-label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
    .kpi-red   { color: #f87171 !important; }
    .kpi-amber { color: #fbbf24 !important; }
    .kpi-green { color: #34d399 !important; }

    .alerta-alto  { background: rgba(248,113,113,0.12); border-left: 4px solid #f87171; }
    .alerta-medio { background: rgba(251,191,36,0.12);  border-left: 4px solid #fbbf24; }
    .alerta-baixo { background: rgba(52,211,153,0.12);  border-left: 4px solid #34d399; }

    .stDataFrame { border-radius: 8px; overflow: hidden; }
    div[data-testid="stSidebarContent"] { background: #161b2e; }
    .sidebar-header { color: #7c85ff; font-weight: 700; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)


# ── Conexão DB ────────────────────────────────────────────────
@st.cache_resource
def get_db():
    if not Path(DB_PATH).exists():
        st.error(f"Banco não encontrado: {DB_PATH}\nExecute: python scripts/setup_db.py")
        st.stop()
    return duckdb.connect(DB_PATH, read_only=True)

# Lista de IBGEs da 13a SJ
IBGES_13SJ = (
    '3516200','3503000','3508207','3513207','3517703',
    '3520103','3521309','3523701','3524105','3525409',
    '3536307','3537008','3542701','3543105','3543600',
    '3549409','3549508'
)


def safe_query(sql: str, params=None) -> pd.DataFrame:
    try:
        con = get_db()
        return con.execute(sql, params or []).df()
    except Exception as e:
        st.warning(f"Erro na consulta: {e}")
        return pd.DataFrame()


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-header">📡 RADAR-EP</div>', unsafe_allow_html=True)
    st.caption("13ª SJ MPF — Franca/SP | v1.0")
    st.divider()

    municipios_df = safe_query("SELECT nome FROM municipios_franca ORDER BY nome")
    mun_lista = ["Todos"] + municipios_df["nome"].tolist() if not municipios_df.empty else ["Todos"]
    municipio_sel = st.selectbox("🏙️ Município", mun_lista)

    ano_range = st.slider("📅 Período", 2014, 2026, (2014, 2026))

    escore_min = st.slider("⚠️ Escore mínimo", 0.0, 1.0, 0.20, step=0.05)

    tipo_emenda_opts = [
        "Todos",
        "Emenda Individual (PIX / Transf. Especiais)",
        "Emenda Individual (Finalidade Definida)",
        "Emenda Individual (Todas)",
        "Emenda de Relator",
        "Emenda de Bancada",
        "Emenda de Comissão"
    ]
    tipo_sel = st.selectbox("📋 Tipo de emenda", tipo_emenda_opts)

    st.divider()
    st.markdown("### 📥 Exportação de Relatórios")
    
    # 1. Relatório de Texto (Resumo Executivo)
    if st.button("📄 Gerar Relatório de Texto (.txt)"):
        df_exec = safe_query(f"""
            SELECT m.nome, m.ibge, m.populacao,
                   COALESCE(SUM(e."Valor Empenhado"), 0) as total,
                   COUNT(e."Código da Emenda") as n_emendas
            FROM municipios_franca m
            LEFT JOIN emendas_parlamentares e ON m.ibge = e."Código Município IBGE"
            GROUP BY 1, 2, 3 ORDER BY total DESC
        """)
        
        # Top 5 Autores
        df_autores = safe_query(f"""
            SELECT "Nome do Autor da Emenda" as parlamentar,
                   COUNT(*) as n_emendas,
                   SUM("Valor Empenhado") as total
            FROM emendas_parlamentares
            WHERE "Código Município IBGE" IN {IBGES_13SJ}
            GROUP BY parlamentar ORDER BY total DESC LIMIT 5
        """)
        
        # Top 5 Maiores Emendas
        df_maiores = safe_query(f"""
            SELECT "Município" as municipio, "Nome do Autor da Emenda" as parlamentar,
                   "Valor Empenhado" as total, "Tipo de Emenda" as tipo
            FROM emendas_parlamentares
            WHERE "Código Município IBGE" IN {IBGES_13SJ}
            ORDER BY "Valor Empenhado" DESC LIMIT 5
        """)

        txt_content = [
            "============================================================",
            "   RADAR-EP — RELATÓRIO EXECUTIVO DE FISCALIZAÇÃO",
            "   13ª Subseção Judiciária do MPF — Franca/SP",
            f"   Gerado em: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}",
            "============================================================",
            "\n1. RESUMO DOS MUNICÍPIOS (13ª SJ)",
            "------------------------------------------------------------"
        ]
        for _, r in df_exec.iterrows():
            txt_content.append(f"- {r['nome']:<25} | R$ {r['total']:>14,.2f} | {r['n_emendas']:>4} emendas")
        
        txt_content.extend([
            "\n2. TOP 5 AUTORES DE EMENDAS (13ª SJ)",
            "------------------------------------------------------------"
        ])
        for _, r in df_autores.iterrows():
            txt_content.append(f"- {r['parlamentar']:<35} | R$ {r['total']:>14,.2f} | {r['n_emendas']:>4} emendas")

        txt_content.extend([
            "\n3. TOP 5 MAIORES EMENDAS INDIVIDUAIS (13ª SJ)",
            "------------------------------------------------------------"
        ])
        for _, r in df_maiores.iterrows():
            txt_content.append(f"- {r['municipio']:<15} | {r['parlamentar']:<25} | {r['tipo']:<20} | R$ {r['total']:>14,.2f}")

        txt_content.extend([
            "\n4. METODOLOGIA DE ANÁLISE DE RISCO (9 INDICADORES)",
            "------------------------------------------------------------",
            "- Concentração Parlamentar: Peso 18%",
            "- Divergência de Objeto (IA): Peso 16%",
            "- Empresa Jovem (<24 meses): Peso 14%",
            "- Doação de Campanha: Peso 14%",
            "- Período Pré-Eleitoral: Peso 12%",
            "- Valor Anômalo: Peso 10%",
            "- Campos Ausentes no Portal: Peso 8%",
            "- Histórico de Sanções (CEIS): Peso 4%",
            "- Prestação de Contas Vencida: Peso 4%",
            "\n5. NOTA TÉCNICA",
            "------------------------------------------------------------",
            "Este relatório visa subsidiar a atuação ministerial na fiscalização",
            "de emendas parlamentares. Alertas indicam indícios a verificar,",
            "não constituindo prova de irregularidade confirmada."
        ])
        
        st.download_button(
            label="Baixar Relatório Texto",
            data="\n".join(txt_content),
            file_name=f"RADAR_EP_Resumo_Executivo.txt",
            mime="text/plain",
        )

    # 2. Relatório Excel Avançado
    if st.button("📊 Gerar Relatório Técnico (.xlsx)"):
        import io
        output = io.BytesIO()
        
        # Obter dados
        df_mun = safe_query("""
            SELECT nome as Município, ibge as IBGE, populacao as População, porte as Porte
            FROM municipios_franca ORDER BY nome
        """)
        df_emendas = safe_query(f"""
            SELECT * FROM emendas_parlamentares 
            WHERE "Código Município IBGE" IN {IBGES_13SJ}
            LIMIT 5000
        """)
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Planilha 1: Resumo
            df_mun.to_excel(writer, sheet_name='Sumário Municípios', index=False)
            
            # Planilha 2: Emendas Detalhadas
            df_emendas.to_excel(writer, sheet_name='Dados Emendas', index=False)
            
            # Planilha 3: Metodologia
            df_metodo = pd.DataFrame({
                'Indicador': ['Concentração', 'Objeto (IA)', 'Empresa Jovem', 'Doações', 'Eleitoral', 'Valor', 'Portal', 'Sanções', 'Contas'],
                'Peso': ['18%', '16%', '14%', '14%', '12%', '10%', '8%', '4%', '4%'],
                'Descrição': [
                    'Concentração excessiva de recursos em poucos favorecidos.',
                    'Divergência entre o objeto da emenda e a atividade do favorecido.',
                    'Empresa contratada criada há menos de 24 meses.',
                    'Favorecido doou para a campanha do parlamentar autor.',
                    'Empenhos concentrados nos 3 meses que antecedem eleições.',
                    'Valor da emenda foge à média histórica para o município.',
                    'Dados ausentes ou inconsistentes no Portal da Transparência.',
                    'Empresa ou sócios presentes no CEIS/CNEP.',
                    'Favorecido com pendências em convênios anteriores.'
                ]
            })
            df_metodo.to_excel(writer, sheet_name='Metodologia de Risco', index=False)
            
        st.download_button(
            label="Baixar Planilha Técnica",
            data=output.getvalue(),
            file_name=f"RADAR_EP_Relatorio_Tecnico_13SJ.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()
    st.caption("🔒 CPFs mascarados (LGPD)\nUso interno restrito MPF")


# ── Cabeçalho ─────────────────────────────────────────────────
st.markdown("## 📡 RADAR-EP — Rastreamento de Emendas Parlamentares")
st.markdown(
    "**13ª Subseção Judiciária do MPF — Franca/SP** | "
    f"Período: {ano_range[0]}–{ano_range[1]} | "
    f"Filtro: {municipio_sel}"
)

# ── KPIs ──────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

# Filtro dinâmico
where_mun = f"AND municipio = '{municipio_sel}'" if municipio_sel != "Todos" else ""
where_ano = f"AND ano_emenda BETWEEN {ano_range[0]} AND {ano_range[1]}"
where_tipo_alertas = ""
where_tipo_emendas = ""

if tipo_sel == "Emenda Individual (PIX / Transf. Especiais)":
    where_tipo_alertas = "AND tipo_emenda LIKE '%Especiais%'"
    where_tipo_emendas = "AND \"Tipo de Emenda\" LIKE '%Especiais%'"
elif tipo_sel == "Emenda Individual (Finalidade Definida)":
    where_tipo_alertas = "AND tipo_emenda LIKE '%Finalidade Definida%'"
    where_tipo_emendas = "AND \"Tipo de Emenda\" LIKE '%Finalidade Definida%'"
elif tipo_sel == "Emenda Individual (Todas)":
    where_tipo_alertas = "AND tipo_emenda LIKE 'Emenda Individual%'"
    where_tipo_emendas = "AND \"Tipo de Emenda\" LIKE 'Emenda Individual%'"
elif tipo_sel != "Todos":
    # Relator, Bancada, Comissão (precisam bater com nomes ou usar LIKE)
    # Ex: 'Emenda de Relator' ou 'Emenda de Comisso' no DB (como visto no erro de encoding)
    where_tipo_alertas = f"AND tipo_emenda LIKE '{tipo_sel[:15]}%'"
    where_tipo_emendas = f"AND \"Tipo de Emenda\" LIKE '{tipo_sel[:15]}%'"

total_alertas = safe_query(f"SELECT COUNT(*) as n FROM alertas WHERE escore >= {escore_min} {where_mun} {where_ano} {where_tipo_alertas}")
alertas_altos = safe_query(f"SELECT COUNT(*) as n FROM alertas WHERE escore >= 0.6 {where_mun} {where_ano} {where_tipo_alertas}")
alertas_abertos = safe_query(f"SELECT COUNT(*) as n FROM alertas WHERE status='aberto' AND escore >= {escore_min} {where_mun} {where_ano} {where_tipo_alertas}")

n_alertas = int(total_alertas["n"].iloc[0]) if not total_alertas.empty else 0
n_altos = int(alertas_altos["n"].iloc[0]) if not alertas_altos.empty else 0
n_abertos = int(alertas_abertos["n"].iloc[0]) if not alertas_abertos.empty else 0

# Lista de IBGEs da 13a SJ já definida no topo
ibge_filter = f"\"Código Município IBGE\" IN {IBGES_13SJ}"

val_q = f"""
    SELECT COALESCE(SUM("Valor Empenhado"), 0) as total
    FROM emendas_parlamentares
    WHERE {ibge_filter}
      AND "Ano da Emenda" BETWEEN {ano_range[0]} AND {ano_range[1]}
    {'AND "Município" = \''+municipio_sel+'\'' if municipio_sel != "Todos" else ""}
    {where_tipo_emendas}
"""
val_df = safe_query(val_q)
total_val = float(val_df["total"].iloc[0]) if not val_df.empty else 0

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value kpi-amber">R$ {total_val/1e6:.1f}M</div>
        <div class="kpi-label">Total Empenhado</div>
    </div>""", unsafe_allow_html=True)

with col2:
    cor = "kpi-red" if n_alertas > 0 else "kpi-green"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value {cor}">{n_alertas}</div>
        <div class="kpi-label">Alertas Gerados</div>
    </div>""", unsafe_allow_html=True)

with col3:
    cor = "kpi-red" if n_altos > 0 else "kpi-green"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value {cor}">{n_altos}</div>
        <div class="kpi-label">Escore Alto (≥ 0.60)</div>
    </div>""", unsafe_allow_html=True)

with col4:
    cor = "kpi-amber" if n_abertos > 0 else "kpi-green"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value {cor}">{n_abertos}</div>
        <div class="kpi-label">Alertas em Aberto</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Abas principais ───────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa", "⚠️ Alertas", "📊 Análises", "🤖 Consulta IA"])


# ══════════════════════════════════════════════════════════════
# ABA 1 — MAPA
# ══════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Mapa de Risco — 17 Municípios da 13ª SJ Franca/SP")

    mun_coords = safe_query("SELECT nome, ibge, populacao, porte, lat, lon FROM municipios_franca")
    alertas_mun = safe_query(f"""
        SELECT municipio, AVG(escore) as escore_medio, COUNT(*) as n_alertas
        FROM alertas WHERE escore >= {escore_min}
        GROUP BY municipio
    """)

    m = folium.Map(location=[-20.40, -47.60], zoom_start=9,
                   tiles="OpenStreetMap")

    if not mun_coords.empty:
        for _, row in mun_coords.iterrows():
            # Buscar escore deste município
            escore_row = alertas_mun[alertas_mun["municipio"] == row["nome"]]
            escore = float(escore_row["escore_medio"].iloc[0]) if not escore_row.empty else 0.0
            n_al = int(escore_row["n_alertas"].iloc[0]) if not escore_row.empty else 0

            # Cor por escore
            if escore >= 0.6:
                cor = "#f87171"   # vermelho
            elif escore >= 0.35:
                cor = "#fbbf24"   # âmbar
            else:
                cor = "#34d399"   # verde

            raio = max(8, min(25, 8 + escore * 20))

            popup_html = f"""
            <div style='font-family:Inter,sans-serif;min-width:180px'>
                <b style='font-size:14px'>{row['nome']}</b><br>
                <span style='color:#94a3b8'>IBGE: {row['ibge']}</span><br>
                <span style='color:#94a3b8'>Pop.: {row['populacao']:,}</span><br>
                <hr style='margin:6px 0'>
                <b style='color:{cor}'>Escore: {escore:.2f}</b><br>
                Alertas: {n_al}
            </div>"""

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=raio,
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"{row['nome']} | Escore: {escore:.2f}",
            ).add_to(m)

    folium_static(m, width=None, height=480)

    # Legenda
    col_l1, col_l2, col_l3, _ = st.columns([1, 1, 1, 3])
    with col_l1:
        st.markdown("🔴 **Alto risco** (≥ 0.60)")
    with col_l2:
        st.markdown("🟡 **Médio risco** (0.35–0.60)")
    with col_l3:
        st.markdown("🟢 **Baixo risco** (< 0.35)")


# ══════════════════════════════════════════════════════════════
# ABA 2 — ALERTAS
# ══════════════════════════════════════════════════════════════
with tab2:
    st.subheader("⚠️ Alertas Ativos")

    where_alertas = f"WHERE escore >= {escore_min}"
    if municipio_sel != "Todos":
        where_alertas += f" AND municipio = '{municipio_sel}'"
    if where_tipo_alertas:
        where_alertas += f" {where_tipo_alertas}"

    alertas_df = safe_query(f"""
        SELECT
            id,
            codigo_emenda   AS "Emenda",
            municipio       AS "Município",
            parlamentar     AS "Parlamentar",
            tipo_alerta     AS "Tipo",
            ano_emenda      AS "Ano",
            PRINTF('R$ %,.2f', valor_emenda) AS "Valor",
            PRINTF('%.3f', escore)           AS "Escore",
            status          AS "Status",
            requer_confirmacao_humana        AS "Conf. Humana",
            descricao       AS "Descrição"
        FROM alertas
        {where_alertas}
        ORDER BY escore DESC, data_geracao DESC
        LIMIT 200
    """)

    if alertas_df.empty:
        st.info("Nenhum alerta encontrado com os filtros atuais. "
                "Execute o pipeline de risco para gerar alertas.")
    else:
        st.dataframe(
            alertas_df.drop(columns=["id", "Descrição"], errors="ignore"),
            use_container_width=True,
            height=400,
        )

        # Detalhe ao selecionar
        if "id" in alertas_df.columns:
            id_sel = st.selectbox(
                "Selecione um alerta para ver detalhes:",
                options=alertas_df["id"].tolist(),
                format_func=lambda x: f"#{x} — {alertas_df[alertas_df['id']==x]['Município'].values[0]}"
            )
            if id_sel:
                detalhe = alertas_df[alertas_df["id"] == id_sel].iloc[0]
                st.markdown(f"**Descrição:** {detalhe.get('Descrição', 'N/A')}")

                # Classificação manual
                st.markdown("**Classificar alerta:**")
                col_c1, col_c2, col_c3 = st.columns(3)
                analista = st.text_input("Identificação do analista")
                obs = st.text_area("Observações", height=80)

                with col_c1:
                    if st.button("✅ Falso Positivo", key=f"fp_{id_sel}"):
                        from src.risco.alerta_writer import classificar_alerta
                        classificar_alerta(id_sel, "falso_positivo", analista, obs, DB_PATH)
                        st.success("Classificado como falso positivo")
                        st.rerun()
                with col_c2:
                    if st.button("📤 Encaminhar", key=f"enc_{id_sel}"):
                        from src.risco.alerta_writer import classificar_alerta
                        classificar_alerta(id_sel, "encaminhado", analista, obs, DB_PATH)
                        st.success("Alerta encaminhado")
                        st.rerun()
                with col_c3:
                    if st.button("🔍 Em Verificação", key=f"ver_{id_sel}"):
                        from src.risco.alerta_writer import classificar_alerta
                        classificar_alerta(id_sel, "verificando", analista, obs, DB_PATH)
                        st.success("Marcado como em verificação")
                        st.rerun()


# ══════════════════════════════════════════════════════════════
# ABA 3 — ANÁLISES
# ══════════════════════════════════════════════════════════════
with tab3:
    st.subheader("📊 Análises Exploratórias — 13ª SJ")
    st.markdown("""
        Esta aba apresenta a distribuição dos recursos destinados aos 17 municípios da jurisdição. 
        As análises permitem identificar concentrações atípicas e o perfil dos investimentos.
    """)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        # Emendas por município
        df_mun = safe_query(f"""
            SELECT "Município" as municipio,
                   SUM("Valor Empenhado") as total
            FROM emendas_parlamentares
            WHERE {ibge_filter}
              AND "Ano da Emenda" BETWEEN {ano_range[0]} AND {ano_range[1]}
              {where_tipo_emendas}
            GROUP BY "Município"
            ORDER BY total DESC
            LIMIT 17
        """)
        if not df_mun.empty:
            fig = px.bar(
                df_mun, x="total", y="municipio", orientation="h",
                title="Valor Total por Município",
                color="total", color_continuous_scale="Blues",
                labels={"total": "Valor Empenhado (R$)", "municipio": "Município"},
                template="plotly_dark",
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False,
                               height=420, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        # Evolução temporal
        df_ano = safe_query(f"""
            SELECT "Ano da Emenda" as ano,
                   SUM("Valor Empenhado") as total
            FROM emendas_parlamentares
            WHERE {ibge_filter}
              AND "Ano da Emenda" BETWEEN {ano_range[0]} AND {ano_range[1]}
            {'AND "Município" = \''+municipio_sel+'\'' if municipio_sel != "Todos" else ""}
            {where_tipo_emendas}
            GROUP BY ano ORDER BY ano
        """)
        if not df_ano.empty:
            fig2 = px.area(
                df_ano, x="ano", y="total",
                title=f"Evolução dos Repasses ({municipio_sel})",
                labels={"total": "R$", "ano": "Ano"},
                template="plotly_dark", color_discrete_sequence=["#7c85ff"],
            )
            fig2.update_layout(height=420, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    col_g3, col_g4 = st.columns(2)
    
    with col_g3:
        # Top parlamentares (Filtrado por 13 SJ)
        df_parl = safe_query(f"""
            SELECT "Nome do Autor da Emenda" as parlamentar,
                   COUNT(*) as n_emendas,
                   SUM("Valor Empenhado") as total
            FROM emendas_parlamentares
            WHERE {ibge_filter}
              AND "Ano da Emenda" BETWEEN {ano_range[0]} AND {ano_range[1]}
            {'AND "Município" = \''+municipio_sel+'\'' if municipio_sel != "Todos" else ""}
            {where_tipo_emendas}
            GROUP BY parlamentar ORDER BY total DESC LIMIT 15
        """)
        if not df_parl.empty:
            fig3 = px.bar(
                df_parl, x="parlamentar", y="total",
                title="Top 15 Autores (Repasses para 13ª SJ)",
                color="n_emendas", color_continuous_scale="Purples",
                labels={"total": "R$", "parlamentar": "Parlamentar/Bancada", "n_emendas": "Qtd. Emendas"},
                template="plotly_dark",
            )
            fig3.update_layout(height=450, xaxis_tickangle=-45,
                               margin=dict(l=0, r=0, t=40, b=120))
            st.plotly_chart(fig3, use_container_width=True)
            
    with col_g4:
        # Distribuição por Tipo de Emenda
        df_tipo = safe_query(f"""
            SELECT "Tipo de Emenda" as tipo,
                   SUM("Valor Empenhado") as total
            FROM emendas_parlamentares
            WHERE {ibge_filter}
              AND "Ano da Emenda" BETWEEN {ano_range[0]} AND {ano_range[1]}
            {'AND "Município" = \''+municipio_sel+'\'' if municipio_sel != "Todos" else ""}
            {where_tipo_emendas}
            GROUP BY tipo ORDER BY total DESC
        """)
        if not df_tipo.empty:
            fig4 = px.pie(
                df_tipo, values="total", names="tipo",
                title="Distribuição por Modalidade",
                hole=0.4, template="plotly_dark",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig4.update_layout(height=450, margin=dict(l=0, r=0, t=40, b=40))
            st.plotly_chart(fig4, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# ABA 4 — CONSULTA IA (NL → SQL)
# ══════════════════════════════════════════════════════════════
with tab4:
    st.subheader("🤖 Consulta em Linguagem Natural")
    st.caption(
        "Digite uma pergunta sobre as emendas. O sistema converte para SQL e "
        "retorna uma narrativa analítica."
    )

    from src.ai_provider import prover_disponivel, gerar_sql, gerar_narrativa
    ai_status = prover_disponivel()
    
    if not ai_status["ativo"]:
        st.warning("Nenhuma chave de IA (Google Gemini ou Anthropic) configurada no .env.")
    else:
        st.info(f"Provedor ativo: {ai_status['ativo'].title()} ({ai_status['modelo']})")
        
        pergunta = st.text_area(
            "Sua pergunta:",
            placeholder=(
                "Ex.: Quais emendas de Ituverava em 2024 têm valor acima de R$500 mil?\n"
                "Ex.: Mostre os parlamentares com mais emendas em municípios pequenos.\n"
                "Ex.: Quais favorecidos receberam mais de R$1 milhão em 2023?"
            ),
            height=100,
        )

        col_btn, col_info = st.columns([1, 4])
        with col_btn:
            consultar = st.button("🔍 Consultar", type="primary", use_container_width=True)
        with col_info:
            st.caption(
                "⚖️ Resultados são analíticos. Linguagem condicional obrigatória "
                "(LC 210/2024 — nunca afirma irregularidade confirmada)."
            )

        if consultar and pergunta:
            try:
                # Obter schema do banco
                con_schema = get_db()
                tabelas = con_schema.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'main'
                """).df()["table_name"].tolist()

                schema_info = []
                for t in tabelas:
                    try:
                        cols = con_schema.execute(f"DESCRIBE {t}").df()
                        schema_info.append(
                            f"Tabela '{t}': " +
                            ", ".join(f"{r['column_name']} ({r['column_type']})"
                                      for _, r in cols.iterrows())
                        )
                    except Exception:
                        pass
                schema_str = "\n".join(schema_info)

                with st.spinner("IA processando pergunta..."):
                    sql_gerado = gerar_sql(pergunta, schema_str)
                
                # Limpeza básica do SQL gerado
                sql_gerado = sql_gerado.replace("```sql", "").replace("```", "").strip()

                with st.expander("📋 SQL gerado pela IA", expanded=False):
                    st.code(sql_gerado, language="sql")

                try:
                    resultado = safe_query(sql_gerado)

                    if resultado.empty:
                        st.info("Nenhum resultado encontrado para esta consulta.")
                    else:
                        st.dataframe(resultado, use_container_width=True, height=300)

                        with st.spinner("Gerando narrativa analítica..."):
                            narrativa = gerar_narrativa(pergunta, resultado.head(10).to_string(index=False))
                        
                        st.info(f"📝 **Análise:** {narrativa}")

                except Exception as e:
                    st.error(f"Erro ao executar SQL: {e}")
                    st.code(sql_gerado, language="sql")

            except Exception as e:
                st.error(f"Erro na consulta IA: {e}")


# ── Rodapé ────────────────────────────────────────────────────
st.divider()
st.caption(
    "📡 RADAR-EP v1.0 | 13ª Subseção Judiciária do MPF — Franca/SP | "
    "Uso interno restrito | LGPD aplicável | "
    "Alertas automáticos não constituem confirmação de irregularidade"
)
