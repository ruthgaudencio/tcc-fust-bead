#!/usr/bin/env python3
"""
Análise de sensibilidade do sorteio da amostra de confiabilidade.

A pergunta que este programa responde: a concentração de pares superficiais
observada na amostra do caso norte-americano é propriedade do material ou do
sorteio? Coeficientes corrigidos pelo acaso caem quando a distribuição das
categorias é concentrada, de sorte que a resposta muda a leitura do kappa e do
alfa reportados em 4.2.

O método compara a amostra efetivamente sorteada com a base de onde ela saiu, e
situa a concordância esperada por acaso do sorteio na distribuição de sorteios
possíveis sobre a mesma base, por simulação.

A base de sorteio é reconstruída pelo mesmo critério de amostra_confiabilidade.py:
pares já codificados cujas janelas não mudaram entre as rodadas, dentro do
recorte declarado em recorte.py.

    python3 coding/sensibilidade_amostra.py
    python3 coding/sensibilidade_amostra.py --caso FUST --sorteios 50000
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import recorte  # noqa: E402

COD = BASE / "coding"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

ELEGIVEIS = {"identico", "so_termos"}
CATEGORIAS = ("falso_positivo", "superficial", "estrutural")
SEMENTE_SIMULACAO = 12345


def base_de_sorteio(caso: str) -> list[str]:
    delta = list(csv.DictReader((COD / "delta_singulares.csv").open(encoding="utf-8")))
    elegiveis = sorted(l["par_id"] for l in delta
                       if l["status"] in ELEGIVEIS and l["ja_codificado"] == "sim")
    por_id = {}
    for arq in sorted(glob.glob(str(COD / "lotes" / "*_lote_*.json"))):
        for par in json.loads(Path(arq).read_text(encoding="utf-8")).get("pares", []):
            por_id[par["par_id"]] = par
    return [p for p in elegiveis
            if p in por_id
            and por_id[p].get("caso", "") == caso
            and recorte.manter(por_id[p].get("caso", ""), por_id[p].get("unit_id", ""))]


def niveis_primeira_leitura() -> dict[str, dict]:
    pares = recorte.filtrar_pares(
        list(csv.DictReader((COD / "pares_eixo_discursivo.csv").open(encoding="utf-8"))))
    return {p["par_id"]: p for p in pares}


def acaso(contagem: Counter, n: int) -> float:
    """Concordância esperada por acaso sobre as marginais de uma leitura."""
    return sum((contagem[k] / n) ** 2 for k in CATEGORIAS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", default="BEAD")
    ap.add_argument("--sorteios", type=int, default=200_000)
    ap.add_argument("--tamanho", type=int, default=60)
    ap.add_argument("--bruta", type=float, default=0.811,
                    help="concordância bruta observada, para o kappa implicado")
    a = ap.parse_args()

    pares = niveis_primeira_leitura()
    base = [p for p in base_de_sorteio(a.caso) if p in pares
            and pares[p]["nivel_do_par"] in CATEGORIAS]
    pool = [pares[p]["nivel_do_par"] for p in base]

    sorteados = {r["par_id"] for r in
                 csv.DictReader((COD / "amostra_confiabilidade_recorte.csv").open(encoding="utf-8"))}
    amostra = [pares[p]["nivel_do_par"] for p in sorteados
               if p in pares and pares[p]["caso"] == a.caso
               and pares[p]["nivel_do_par"] in CATEGORIAS]

    cp, ca = Counter(pool), Counter(amostra)
    nP, nA = len(pool), len(amostra)
    print(f"=== {a.caso}: amostra sorteada contra a base de sorteio ===")
    print(f"{'categoria':<17}{'amostra':>18}{'base':>20}")
    for k in CATEGORIAS:
        print(f"{k:<17}{ca[k]:>7} ({ca[k]/nA*100:>5.1f}%){cp[k]:>10} ({cp[k]/nP*100:>5.1f}%)")
    print(f"{'total':<17}{nA:>7}          {nP:>10}")

    obs = acaso(ca, nA)
    rng = random.Random(SEMENTE_SIMULACAO)
    simulados = sorted(acaso(Counter(rng.sample(pool, a.tamanho)), a.tamanho)
                       for _ in range(a.sorteios))
    acima = sum(1 for p in simulados if p >= obs)

    def pct(q):
        return simulados[min(int(q * len(simulados)), len(simulados) - 1)]

    def kappa(pe):
        return (a.bruta - pe) / (1 - pe)

    print()
    print(f"=== concordância esperada por acaso, {a.sorteios} sorteios de {a.tamanho} ===")
    for rotulo, q in (("percentil 5", 0.05), ("mediana", 0.50), ("percentil 95", 0.95)):
        print(f"  {rotulo:<14}{pct(q)*100:>6.1f}%   kappa implicado a {a.bruta:.3f}: {kappa(pct(q)):.3f}")
    print(f"  {'observado':<14}{obs*100:>6.1f}%   kappa implicado a {a.bruta:.3f}: {kappa(obs):.3f}")
    print()
    print(f"  sorteios ao menos tão concentrados quanto o observado: "
          f"{acima} em {a.sorteios} ({acima/a.sorteios:.4f})")
    print()
    print("  Os coeficientes reportados em 4.2 são os medidos sobre a amostra efetivamente")
    print("  sorteada. A simulação acima é análise de sensibilidade, e não os substitui.")


if __name__ == "__main__":
    main()
