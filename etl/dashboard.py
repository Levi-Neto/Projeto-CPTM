# Instrucoes para executar na raiz do projeto:
# 1. Instale as dependencias: .venv\Scripts\python -m pip install -r requirements.txt
# 2. Inicie o dashboard: .venv\Scripts\python -m streamlit run etl\dashboard.py

from pathlib import Path

import pandas as pd
import streamlit as st

from parsers import parse_cdvs, parse_sinais


PASTA_PROJETO = Path(__file__).resolve().parent.parent
ARQUIVO_SINAIS = PASTA_PROJETO / "dataset" / "levantamento_BD_Sinais_via_1_e_2.xlsx"
ARQUIVO_CDVS = PASTA_PROJETO / "dataset" / "levantamento_BD_CDVs_via_1_e_2.xlsx"

st.set_page_config(page_title="Locação de sinalização ferroviária", layout="wide")


@st.cache_data(show_spinner="Carregando os bancos de dados...")
def carregar_dados(
    caminho_sinais: str, caminho_cdvs: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê as planilhas e converte os blocos em tabelas de locação."""
    return parse_sinais(caminho_sinais), parse_cdvs(caminho_cdvs)


def exibir_cenario(
    dados: pd.DataFrame, nome_equipamento: str, chave: str
) -> None:
    """Aplica filtros e mostra os vínculos entre tags, locais e posições."""
    if dados.empty:
        st.warning(f"Nenhum registro de {nome_equipamento.lower()} foi encontrado.")
        return

    equipamentos = sorted(dados["numero"].dropna().unique().tolist())
    locais = sorted(dados["local_detalhe"].dropna().unique().tolist())

    col_filtro_equipamento, col_filtro_local = st.columns(2)
    with col_filtro_equipamento:
        equipamentos_selecionados = st.multiselect(
            nome_equipamento,
            options=equipamentos,
            default=equipamentos,
            key=f"{chave}_equipamentos",
        )
    with col_filtro_local:
        locais_selecionados = st.multiselect(
            "Locação / local",
            options=locais,
            default=locais,
            key=f"{chave}_locais",
        )

    filtrados = dados.loc[
        dados["numero"].isin(equipamentos_selecionados)
        & dados["local_detalhe"].isin(locais_selecionados)
    ].copy()
    locados = filtrados.loc[filtrados["valor"].notna()]

    metricas = st.columns(3)
    metricas[0].metric("Equipamentos", filtrados["equipamento"].nunique())
    metricas[1].metric("Vínculos com posição", len(locados))
    metricas[2].metric("Locais", filtrados["local_detalhe"].nunique())

    if filtrados.empty:
        st.info("Nenhum registro corresponde aos filtros selecionados.")
        return

    resumo = (
        locados.groupby("local_tipo", as_index=False)
        .size()
        .rename(columns={"local_tipo": "Tipo de local", "size": "Vínculos locados"})
    )
    st.subheader("Distribuição por tipo de local")
    st.bar_chart(resumo, x="Tipo de local", y="Vínculos locados")

    colunas = ["equipamento", "numero", "tag"]
    if "aspecto" in filtrados.columns:
        colunas.append("aspecto")
    if "funcao" in filtrados.columns:
        colunas.append("funcao")
    colunas.extend(["local_tipo", "local_detalhe", "valor"])

    tabela = filtrados[colunas].rename(
        columns={
            "equipamento": "Equipamento",
            "numero": "Sinal / CDV",
            "tag": "Tag",
            "aspecto": "Aspecto",
            "funcao": "Função",
            "local_tipo": "Tipo de local",
            "local_detalhe": "Locação / local",
            "valor": "Posição",
        }
    )
    tabela["Posição"] = tabela["Posição"].fillna("Não informada")
    st.subheader("Detalhamento das locações")
    st.dataframe(tabela, hide_index=True, width="stretch")

    st.download_button(
        "Baixar dados filtrados (CSV)",
        data=tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{chave}_locacoes.csv",
        mime="text/csv",
        key=f"{chave}_download",
    )


st.title("Dashboard de sinalização ferroviária")
st.caption(
    "Consulta de sinais e circuitos de via (CDVs), com filtros por equipamento "
    "e pelas locações registradas nas planilhas."
)

arquivos_ausentes = [
    caminho.name for caminho in (ARQUIVO_SINAIS, ARQUIVO_CDVS) if not caminho.is_file()
]
if arquivos_ausentes:
    st.error(
        "Não foi possível localizar os bancos de dados na pasta `dataset`: "
        + ", ".join(arquivos_ausentes)
    )
    st.stop()

dados_sinais, dados_cdvs = carregar_dados(
    str(ARQUIVO_SINAIS), str(ARQUIVO_CDVS)
)

aba_sinais, aba_cdvs = st.tabs(["Sinais", "CDVs"])
with aba_sinais:
    exibir_cenario(dados_sinais, "Sinal", "sinais")
with aba_cdvs:
    exibir_cenario(dados_cdvs, "CDV", "cdvs")
