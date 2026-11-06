#!/usr/bin/env python3
"""
Gráficos que substituem enumeração em prosa e os dois quadros de resultado.

Seis saídas, todas em resultados/:

  grafico_corpus_fust.png/.svg        unidades de fala por casa e origem do texto
  grafico_corpus_bead.png/.svg        depoimentos por tipo de ator
  grafico_modalidade_fust.png/.svg    ocorrências por modalidade de uso da palavra
  grafico_mecanismos.png/.svg         mecanismos vinculantes por tipo e caso
  grafico_eixo_normativo.png/.svg     nível normativo por subcategoria e caso
  grafico_divergencia.png/.svg        combinação dos dois eixos por subcategoria

Por que gráfico e não prosa. As quatro primeiras figuras substituem listas de
números que o texto enumerava frase a frase, e que o leitor não consegue
comparar enquanto lê. As duas últimas substituem quadros de dezoito linhas:
a informação é categórica, de duas a seis classes, e cabe melhor em marcação
por posição e cor do que em célula de tabela.

O escopo normativo é o mesmo declarado em 3.3 e fixado em
coding/agregar_eixo_normativo.py: Lei 9.998/2000, IIJA SEC. 60102 e o Digital
Equity Act incorporado. O recorte temporal vem de recorte.py.

    python3 graficos_novos.py
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from analise_lexical import COR, TINTA, TINTA2, CASOS  # noqa: E402
import recorte  # noqa: E402

SAIDA = BASE / "resultados"
COD = BASE / "coding"
ESCOPO = "com-dea"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# níveis e posições em escala de um mesmo tom, do mais claro ao mais escuro
NIVEL_COR = {"ausente": "#d7dbdf", "superficial": "#8d9aa5",
             "estrutural": "#2e3d49", "não aplicável": "#f0f1f2"}
POSICAO_COR = {
    "coerência": "#2e3d49",
    "retórica sem arquitetura": "#2e3d49",
    "estrutural / superficial": "#8d9aa5",
    "superficial / estrutural": "#b7bfc6",
    "superficial / ausente": "#d7dbdf",
    "não aplicável (sem léxico no sistema)": "#f0f1f2",
}
# A posição em que a hipótese se confirma é destacada por textura, e não por
# cor, de modo que a paleta continua neutra e o destaque sobrevive à impressão
# em preto e branco.
POSICAO_HACHURA = {"retórica sem arquitetura": "////"}
MEC_CURTO = {"critério de elegibilidade": "elegibilidade",
             "percentual destinado": "percentual",
             "obrigação de monitoramento": "monitoramento",
             "meta diferenciada": "meta",
             "nenhum": "", "": ""}
ATOR_PT = {"industry": "indústria", "government": "ente governamental",
           "advocacy": "defesa de direitos", "academic": "universidade",
           "think tank": "instituto de pesquisa aplicada",
           "no organization": "sem vínculo organizacional",
           "unclear": "não classificado pelo documento"}


def ler(p: Path) -> list[dict]:
    if not p.exists():
        raise SystemExit(f"não encontrei {p}")
    return list(csv.DictReader(p.open(encoding="utf-8")))


def escopos() -> dict:
    spec = importlib.util.spec_from_file_location("ag", COD / "agregar_eixo_normativo.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod.ESCOPOS


def gravar(fig, nome: str) -> None:
    fig.savefig(SAIDA / f"{nome}.png")
    fig.savefig(SAIDA / f"{nome}.svg")
    plt.close(fig)
    print("   ", nome)


def barras(rotulos, valores, largura=7.6, sufixo="", altura_linha=0.42):
    """Barras horizontais, maior em cima, com o valor ao lado de cada barra."""
    n = len(rotulos)
    fig, ax = plt.subplots(figsize=(largura, altura_linha * n + 0.9))
    y = list(range(n))[::-1]
    ax.barh(y, valores, height=0.58, color=COR["FUST"], zorder=3)
    for yy, v in zip(y, valores):
        ax.text(v + max(valores) * 0.012, yy, f"{v:,}{sufixo}".replace(",", "."),
                va="center", ha="left", fontsize=8.4, color=TINTA2, zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(rotulos, fontsize=8.6)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    for lado in ("bottom", "left"):
        ax.spines[lado].set_visible(False)
    ax.grid(visible=False)
    ax.margins(x=0.16)
    fig.tight_layout()
    return fig


def grafico_corpus_fust() -> None:
    reg = ler(BASE / "corpus_fust" / "corpus_index.csv")
    chave = {("senado", "senado_api"): "Senado Federal · interface de dados",
             ("senado", "diario_ocr"): "Senado Federal · Diário segmentado",
             ("camara", "diario_ocr"): "Câmara dos Deputados · Diário segmentado"}
    c = Counter((r["casa"], r["source"]) for r in reg)
    itens = sorted(((chave.get(k, str(k)), v) for k, v in c.items()),
                   key=lambda kv: -kv[1])
    gravar(barras([i[0] for i in itens], [i[1] for i in itens], largura=7.4),
           "grafico_corpus_fust")


def grafico_corpus_bead() -> None:
    reg = [r for r in ler(BASE / "corpus_bead" / "arguments_matrix.csv")
           if recorte.manter("BEAD", r["id"])]
    c = Counter(r["actor_type"] for r in reg)
    itens = sorted(((ATOR_PT.get(k, k), v) for k, v in c.items()), key=lambda kv: -kv[1])
    gravar(barras([i[0] for i in itens], [i[1] for i in itens], largura=7.4),
           "grafico_corpus_bead")


def grafico_modalidade() -> None:
    reg = ler(SAIDA / "tabela_modalidade_fust.csv")
    cols = [c for c in reg[0] if c not in ("codigo", "subcategoria", "total")]
    tot = {c: sum(int(r[c] or 0) for r in reg) for c in cols}
    nomes = {"presidencia": "manifestação da presidência",
             "encaminhamento": "encaminhamento de votação",
             "para uma comunicação": "comunicação",
             "para comunicação de liderança": "comunicação de liderança"}
    itens = sorted(((nomes.get(k, k), v) for k, v in tot.items()), key=lambda kv: -kv[1])
    gravar(barras([i[0] for i in itens], [i[1] for i in itens], largura=7.4),
           "grafico_modalidade_fust")


def grafico_mecanismos() -> None:
    disp = ler(COD / "dispositivos_eixo_normativo.csv")
    diplomas = escopos()[ESCOPO]
    sel = [d for d in disp if d["diploma"] in diplomas
           and d["pertinencia"].strip().lower() == "sim"
           and d["nivel_do_dispositivo"].strip() == "estrutural"]
    c = Counter((d["caso"], d["mecanismo_tipo"]) for d in sel)
    tipos = ["critério de elegibilidade", "percentual destinado",
             "obrigação de monitoramento", "meta diferenciada"]
    fig, ax = plt.subplots(figsize=(7.6, 0.72 * len(tipos) + 1.1))
    y = list(range(len(tipos)))[::-1]
    alt = 0.34
    for k, caso in enumerate(CASOS):
        desl = (0.5 - k) * alt * 1.08
        vals = [c.get((caso, t), 0) for t in tipos]
        ax.barh([yy + desl for yy in y], vals, height=alt, color=COR[caso],
                label=caso, zorder=3)
        for yy, v in zip(y, vals):
            ax.text(v + 0.35, yy + desl, str(v), va="center", ha="left",
                    fontsize=8.4, color=TINTA2, zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(tipos, fontsize=8.8)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    for lado in ("bottom", "left"):
        ax.spines[lado].set_visible(False)
    ax.grid(visible=False)
    ax.margins(x=0.14)
    ax.legend(handles=[Patch(facecolor=COR[c_], label=c_) for c_ in CASOS],
              loc="lower right", frameon=False, fontsize=8.6)
    fig.tight_layout()
    gravar(fig, "grafico_mecanismos")


def _matriz(linhas, valor_de, cores, rotulo_de, nome, legenda_ordem, anota=None,
            hachuras=None):
    """Uma coluna por caso, uma linha por subcategoria, marca colorida na célula."""
    codigos = sorted({l["codigo"] for l in linhas},
                     key=lambda c: [int(x) for x in c.split(".")])
    nomes = {l["codigo"]: l["subcategoria"] for l in linhas}
    por = {(l["caso"], l["codigo"]): l for l in linhas}
    y = list(range(len(codigos)))[::-1]
    fig, ax = plt.subplots(figsize=(8.4, 0.40 * len(codigos) + 1.9))
    for k, caso in enumerate(CASOS):
        for yy, cod in zip(y, codigos):
            l = por.get((caso, cod))
            if l is None:
                continue
            v = valor_de(l)
            ax.scatter([k], [yy], s=190, color=cores.get(v, "#f0f1f2"),
                       hatch=(hachuras or {}).get(v), edgecolors="#ffffff",
                       linewidths=1.1, zorder=3)
            if anota:
                t = anota(l)
                if t:
                    ax.text(k + 0.085, yy, t, va="center", ha="left",
                            fontsize=7.0, color=TINTA2, zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{c} {nomes.get(c, '')}" for c in codigos], fontsize=8.4)
    ax.set_xticks(list(range(len(CASOS))))
    ax.set_xticklabels(list(CASOS), fontsize=9.4)
    ax.xaxis.set_ticks_position("top")
    ax.set_xlim(-0.45, len(CASOS) - 0.1)
    ax.tick_params(axis="both", length=0)
    for lado in ("top", "bottom", "left", "right"):
        ax.spines[lado].set_visible(False)
    ax.grid(visible=False)
    marcas = [Patch(facecolor=cores[v], hatch=(hachuras or {}).get(v),
                    edgecolor="#ffffff", linewidth=1.1, label=rotulo_de(v))
              for v in legenda_ordem]
    ax.legend(handles=marcas, loc="upper left", bbox_to_anchor=(0, -0.02),
              ncol=2, frameon=False, fontsize=8.2)
    fig.tight_layout()
    gravar(fig, nome)


def grafico_eixo_normativo() -> None:
    linhas = ler(COD / f"eixo_normativo_{ESCOPO}.csv")
    _matriz(linhas, lambda l: l["nivel"], NIVEL_COR, lambda v: v,
            "grafico_eixo_normativo",
            ["estrutural", "superficial", "ausente"],
            anota=lambda l: MEC_CURTO.get(l.get("mecanismo_tipo", ""), ""))


def grafico_divergencia() -> None:
    linhas = ler(COD / f"tabela4_divergencia_{ESCOPO}.csv")
    presentes = [p for p in POSICAO_COR if any(l["posicao"] == p for l in linhas)]
    _matriz(linhas, lambda l: l["posicao"], POSICAO_COR,
            lambda v: v.replace(" (sem léxico no sistema)", ", sem léxico"),
            "grafico_divergencia", presentes, hachuras=POSICAO_HACHURA)


def main() -> None:
    print("gravado em resultados/:")
    grafico_corpus_fust()
    grafico_corpus_bead()
    grafico_modalidade()
    grafico_mecanismos()
    grafico_eixo_normativo()
    grafico_divergencia()


if __name__ == "__main__":
    main()
