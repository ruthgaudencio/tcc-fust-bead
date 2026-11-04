#!/usr/bin/env python3
"""
Compara a segunda codificação independente com a primeira, sobre a mesma
amostra de pares, e reporta a concordância.

A amostra foi sorteada por `amostra_confiabilidade.py` entre os pares cujas
janelas não mudaram desde a primeira codificação, de modo que as duas leituras
incidem sobre exatamente o mesmo material. A segunda codificação correu em
sessão sem acesso à primeira.

Reporta concordância bruta e corrigida pelo acaso, no nível do par e na
pertinência. O kappa ponderado trata a escala como ordinal, de sorte que
discordar entre ausente e estrutural pesa mais do que discordar entre níveis
vizinhos. Os pares em que qualquer das leituras registrou `indeterminado` são
reportados à parte, e o cálculo principal os exclui, por não constituírem
atribuição de nível.

    python3 coding/medir_confiabilidade.py
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


def kappa(a: list[str], b: list[str], cats: list[str], ponderado: bool = False) -> tuple[float, float, float]:
    n = len(a)
    ordem = {c: i for i, c in enumerate(cats)}
    maxd = len(cats) - 1

    def peso(x, y):
        return 1 - abs(ordem[x] - ordem[y]) / maxd if ponderado else (1.0 if x == y else 0.0)

    po = sum(peso(x, y) for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[x] / n) * (cb[y] / n) * peso(x, y) for x in cats for y in cats)
    return po, pe, (po - pe) / (1 - pe) if pe < 1 else 1.0


def bloco(rotulo: str, pares: list[str], um: dict, dois: dict, campo: str, cats: list[str]) -> None:
    a = [um[p][campo] for p in pares]
    b = [dois[p][campo] for p in pares]
    po, pe, k = kappa(a, b, cats)
    print(f"  {rotulo} ({len(pares)} pares)")
    print(f"     concordância bruta: {po * 100:.1f}%   esperada por acaso: {pe * 100:.1f}%   kappa: {k:.3f}")
    if len(cats) > 2:
        _, _, kw = kappa(a, b, cats, ponderado=True)
        print(f"     kappa ponderado (ordinal): {kw:.3f}")


def main() -> None:
    um = ler(AQUI / "pares_eixo_discursivo.csv")
    dois = ler(AQUI / "pares_confiabilidade_recorte.csv")
    amostra = [l["par_id"] for l in csv.DictReader((AQUI / "amostra_confiabilidade_recorte.csv").open(encoding="utf-8"))]

    comuns = [p for p in amostra if p in um and p in dois]
    comuns = [p for p in comuns if recorte.manter(um[p]["caso"], um[p]["unit_id"])]
    print(f"amostra sorteada: {len(amostra)}   presentes nas duas codificações: {len(comuns)}\n")

    indet = [p for p in comuns if "indeterminado" in (um[p]["nivel_do_par"], dois[p]["nivel_do_par"])]
    base = [p for p in comuns if p not in indet]
    print(f"pares com indeterminado em alguma das leituras: {len(indet)}")
    for p in indet:
        print(f"     {p}: 1a={um[p]['nivel_do_par']}  2a={dois[p]['nivel_do_par']}")
    print()

    print("=== NÍVEL DO PAR ===")
    bloco("todos", base, um, dois, "nivel_do_par", NIVEIS)
    for caso in ("FUST", "BEAD"):
        sel = [p for p in base if um[p]["caso"] == caso]
        if sel:
            bloco(caso, sel, um, dois, "nivel_do_par", NIVEIS)
    print()

    print("=== PERTINÊNCIA ===")
    pert = [p for p in comuns if um[p]["pertinencia"] in ("sim", "nao") and dois[p]["pertinencia"] in ("sim", "nao")]
    bloco("todos", pert, um, dois, "pertinencia", ["nao", "sim"])
    print()

    print("=== MATRIZ (linha = 1a codificação, coluna = 2a) ===")
    m = Counter((um[p]["nivel_do_par"], dois[p]["nivel_do_par"]) for p in base)
    print(f"{'':<17}" + "".join(f"{c:>17}" for c in NIVEIS))
    for x in NIVEIS:
        print(f"{x:<17}" + "".join(f"{m[(x, y)]:>17}" for y in NIVEIS))
    ordem = {c: i for i, c in enumerate(NIVEIS)}
    desceu = sum(n for (x, y), n in m.items() if ordem[y] < ordem[x])
    subiu = sum(n for (x, y), n in m.items() if ordem[y] > ordem[x])
    print(f"\n  desceu de nível na 2a leitura: {desceu}    subiu: {subiu}")
    ent = sum(n for (x, y), n in m.items() if x != "falso_positivo" and y == "falso_positivo")
    sai = sum(n for (x, y), n in m.items() if x == "falso_positivo" and y != "falso_positivo")
    print(f"  entraram em falso positivo: {ent}    saíram: {sai}")
    print("\n  referência para o kappa: Landis e Koch (1977) — 0,61 a 0,80")
    print("  substancial; 0,81 a 1,00 quase perfeita. As faixas de 0,667 e 0,80")
    print("  pertencem ao alfa de Krippendorff, não ao kappa; para o alfa sobre")
    print("  esta mesma amostra, ver coding/medir_alfa_krippendorff.py.")


if __name__ == "__main__":
    main()
