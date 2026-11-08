"""
Esquemas dos dois processos legislativos, com o que foi coletado de cada etapa.

O desenho dos dois difere porque os processos diferem, e essa é a informação
principal que as figuras carregam: o caso brasileiro é cadeia linear, um projeto
percorrendo casas e fases até a sanção; o caso norte-americano é convergência,
projetos distintos incorporados a uma lei única de infraestrutura.

Datas e movimentações do lado brasileiro saem de
corpus_fust/camara/tramitacoes.json. A cadeia de projetos do lado
norte-americano está documentada em bead-witnesses/archive/CONTEXT.md.

    python3 diagramas_processo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "resultados"
sys.path.insert(0, str(BASE))
from analise_lexical import COR, TINTA, TINTA2, SUPERFICIE  # noqa: E402

# Preenchimento neutro: quem distingue os dois casos é a cor da borda, vinda de
# COR, e não um matiz que evoque as bandeiras dos dois países.
CLARO = {"FUST": "#e9ecef", "BEAD": "#f5f6f7"}


# O desenho usa unidades de conteúdo, e não frações da figura: uma unidade é a
# altura de uma linha de texto. A figura é dimensionada no fim, a partir da
# extensão ocupada. Posicionar em frações fixas quebra assim que um item cresce.
U_TIT, U_LIN, U_PAD = 1.45, 1.05, 0.75
ESCALA = 0.235          # polegadas por unidade
# O contorno arredondado e desenhado 0.12 para fora do retangulo da caixa.
# Sem esta folga a borda inferior da ultima caixa cai fora do eixo e some.
MARGEM_INF = 0.6


def altura_caixa(titulo, linhas):
    return U_PAD * 2 + U_TIT * (1 + titulo.count("\n")) + U_LIN * len(linhas)


def caixa(ax, x, y, w, titulo, linhas, caso, destaque=False):
    """Desenha a partir do canto inferior esquerdo; devolve a altura usada."""
    h = altura_caixa(titulo, linhas)
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.12,rounding_size=0.25",
        linewidth=2.0 if destaque else 1.2,
        edgecolor=COR[caso], facecolor=CLARO[caso], zorder=2))
    ax.text(x + w / 2, y + h - U_PAD, titulo, ha="center", va="top",
            fontsize=9.2, color=TINTA, weight="bold" if destaque else "normal",
            zorder=3, linespacing=1.35)
    y0 = y + h - U_PAD - U_TIT * (1 + titulo.count("\n"))
    for i, t in enumerate(linhas):
        ax.text(x + w / 2, y0 - i * U_LIN, t, ha="center", va="top",
                fontsize=7.8, color=TINTA2, zorder=3)
    return h


def seta(ax, p1, p2, rad=0.0):
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle="-|>", mutation_scale=13, linewidth=1.3,
        color=TINTA2, zorder=1, connectionstyle=f"arc3,rad={rad}",
        shrinkA=3, shrinkB=5))


def finalizar(fig, ax, larg, alt, titulo):
    ax.set_xlim(0, larg); ax.set_ylim(0, alt); ax.axis("off")
    # Sem título dentro da imagem: o achado vai na legenda do documento.
    del titulo
    fig.tight_layout(pad=0.6)


def diagrama_fust():
    etapas = [
        ("1. Comissão na Câmara dos Deputados",
         ["5 de novembro de 1997 a 25 de outubro de 1999 · 24 movimentações",
          "PL 3.808/1997, apensado ao PL 3.938/1997",
          "três relatores na CCTCI, dois substitutivos, 30 emendas",
          "nenhuma unidade no corpus"]),
        ("2. Plenário da Câmara dos Deputados",
         ["26 de outubro a 7 de dezembro de 1999 · 8 movimentações",
          "urgência dos líderes, discussão em turno único e aprovação",
          "8 Diários da Câmara coletados; 2 com sessão de debate",
          "142 falas segmentadas por orador"]),
        ("3. Senado Federal",
         ["8 de dezembro de 1999 a 1º de agosto de 2000",
          "remessa pelo Ofício PS-GSE/387/99 · Parecer nº 712/2000 da CI",
          "9 Diários do Senado, 2 segmentados; 352 pronunciamentos",
          "421 falas em 97 sessões"]),
        ("4. Sanção e veto parcial",
         ["2 de agosto a 18 de outubro de 2000",
          "Lei nº 9.998, de 17 de agosto de 2000, vetada parcialmente",
          "12 pronunciamentos em 11 sessões"]),
        ("5. Apreciação do veto no Congresso Nacional",
         ["19 de outubro de 2000 a 3 de abril de 2008 · 7 movimentações",
          "Mensagem 788/00-CN; veto declarado prejudicado em 2008",
          "nenhuma unidade no corpus"]),
    ]
    vao, larg = 1.3, 34.0
    alt = (sum(altura_caixa(t, l) for t, l in etapas)
           + vao * (len(etapas) - 1) + 2.2 + MARGEM_INF)
    fig, ax = plt.subplots(figsize=(larg * ESCALA, alt * ESCALA))
    y = alt - 2.2
    for i, (tit, ls) in enumerate(etapas):
        h = altura_caixa(tit, ls)
        caixa(ax, 0.3, y - h, larg - 0.6, tit, ls, "FUST")
        if i < len(etapas) - 1:
            seta(ax, (larg / 2, y - h), (larg / 2, y - h - vao))
        y -= h + vao
    finalizar(fig, ax, larg, alt,
              "Processo legislativo do FUST: do PL 3.808/1997 à Lei nº 9.998/2000")
    return fig


def diagrama_bead():
    origem = [
        ("Digital Equity Act, 2019", ["S. 1167 e H.R. 4486", "116º Congresso"]),
        ("Accessible, Affordable Internet\npara All Act, 2020", ["H.R. 7302", "116º Congresso"]),
        ("BRIDGE Act, 2021", ["S. 2071", "117º Congresso"]),
    ]
    origem[1] = ("Accessible, Affordable Internet\nfor All Act, 2020",
                 ["H.R. 7302", "116º Congresso"])
    tit_i = "Infrastructure Investment and Jobs Act"
    lin_i = ["H.R. 3684 · P.L. 117-58",
             "promulgada em 15 de novembro de 2021",
             "institui o BEAD na SEC. 60102"]
    banda = [("Corpus de audiências",
              ["116º Congresso e 117º até a promulgação",
               "38 audiências · 173 depoimentos"])]

    vao, larg = 1.0, 40.0
    h_cadeia = sum(altura_caixa(t, l) for t, l in origem) + vao * (len(origem) - 1)
    h_banda = max(altura_caixa(t, l) for t, l in banda)
    alt = 2.2 + h_cadeia + 3.0 + h_banda + 1.6
    fig, ax = plt.subplots(figsize=(larg * ESCALA, alt * ESCALA))

    w, x0 = 13.0, 0.3
    topo = alt - 2.2
    y, centros = topo, []
    for tit, ls in origem:
        h = altura_caixa(tit, ls)
        caixa(ax, x0, y - h, w, tit, ls, "BEAD")
        centros.append(y - h / 2)
        y -= h + vao

    hi = altura_caixa(tit_i, lin_i)
    xi, wi = 19.0, larg - 19.3
    yi = (centros[0] + centros[-1]) / 2 - hi / 2
    caixa(ax, xi, yi, wi, tit_i, lin_i, "BEAD", destaque=True)
    for cy in centros:
        seta(ax, (x0 + w, cy), (xi, yi + hi / 2), rad=0.10)

    yb = 1.6
    caixa(ax, 0.3, yb, larg - 0.6, *banda[0], "BEAD")
    ax.text(larg / 2, 0.6, "a promulgação é o termo final do corpus de audiências",
            ha="center", va="center", fontsize=7.8, color=TINTA2)
    finalizar(fig, ax, larg, alt,
              "Processo legislativo do BEAD: a cadeia de projetos incorporada à IIJA")
    return fig


def main():
    SAIDA.mkdir(exist_ok=True)
    for nome, f in (("figura_1_processo_fust", diagrama_fust()),
                    ("figura_2_processo_bead", diagrama_bead())):
        f.savefig(SAIDA / f"{nome}.png", dpi=200)
        f.savefig(SAIDA / f"{nome}.svg")
        print(f"   {nome}.png / .svg")
    print(f"\ngravado em {SAIDA}")


if __name__ == "__main__":
    main()
