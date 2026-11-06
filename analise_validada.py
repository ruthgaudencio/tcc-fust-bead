"""
Resultados depois da codificação: Tabela 2 com densidade, Tabela 1 validada e a
figura da densidade estrutural.

Três saídas, todas em resultados/:

  tabela2_eixo_discursivo.csv   as 34 células com o nível agregado E a densidade
  tabela1_validada.csv          contagem lexical ao lado da contagem pertinente
  figura_8_densidade.png/.svg   densidade estrutural por subcategoria e caso

Por que a densidade. O nível de cada célula é o mais alto alcançado, conforme a
seção 3.3: basta um par estrutural para a célula ser estrutural. Com densidade
de 17,6% no caso brasileiro e 23,8% no norte-americano, toda célula com algumas
dezenas de pares alcança esse nível, e o resultado é que 31 das 34 células dizem
a mesma coisa. A densidade, que é a proporção de pares estruturais dentro da
célula, usa a mesma codificação e distingue o que o nível não distingue. As duas
medidas respondem a perguntas diferentes: o nível responde se chegou a
acontecer, a densidade responde quão difundido foi.

Por que a Tabela 1 validada. A Tabela 1 conta ocorrência de termo da lista, e a
codificação mostrou que a taxa de falso positivo varia de 0% a 60,6% conforme a
célula. A contagem pertinente desconta os pares em que o termo não invoca a
subcategoria, e é ela que sustenta afirmação sobre menção.

    python3 analise_validada.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# paleta e estilo vêm de analise_lexical.py, para haver uma fonte só
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analise_lexical import COR, HACHURA, TINTA2, SUPERFICIE, CASOS  # noqa: E402

BASE = Path(__file__).resolve().parent

import recorte
SAIDA = BASE / "resultados"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def ler(p: Path) -> list[dict]:
    if not p.exists():
        raise SystemExit(f"não encontrei {p}")
    return list(csv.DictReader(p.open(encoding="utf-8")))


def i(v) -> int:
    v = str(v or "").strip()
    return int(v) if v.lstrip("-").isdigit() else 0


def main():
    SAIDA.mkdir(exist_ok=True)
    celulas = ler(BASE / "coding" / "eixo_discursivo.csv")
    pares = ler(BASE / "coding" / "pares_eixo_discursivo.csv")
    pares = recorte.filtrar_pares(pares)
    cobertura = ler(SAIDA / "tabela1_cobertura.csv")

    # ---------- Tabela 2: nível + densidade
    linhas2 = []
    for c in celulas:
        n = i(c.get("n_pares"))
        e, s = i(c.get("n_pares_estrutural")), i(c.get("n_pares_superficial"))
        f, ind = i(c.get("n_pares_falso_positivo")), i(c.get("n_pares_indeterminado"))
        pert = n - f - ind
        linhas2.append({
            "caso": c.get("caso", ""),
            "codigo": c.get("codigo_subcategoria", ""),
            "subcategoria": c.get("nome_subcategoria", ""),
            "nivel": c.get("nivel", ""),
            "pares": n, "pares_pertinentes": pert,
            "estrutural": e, "superficial": s, "falso_positivo": f, "indeterminado": ind,
            # densidade sobre os pares PERTINENTES: o falso positivo não é
            # menção, então não pertence ao denominador
            "densidade_estrutural_pct": round(100 * e / pert, 1) if pert else "",
            "taxa_falso_positivo_pct": round(100 * f / n, 1) if n else "",
            "evidencia_verbatim": c.get("evidencia_verbatim", ""),
        })
    cols2 = list(linhas2[0])
    with (SAIDA / "tabela2_eixo_discursivo.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols2); w.writeheader(); w.writerows(linhas2)

    # ---------- Tabela 1 validada: unidades lexicais x unidades pertinentes
    # A base é a mesma do denominador da densidade: pares cujo nível foi
    # decidido, isto é, estrutural ou superficial. Pares pertinentes de nível
    # indeterminado ficam fora, pelo mesmo critério que os exclui da base de
    # cálculo da confiabilidade: o nível não foi decidido porque as janelas
    # exibidas não bastaram, e contá-los no denominador afirmaria ausência de
    # fundamentação que a leitura não constatou.
    NIVEIS_DECIDIDOS = ("estrutural", "superficial")
    unid = defaultdict(set)
    for p in pares:
        if (p.get("nivel_do_par") or "").strip().lower() in NIVEIS_DECIDIDOS:
            unid[(p.get("caso", ""), (p.get("subcategoria") or "").strip())].add(p.get("unit_id", ""))
    linhas1 = []
    for c in cobertura:
        linha = {"codigo": c["codigo"], "categoria": c["categoria"], "subcategoria": c["subcategoria"]}
        for caso in CASOS:
            lex = c.get(f"{caso}_unidades", "")
            if str(lex).strip() == "":
                linha[f"{caso}_unidades_lexicais"] = ""
                linha[f"{caso}_unidades_pertinentes"] = ""
                linha[f"{caso}_reducao_pct"] = ""
                linha[f"{caso}_situacao"] = c.get(f"{caso}_situacao", "")
                continue
            lex = i(lex)
            val = len(unid.get((caso, c["subcategoria"]), set()))
            linha[f"{caso}_unidades_lexicais"] = lex
            linha[f"{caso}_unidades_pertinentes"] = val
            linha[f"{caso}_reducao_pct"] = round(100 * (lex - val) / lex, 1) if lex else ""
            linha[f"{caso}_situacao"] = c.get(f"{caso}_situacao", "")
        linhas1.append(linha)
    cols1 = list(linhas1[0])
    with (SAIDA / "tabela1_validada.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols1); w.writeheader(); w.writerows(linhas1)

    # ---------- Figura 4: densidade estrutural
    por = {(l["caso"], l["codigo"]): l for l in linhas2}
    codigos = sorted({l["codigo"] for l in linhas2}, key=lambda c: [int(x) for x in c.split(".")])
    vis = list(reversed(codigos))
    alt = 0.38
    fig, ax = plt.subplots(figsize=(8.2, 0.42 * len(vis) + 1.6))
    for k, caso in enumerate(CASOS):
        desl = (0.5 - k) * alt * 1.06
        vals, rot = [], []
        for cod in vis:
            l = por.get((caso, cod))
            d = l["densidade_estrutural_pct"] if l else ""
            vals.append(float(d) if d != "" else 0.0)
            rot.append(d)
        ax.barh([y + desl for y in range(len(vis))], vals, height=alt, color=COR[caso],
                hatch=HACHURA[caso], edgecolor=SUPERFICIE, linewidth=1.2, label=caso, zorder=3)
        for y, (v, d) in enumerate(zip(vals, rot)):
            if d == "":
                ax.text(0.4, y + desl, "sem léxico", va="center", ha="left",
                        fontsize=7.2, style="italic", color=TINTA2, zorder=4)
            else:
                ax.text(v + 0.5, y + desl, f"{v:.1f}%", va="center", ha="left",
                        fontsize=7.4, color=TINTA2, zorder=4)
    nomes = {l["codigo"]: l["subcategoria"] for l in linhas2}
    ax.set_yticks(range(len(vis)))
    ax.set_yticklabels([f"{c} {nomes.get(c, '')}" for c in vis], fontsize=8)
    ax.set_xlabel("pares estruturais, em % dos pares pertinentes")
    ax.set_title("Densidade do nível estrutural por subcategoria\n"
                 "proporção das menções válidas em que há razão declarada e dado",
                 fontsize=10.5, loc="left", pad=12)
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[Patch(facecolor=COR[c], hatch=HACHURA[c], edgecolor=SUPERFICIE, label=c)
                       for c in CASOS], loc="lower right", frameon=False, fontsize=8.5)
    ax.margins(x=0.14)
    fig.tight_layout()
    fig.savefig(SAIDA / "figura_8_densidade.png")
    fig.savefig(SAIDA / "figura_8_densidade.svg")

    print("gravado em resultados/:")
    for n in ("tabela2_eixo_discursivo.csv", "tabela1_validada.csv",
              "figura_8_densidade.png", "figura_8_densidade.svg"):
        print("   ", n)
    print()
    print(f"{'caso':5s} {'cod':5s} {'subcategoria':38s} {'nivel':12s} {'dens':>7s} {'falso+':>7s}")
    for l in sorted(linhas2, key=lambda x: (x["caso"], x["codigo"])):
        print(f"{l['caso']:5s} {l['codigo']:5s} {l['subcategoria'][:38]:38s} {l['nivel']:12s} "
              f"{str(l['densidade_estrutural_pct'])+'%':>7s} {str(l['taxa_falso_positivo_pct'])+'%':>7s}")


if __name__ == "__main__":
    main()
