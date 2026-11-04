#!/usr/bin/env python3
"""
Diagrama do procedimento metodológico, da coleta à agregação.

As duas primeiras etapas aparecem separadas por caso, porque a coleta e o
tratamento do material diferem entre os dois sistemas. As seguintes aparecem
em caixa única, porque o procedimento é o mesmo nos dois e só os números
mudam, que é precisamente o que o desenho da pesquisa afirma.

Reaproveita as funções de desenho de `diagramas_processo.py`, de modo que a
figura saia no mesmo estilo das figuras 1 e 2.

    python3 diagrama_metodologia.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "resultados"
sys.path.insert(0, str(BASE))

_spec = importlib.util.spec_from_file_location("dp", BASE / "diagramas_processo.py")
dp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dp)

from analise_lexical import TINTA2  # noqa: E402

# Caixa neutra para as etapas comuns aos dois casos.
dp.COR["AMBOS"] = TINTA2
dp.CLARO["AMBOS"] = "#f2f2f0"

LARG = 48.0
MARG = 1.2                      # margem lateral, para a caixa não encostar na borda
GAP = 3.0                       # vão entre as duas colunas
UTIL = LARG - 2 * MARG
COL = (UTIL - GAP) / 2


def montar():
    etapas_separadas = [
        ("1. Coleta",
         ("FUST", ["414 documentos de origem",
                   "Diários, pronunciamentos, emendas,",
                   "parecer e texto da lei"]),
         ("BEAD", ["391 registros de audiência",
                   "116º ao 119º Congresso",
                   "fevereiro de 2019 a julho de 2026"])),
        ("2. Tratamento do material",
         ("FUST", ["reconhecimento óptico refeito",
                   "segmentação por marcador de orador",
                   "575 unidades de análise"]),
         ("BEAD", ["extração do texto publicado",
                   "42 registros sem texto, com",
                   "a razão declarada em campo próprio",
                   "349 unidades de análise"])),
    ]
    etapas_comuns = [
        ("3. Busca léxica",
         ["lista de 256 termos em 18 subcategorias",
          "passada estrita, com fronteira de palavra, e passada tolerante, que atravessa o defeito de extração",
          "4.053 ocorrências no FUST e 6.702 no BEAD"]),
        ("4. Formação dos pares",
         ["unidade de codificação: o par (fala, subcategoria)",
          "cada ocorrência apresentada com 900 caracteres de cada lado, ajustados para fronteira de período",
          "1.196 pares no FUST e 1.540 no BEAD, 2.736 ao todo"]),
    ]
    eixos = [
        ("5. Codificação\nEixo discursivo",
         ["2.736 pares codificados",
          "ausente, superficial ou estrutural,",
          "por razão declarada e dado"]),
        ("5. Codificação\nEixo normativo",
         ["221 dispositivos do texto aprovado",
          "ausente, superficial ou estrutural,",
          "por mecanismo vinculante"]),
    ]
    fecho = ("6. Agregação e cruzamento",
             ["nível mais alto alcançado em cada subcategoria, com a densidade ao lado",
              "36 células, 18 subcategorias em cada caso",
              "cruzamento dos dois eixos, de que resultam as posições da hipótese"])

    # altura total
    alt = 2.2
    alturas = []
    for tit, (_, l1), (_, l2) in etapas_separadas:
        h = max(dp.altura_caixa(f"{tit}\nFUST", l1), dp.altura_caixa(f"{tit}\nBEAD", l2))
        alturas.append(h); alt += h + 2.6
    for tit, linhas in etapas_comuns:
        h = dp.altura_caixa(tit, linhas); alturas.append(h); alt += h + 2.6
    h_eixo = max(dp.altura_caixa(e[0], e[1]) for e in eixos)
    alturas.append(h_eixo); alt += h_eixo + 2.6
    h_fecho = dp.altura_caixa(fecho[0], fecho[1])
    alturas.append(h_fecho); alt += h_fecho + 1.0

    fig, ax = plt.subplots(figsize=(LARG * dp.ESCALA, alt * dp.ESCALA))
    y = alt - 2.2
    meio = LARG / 2
    esq, dir_ = MARG, MARG + COL + GAP

    for i, (tit, (c1, l1), (c2, l2)) in enumerate(etapas_separadas):
        h = alturas[i]; y -= h
        dp.caixa(ax, esq, y, COL, f"{tit}\n{c1}", l1, c1)
        dp.caixa(ax, dir_, y, COL, f"{tit}\n{c2}", l2, c2)
        if i == 0:
            dp.seta(ax, (esq + COL / 2, y), (esq + COL / 2, y - 2.6))
            dp.seta(ax, (dir_ + COL / 2, y), (dir_ + COL / 2, y - 2.6))
        else:
            dp.seta(ax, (esq + COL / 2, y), (meio - 1.0, y - 2.6), rad=-0.12)
            dp.seta(ax, (dir_ + COL / 2, y), (meio + 1.0, y - 2.6), rad=0.12)
        y -= 2.6

    for j, (tit, linhas) in enumerate(etapas_comuns):
        h = alturas[len(etapas_separadas) + j]; y -= h
        dp.caixa(ax, MARG, y, UTIL, tit, linhas, "AMBOS")
        dp.seta(ax, (meio, y), (meio, y - 2.6))
        y -= 2.6

    y -= h_eixo
    dp.caixa(ax, esq, y, COL, eixos[0][0], eixos[0][1], "AMBOS")
    dp.caixa(ax, dir_, y, COL, eixos[1][0], eixos[1][1], "AMBOS")
    dp.seta(ax, (esq + COL / 2, y), (meio - 1.0, y - 2.6), rad=-0.12)
    dp.seta(ax, (dir_ + COL / 2, y), (meio + 1.0, y - 2.6), rad=0.12)
    y -= 2.6

    y -= h_fecho
    dp.caixa(ax, MARG, y, UTIL, fecho[0], fecho[1], "AMBOS", destaque=True)

    dp.finalizar(fig, ax, LARG, alt,
                 "Procedimento metodológico, da coleta ao cruzamento dos eixos")
    return fig


def main():
    SAIDA.mkdir(exist_ok=True)
    f = montar()
    f.savefig(SAIDA / "figura_3_metodologia.png", dpi=200)
    f.savefig(SAIDA / "figura_3_metodologia.svg")
    print("gravado: resultados/figura_3_metodologia.png e .svg")


if __name__ == "__main__":
    main()
