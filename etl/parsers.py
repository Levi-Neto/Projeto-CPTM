import re
import unicodedata
import pandas as pd
 
# Padrões utilizados para identificar blocos de equipamentos na planilha Excel.
# Exemplo de célula reconhecida: "SINAL 123 LUZ" ou "CDV 456 LUZ".
RE_SINAL = re.compile(r"^SINAL\s+(\S+)\s+LUZ$", re.I)
RE_CDV = re.compile(r"^CDV\s+(\S+)\s+LUZ$", re.I)


def _norm_local(txt: str) -> str:
    
    # Normaliza e padroniza os rótulos de local para nomes consistentes.
    # Remove acentos e caracteres especiais para comparar o texto de forma uniforme.
    t = unicodedata.normalize("NFKD", str(txt).strip()).encode("ascii", "ignore").decode()
    if t.lower().startswith("loca"):
        return "Locação"
    if t.lower().startswith("armar"):
        return "Armário TB"
    if t.lower().startswith("interface"):
        return "Interface"
    if t.lower().startswith("bastidor"):
        return "Bastidor"
    if t.lower().startswith("sinaleiro"):
        return "Sinaleiro - TB"
    return t


def _clean(v):
    
    # Remove valores vazios, marcados como '-' ou ausentes antes de persistir no DataFrame.
    if pd.isna(v):
        return None
    s = str(v).strip()
    return None if s in ("", "-") else s


def _read_blocks(df, anchor_re, n_cols, tag_row_offset):
    
    # Busca cada cabeçalho de bloco na planilha (ex.: SINAL 123 LUZ ou CDV 456 LUZ).
    # O objetivo é localizar a posição de cada equipamento na grade da planilha.
    anchors = []
    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            v = df.iat[r, c]
            if isinstance(v, str) and anchor_re.match(v.strip()):
                anchors.append((r, c, v.strip()))

    # Extrai os registros de cada bloco encontrado.
    rows = []
    
    for r0, c0, nome in anchors:
    
        # A linha das tags fica deslocada do título do bloco por um valor fixo.
        tag_row = r0 + tag_row_offset
    
        # Lê as tags que pertencem às colunas à direita do cabeçalho do equipamento.
        tags = [_clean(df.iat[tag_row, c0 + k]) for k in range(1, n_cols + 1)
                if c0 + k < df.shape[1]]
        r = tag_row + 1

        # Varre todas as linhas do bloco até encontrar uma linha em branco ou outro cabeçalho.
        while r < df.shape[0]:
            bloco = df.iloc[r, c0:c0 + n_cols + 1]
            if bloco.isna().all():
                break  # linha em branco encerra o bloco
            if isinstance(df.iat[r, c0], str) and (anchor_re.match(df.iat[r, c0].strip())):
                break
            rotulo = _clean(df.iat[r, c0])
            for k, tag in enumerate(tags, start=1):
                if tag is None:
                    continue
                rows.append({
                    "equipamento": nome,
                    "tag": tag,
                    "local_tipo": _norm_local(rotulo) if rotulo else None,
                    "local_detalhe": rotulo,
                    "valor": _clean(df.iat[r, c0 + k]),
                })
            r += 1
    return pd.DataFrame(rows)


def parse_sinais(path) -> pd.DataFrame:
    
    # Lê a planilha Excel e transforma os blocos de sinal em um DataFrame padronizado.
    df = pd.read_excel(path, header=None, sheet_name=0)
    out = _read_blocks(df, RE_SINAL, n_cols=4, tag_row_offset=3)
    out["tipo"] = "Sinal"
    
    # Exemplo: "SINAL 123 LUZ" -> "123".
    out["numero"] = out["equipamento"].str.extract(r"SINAL\s+(\S+)")
    
    # Identifica o aspecto pela tag, como "1RGE" -> Vermelho ou "1YGE" -> Amarelo.
    out["aspecto"] = out["tag"].str.extract(r"\d+([RY])GE")[0].map({"R": "Vermelho", "Y": "Amarelo"})
    
    # Se a tag termina em "NX", o sinal tem sentido NX; caso contrário, é considerado normal.
    out["sentido"] = out["tag"].str.endswith("NX").map({True: "NX", False: "Normal"})
    return out


def parse_cdvs(path) -> pd.DataFrame:
    
    # Lê a planilha Excel e transforma os blocos de CDV em um DataFrame padronizado.
    df = pd.read_excel(path, header=None, sheet_name=0)
    out = _read_blocks(df, RE_CDV, n_cols=5, tag_row_offset=3)
    out["tipo"] = "CDV"
    
    # Exemplo: "CDV 456 LUZ" -> "456".
    out["numero"] = out["equipamento"].str.extract(r"CDV\s+(\S+)\s+LUZ")

    # Classifica a função da tag de acordo com o seu sufixo.
    def funcao(t):
        if t.endswith("NCTP") or t.endswith("SCTP"):
            return "Codificação"
        if t.endswith("TPR") or t.endswith("TPRN"):
            return "Indicação"
        return "Outros (N12-CTP)"
    out["funcao"] = out["tag"].map(funcao)
    return out


def carregar_tudo(path_sinais, path_cdvs) -> pd.DataFrame:
    
    # Junta os dados de todos os equipamentos em um único DataFrame para uso posterior.
    return pd.concat([parse_sinais(path_sinais), parse_cdvs(path_cdvs)], ignore_index=True)
