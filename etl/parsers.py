import re
import unicodedata
import pandas as pd

RE_SINAL = re.compile(r"^SINAL\s+(\S+)\s+LUZ$", re.I)
RE_CDV = re.compile(r"^CDV\s+(\S+)\s+LUZ$", re.I)

def _norm_local(txt: str) -> str:
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
    if pd.isna(v):
        return None
    s = str(v).strip()
    return None if s in ("", "-") else s

def _read_blocks(df, anchor_re, n_cols, tag_row_offset):
    anchors = []
    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            v = df.iat[r, c]
            if isinstance(v, str) and anchor_re.match(v.strip()):
                anchors.append((r, c, v.strip()))

    rows = []
    for r0, c0, nome in anchors:
        tag_row = r0 + tag_row_offset
        tags = [_clean(df.iat[tag_row, c0 + k]) for k in range(1, n_cols + 1)
                if c0 + k < df.shape[1]]
        r = tag_row + 1

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
    df = pd.read_excel(path, header=None, sheet_name=0)
    out = _read_blocks(df, RE_SINAL, n_cols=4, tag_row_offset=3)
    out["tipo"] = "Sinal"
    out["numero"] = out["equipamento"].str.extract(r"SINAL\s+(\S+)")
    out["aspecto"] = out["tag"].str.extract(r"\d+([RY])GE")[0].map({"R": "Vermelho", "Y": "Amarelo"})
    out["sentido"] = out["tag"].str.endswith("NX").map({True: "NX", False: "Normal"})
    return out

def parse_cdvs(path) -> pd.DataFrame:
    df = pd.read_excel(path, header=None, sheet_name=0)
    out = _read_blocks(df, RE_CDV, n_cols=5, tag_row_offset=3)
    out["tipo"] = "CDV"
    out["numero"] = out["equipamento"].str.extract(r"CDV\s+(\S+)\s+LUZ")

    def funcao(t):
        if t.endswith("NCTP") or t.endswith("SCTP"):
            return "Codificação"
        if t.endswith("TPR") or t.endswith("TPRN"):
            return "Indicação"
        return "Outros (N12-CTP)"
    out["funcao"] = out["tag"].map(funcao)
    return out

def carregar_tudo(path_sinais, path_cdvs) -> pd.DataFrame:
    return pd.concat([parse_sinais(path_sinais), parse_cdvs(path_cdvs)], ignore_index=True)
