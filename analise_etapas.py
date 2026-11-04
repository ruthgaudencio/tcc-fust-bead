"""
Etiqueta cada unidade do corpus com a etapa do processo legislativo em que foi
produzida, e calcula a densidade do nível estrutural por etapa.

Responde à pergunta que a hipótese formula no tempo: a invocação fundamentada da
equidade se distribui igualmente ao longo do processo, ou se concentra nas fases
de discussão e rareia nas fases de decisão?

As fronteiras do caso brasileiro saem de corpus_fust/camara/tramitacoes.json, o
registro oficial de tramitação do PL 3.808/1997, e cada uma traz o despacho que
a fixa, de modo que a periodização seja conferível e não arbitrada aqui.

O caso norte-americano não tem tramitação única: o BEAD resulta de uma cadeia de
projetos anteriores incorporados à Infrastructure Investment and Jobs Act. A
fronteira que o corpus permite fixar com segurança é a promulgação, que separa a
formação da agenda da fiscalização da execução.

    python3 analise_etapas.py
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent

import recorte
SAIDA = BASE / "resultados"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# (ordem, rótulo, início, fim inclusive, marco documental)
ETAPAS = {
    "FUST": [
        (1, "Comissão na Câmara", "1997-11-05", "1999-10-25",
         "apresentação do projeto pelo Dep. José Pimentel; instrução na CCTCI"),
        (2, "Plenário da Câmara", "1999-10-26", "1999-12-07",
         "aprovação do requerimento de urgência dos líderes"),
        (3, "Senado Federal", "1999-12-08", "2000-08-01",
         "remessa ao Senado pelo Ofício PS-GSE/387/99"),
        (4, "Sanção e veto parcial", "2000-08-02", "2000-10-18",
         "Ofício 1190-SF comunicando remessa à sanção; Lei 9.998 em 17/08/2000"),
        (5, "Apreciação do veto", "2000-10-19", "2008-12-31",
         "leitura da Mensagem 788/00-CN no Congresso Nacional"),
    ],
    # As etapas norte-americanas são ancoradas no Congresso de cada audiência,
    # que é campo do próprio índice do corpus, e na data da promulgação, que
    # parte o 117º Congresso em dois. A cadeia de projetos que antecede o
    # programa está documentada em bead-witnesses/archive/CONTEXT.md.
    "BEAD": [
        (1, "Projetos de origem (116º)", "2019-01-03", "2021-01-02",
         "Digital Equity Act, S. 1167 e H.R. 4486, de 2019, e AAIA, H.R. 7302, de 2020"),
        (2, "Incorporação à IIJA (117º, até a promulgação)", "2021-01-03", "2021-11-14",
         "BRIDGE Act, S. 2071, e incorporação à Infrastructure Investment and Jobs Act"),
        (3, "Início da execução (117º, após a promulgação)", "2021-11-15", "2023-01-02",
         "promulgação da IIJA, P.L. 117-58, em 15/11/2021"),
        (4, "Fiscalização (118º)", "2023-01-03", "2025-01-02",
         "audiências de acompanhamento da execução do programa"),
        (5, "Fiscalização (119º)", "2025-01-03", "2030-12-31",
         "audiências de acompanhamento da execução do programa"),
    ],
}


def etapa_de(caso: str, data: str):
    try:
        d = dt.date.fromisoformat(data[:10])
    except ValueError:
        return None
    for ordem, rotulo, ini, fim, marco in ETAPAS[caso]:
        if dt.date.fromisoformat(ini) <= d <= dt.date.fromisoformat(fim):
            return ordem, rotulo
    return None


def ler(p: Path) -> list[dict]:
    if not p.exists():
        raise SystemExit(f"não encontrei {p}")
    return list(csv.DictReader(p.open(encoding="utf-8")))




# ---------------------------------------------------------------- figura

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch  # noqa: E402
sys.path.insert(0, str(BASE))
from analise_lexical import COR, HACHURA, TINTA, TINTA2, SUPERFICIE  # noqa: E402


def figura_etapas(caso: str, linhas: list[dict]):
    """Volume e densidade por etapa, em dois painéis que partilham o eixo das
    etapas. Duas medidas de escalas diferentes não partilham eixo: o volume
    está em pares e a densidade em porcentagem, e por isso saem separadas.

    A imagem leva apenas o gráfico. A nota sobre o gênero das falas da etapa 2
    do caso brasileiro vai abaixo da figura, no texto, em NOTA_FUST."""
    ls = [l for l in linhas if l["caso"] == caso]
    if not ls:
        return None
    ls.sort(key=lambda l: l["ordem"], reverse=True)   # etapa 1 no topo
    rot = [f"{l['ordem']}. {l['etapa']}" for l in ls]
    vol = [l["pares_pertinentes"] for l in ls]
    den = [float(l["densidade_estrutural_pct"]) if l["densidade_estrutural_pct"] != "" else 0.0
           for l in ls]
    y = range(len(ls))

    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(11.2, 0.62 * len(ls) + 2.4), sharey=True,
        gridspec_kw={"width_ratios": [1, 1], "wspace": 0.08})

    a1.barh(list(y), vol, height=0.56, color=COR[caso], hatch=HACHURA[caso],
            edgecolor=SUPERFICIE, linewidth=1.2, zorder=3)
    for i, v in enumerate(vol):
        a1.text(v + max(vol) * 0.015, i, f"{v}", va="center", ha="left",
                fontsize=8, color=TINTA2, zorder=4)
    a1.set_xlabel("menções válidas (pares pertinentes)")
    a1.set_title("Volume do debate", fontsize=10, loc="left", pad=8)

    a2.barh(list(y), den, height=0.56, color=COR[caso], hatch=HACHURA[caso],
            edgecolor=SUPERFICIE, linewidth=1.2, zorder=3)
    for i, (d, l) in enumerate(zip(den, ls)):
        txt = f"{d:.1f}%" if l["pares_pertinentes"] >= 5 else "base insuficiente"
        a2.text(d + max(max(den), 1) * 0.02, i, txt, va="center", ha="left",
                fontsize=8, color=TINTA2, zorder=4)
    a2.set_xlabel("densidade do nível estrutural, em %")
    a2.set_title("Qualidade do debate", fontsize=10, loc="left", pad=8)

    a1.set_yticks(list(y))
    a1.set_yticklabels(rot, fontsize=8.5)
    for ax in (a1, a2):
        ax.grid(axis="y", visible=False)
        ax.margins(x=0.18)
    fig.suptitle(f"Debate sobre desigualdade por etapa do processo legislativo — {caso}",
                 fontsize=11, x=0.012, ha="left", y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    return fig



def figura_etapas_comparada(linhas: list[dict]):
    """Volume e densidade por etapa, com os dois casos na mesma figura.

    Antes eram duas figuras, uma por caso, e a comparação dependia de o leitor
    guardar a primeira enquanto lia a segunda. Aqui as etapas dos dois processos
    partilham o eixo da densidade, de modo que a comparação se faça de uma vez.

    A ordem é a do processo dentro de cada caso, e um filete separa os blocos.
    Cor e hachura distinguem os casos, porque cor sozinha não carrega identidade
    em impressão preto e branco."""
    blocos = []
    for caso in ("FUST", "BEAD"):
        ls = [l for l in linhas if l["caso"] == caso]
        ls.sort(key=lambda l: l["ordem"])
        if ls:
            blocos.append((caso, ls))
    if not blocos:
        return None

    ordenadas = []            # de cima para baixo
    for caso, ls in blocos:
        for l in ls:
            ordenadas.append((caso, l))
    ordenadas.reverse()       # barh conta de baixo para cima

    rot = [f"{c}  {l['ordem']}. {l['etapa']}" for c, l in ordenadas]
    vol = [l["pares_pertinentes"] for _, l in ordenadas]
    den = [float(l["densidade_estrutural_pct"]) if l["densidade_estrutural_pct"] != "" else 0.0
           for _, l in ordenadas]
    cores = [COR[c] for c, _ in ordenadas]
    hachs = [HACHURA[c] for c, _ in ordenadas]
    y = list(range(len(ordenadas)))

    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(12.0, 0.62 * len(ordenadas) + 2.8), sharey=True,
        gridspec_kw={"width_ratios": [1, 1], "wspace": 0.08})

    for ax, dados, rotulo, titulo in (
            (a1, vol, "menções válidas (pares pertinentes)", "Volume do debate"),
            (a2, den, "densidade do nível estrutural, em %", "Qualidade do debate")):
        for i, (v, cor, h) in enumerate(zip(dados, cores, hachs)):
            ax.barh(i, v, height=0.56, color=cor, hatch=h,
                    edgecolor=SUPERFICIE, linewidth=1.2, zorder=3)
        ax.set_xlabel(rotulo)
        ax.set_title(titulo, fontsize=10, loc="left", pad=8)
        ax.grid(axis="y", visible=False)
        ax.margins(x=0.20)

    maxv = max(vol) if vol else 1
    for i, v in enumerate(vol):
        a1.text(v + maxv * 0.015, i, f"{v}", va="center", ha="left",
                fontsize=8, color=TINTA2, zorder=4)
    maxd = max(max(den), 1)
    for i, (d, (_, l)) in enumerate(zip(den, ordenadas)):
        txt = f"{d:.1f}%" if l["pares_pertinentes"] >= 5 else "base insuficiente"
        a2.text(d + maxd * 0.02, i, txt, va="center", ha="left",
                fontsize=8, color=TINTA2, zorder=4)

    # filete entre os dois blocos
    n_segundo = len(blocos[1][1]) if len(blocos) > 1 else 0
    if n_segundo:
        for ax in (a1, a2):
            ax.axhline(n_segundo - 0.5, color=TINTA2, linewidth=0.8,
                       alpha=0.35, zorder=2)

    a1.set_yticks(y)
    a1.set_yticklabels(rot, fontsize=8.5)
    marcas = [Patch(facecolor=COR[c], hatch=HACHURA[c], edgecolor=SUPERFICIE,
                    label=c) for c, _ in blocos]
    fig.legend(handles=marcas, loc="lower left", bbox_to_anchor=(0.012, 0.0),
               ncol=2, frameon=False, fontsize=9)
    fig.suptitle("Debate sobre desigualdade por etapa do processo legislativo",
                 fontsize=11, x=0.012, ha="left", y=0.99)
    fig.tight_layout(rect=(0, 0.055, 1, 0.955))
    return fig


NOTA_FUST = ("Nota: a etapa 2 é composta de intervenções processuais e de falas da presidência, com mediana de 2.358 caracteres,\n"
             "contra 11.786 na etapa 3. A ausência de nível estrutural nela decorre do gênero das falas disponíveis, e não permite\n"
             "conclusão sobre a etapa. A etapa 1, de comissão, não tem unidade alguma no corpus.")


def main():
    SAIDA.mkdir(exist_ok=True)
    pares = ler(BASE / "coding" / "pares_eixo_discursivo.csv")
    pares = recorte.filtrar_pares(pares)
    idx = {}
    for caso, sub in (("FUST", "corpus_fust"), ("BEAD", "corpus_bead")):
        for r in ler(BASE / sub / "corpus_index.csv"):
            idx[(caso, r["id"])] = (r.get("data") or r.get("date") or "").strip()

    # por etapa
    agreg = defaultdict(lambda: {"pares": 0, "pert": 0, "estr": 0, "falso": 0,
                                 "unidades": set(), "subcats": set()})
    sem_etapa = 0
    for p in pares:
        caso = p.get("caso", "")
        data = idx.get((caso, p.get("unit_id", "")), "")
        et = etapa_de(caso, data) if data else None
        if not et:
            sem_etapa += 1
            continue
        a = agreg[(caso, et[0], et[1])]
        a["pares"] += 1
        a["unidades"].add(p.get("unit_id", ""))
        nivel = (p.get("nivel_do_par") or "").strip().lower()
        if (p.get("pertinencia") or "").strip().lower() == "sim":
            a["pert"] += 1
            a["subcats"].add(p.get("subcategoria", ""))
            if nivel == "estrutural":
                a["estr"] += 1
        if nivel == "falso_positivo":
            a["falso"] += 1

    linhas = []
    for (caso, ordem, rotulo), a in sorted(agreg.items()):
        marco = next(m for o, r, i, f, m in ETAPAS[caso] if o == ordem)
        linhas.append({
            "caso": caso, "ordem": ordem, "etapa": rotulo,
            "unidades": len(a["unidades"]), "pares": a["pares"],
            "pares_pertinentes": a["pert"], "pares_estruturais": a["estr"],
            "densidade_estrutural_pct": round(100 * a["estr"] / a["pert"], 1) if a["pert"] else "",
            "subcategorias_invocadas": len(a["subcats"]),
            "falso_positivo_pct": round(100 * a["falso"] / a["pares"], 1) if a["pares"] else "",
            "marco_documental": marco,
        })
    with (SAIDA / "tabela5_densidade_por_etapa.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)

    # por etapa x subcategoria, só onde há base
    det = defaultdict(lambda: {"pert": 0, "estr": 0})
    for p in pares:
        caso = p.get("caso", "")
        data = idx.get((caso, p.get("unit_id", "")), "")
        et = etapa_de(caso, data) if data else None
        if not et or (p.get("pertinencia") or "").strip().lower() != "sim":
            continue
        k = (caso, et[0], et[1], (p.get("codigo") or "").strip(), (p.get("subcategoria") or "").strip())
        det[k]["pert"] += 1
        if (p.get("nivel_do_par") or "").strip().lower() == "estrutural":
            det[k]["estr"] += 1
    linhas2 = [{"caso": c, "ordem": o, "etapa": e, "codigo": cod, "subcategoria": s,
                "pares_pertinentes": v["pert"], "pares_estruturais": v["estr"],
                "densidade_estrutural_pct": round(100 * v["estr"] / v["pert"], 1) if v["pert"] else ""}
               for (c, o, e, cod, s), v in sorted(det.items())]
    with (SAIDA / "tabela6_etapa_por_subcategoria.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas2[0])); w.writeheader(); w.writerows(linhas2)

    if sem_etapa:
        print(f"aviso: {sem_etapa} pares sem data utilizável ou fora das faixas\n")
    print(f"{'caso':5s} {'etapa':26s} {'unid':>5s} {'pares':>6s} {'pert':>5s} {'estrut':>6s} {'dens':>7s} {'subcats':>7s}")
    for l in linhas:
        print(f"{l['caso']:5s} {l['etapa'][:26]:26s} {l['unidades']:5d} {l['pares']:6d} "
              f"{l['pares_pertinentes']:5d} {l['pares_estruturais']:6d} "
              f"{str(l['densidade_estrutural_pct'])+'%':>7s} {l['subcategorias_invocadas']:7d}")
    f = figura_etapas_comparada(linhas)
    if f:
        for nome in ("figura_9_etapas_comparada",):
            f.savefig(SAIDA / f"{nome}.png")
            f.savefig(SAIDA / f"{nome}.svg")
            print(f"   figura: {nome}.png")
    print("\ngravado em resultados/: tabela5_densidade_por_etapa.csv, "
          "tabela6_etapa_por_subcategoria.csv e as duas figuras por etapa")


if __name__ == "__main__":
    main()
