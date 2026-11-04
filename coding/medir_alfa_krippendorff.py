#!/usr/bin/env python3
"""
Calcula o alfa de Krippendorff sobre a mesma amostra de confiabilidade usada
por `medir_confiabilidade.py`, que reporta kappa de Cohen.

Motivo de haver as duas medidas. O kappa de Cohen é definido para dois
codificadores e corrige o acaso pelas marginais de cada um separadamente. O
alfa de Krippendorff admite qualquer número de codificadores, admite dados
faltantes e corrige o acaso por uma distribuição única, obtida do conjunto das
atribuições. A literatura de codificação por especialista em pesquisa jurídica
recomenda o alfa (OVADEK; SCHROEDER; ZGLINSKI, 2024), e fixa faixas próprias:
acima de 0,80 confiável; entre 0,667 e 0,80 sustenta conclusão tentativa;
abaixo de 0,667 recomenda-se descartar. Essas faixas são do alfa e não se
transferem ao kappa, cuja referência usual é a de Landis e Koch (1977).

São reportadas duas métricas de diferença. A nominal trata qualquer
discordância como igual. A ordinal pesa a distância na escala, de sorte que
discordar entre ausente e estrutural pesa mais do que entre níveis vizinhos.
Para a escala de três níveis a ordinal é a pertinente; a nominal fica como
piso conservador.

    python3 coding/medir_alfa_krippendorff.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent

import sys
sys.path.insert(0, str(AQUI.parent))
import recorte
NIVEIS = ["falso_positivo", "superficial", "estrutural"]


def ler(caminho: Path, chave: str = "par_id") -> dict[str, dict]:
    with caminho.open(encoding="utf-8") as f:
        return {l[chave]: l for l in csv.DictReader(f)}


def alfa(a: list[str], b: list[str], cats: list[str], metrica: str = "nominal") -> tuple[float, float, float]:
    """Alfa de Krippendorff para dois codificadores com dados completos.

    Monta a matriz de coincidencias, nao a de contingencia: cada unidade
    contribui com os dois pares ordenados de suas atribuicoes, de modo que a
    matriz e simetrica e totaliza 2N atribuicoes.

    Devolve (Do, De, alfa).
    """
    if not a:
        return 0.0, 0.0, 1.0

    n_total = 2 * len(a)
    marg = Counter(a) + Counter(b)
    for c in cats:
        marg.setdefault(c, 0)
    idx = {c: i for i, c in enumerate(cats)}

    def delta2(c: str, k: str) -> float:
        if metrica == "nominal":
            return 0.0 if c == k else 1.0
        i, j = sorted((idx[c], idx[k]))
        soma = sum(marg[cats[g]] for g in range(i, j + 1))
        return (soma - (marg[c] + marg[k]) / 2.0) ** 2

    # Discordancia observada: media de delta2 sobre as unidades.
    do = sum(delta2(x, y) for x, y in zip(a, b)) / len(a)

    # Discordancia esperada: sobre todos os pares de atribuicoes do conjunto.
    de = sum(
        marg[c] * marg[k] * delta2(c, k)
        for c in cats
        for k in cats
    ) / (n_total * (n_total - 1))

    return do, de, (1.0 - do / de) if de > 0 else 1.0


def faixa(v: float) -> str:
    if v >= 0.80:
        return "confiavel"
    if v >= 0.667:
        return "conclusao tentativa"
    return "abaixo do limiar de descarte"


def bloco(rotulo: str, pares: list[str], um: dict, dois: dict, campo: str, cats: list[str]) -> None:
    a = [um[p][campo] for p in pares]
    b = [dois[p][campo] for p in pares]
    print(f"  {rotulo} ({len(pares)} pares)")
    for metrica in ("nominal", "ordinal") if len(cats) > 2 else ("nominal",):
        do, de, al = alfa(a, b, cats, metrica)
        print(f"     alfa {metrica:<8} Do={do:.4f}  De={de:.4f}  alfa={al:.3f}   [{faixa(al)}]")


def main() -> None:
    um = ler(AQUI / "pares_eixo_discursivo.csv")
    dois = ler(AQUI / "pares_confiabilidade_recorte.csv")
    amostra = [l["par_id"] for l in csv.DictReader((AQUI / "amostra_confiabilidade_recorte.csv").open(encoding="utf-8"))]

    comuns = [p for p in amostra if p in um and p in dois]
    comuns = [p for p in comuns if recorte.manter(um[p]["caso"], um[p]["unit_id"])]
    indet = [p for p in comuns if "indeterminado" in (um[p]["nivel_do_par"], dois[p]["nivel_do_par"])]
    base = [p for p in comuns if p not in indet]

    print(f"amostra sorteada: {len(amostra)}   presentes nas duas codificacoes: {len(comuns)}")
    print(f"pares com indeterminado em alguma leitura (excluidos): {len(indet)}")
    print(f"base do calculo: {len(base)}\n")

    print("=== NIVEL DO PAR ===")
    bloco("todos", base, um, dois, "nivel_do_par", NIVEIS)
    for caso in ("FUST", "BEAD"):
        sel = [p for p in base if um[p]["caso"] == caso]
        if sel:
            bloco(caso, sel, um, dois, "nivel_do_par", NIVEIS)
    print()

    print("=== PERTINENCIA ===")
    pert = [p for p in comuns if um[p]["pertinencia"] in ("sim", "nao") and dois[p]["pertinencia"] in ("sim", "nao")]
    bloco("todos", pert, um, dois, "pertinencia", ["nao", "sim"])
    print()

    print("faixas de OVADEK; SCHROEDER; ZGLINSKI (2024) para o alfa:")
    print("  >= 0,80 confiavel   0,667 a 0,80 conclusao tentativa   < 0,667 descartar")
    print("essas faixas sao do alfa; para o kappa vale Landis e Koch (1977).")


if __name__ == "__main__":
    main()
