#!/usr/bin/env python3
"""
Sorteia a amostra de pares para a segunda codificação independente.

Mede-se a estabilidade do instrumento recodificando, sem acesso à codificação
anterior, uma amostra de pares já codificados. Só entram no sorteio os pares
cujas janelas não mudaram desde a primeira codificação, para que as duas
leituras incidam sobre exatamente o mesmo material: a elegibilidade é lida de
`delta_singulares.csv`, nos estados `identico` e `so_termos`.

A semente é fixa e está registrada abaixo, de modo que o sorteio é
reproduzível por qualquer pessoa que tenha o repositório. O sorteio é
estratificado por caso, em partes iguais, e incide apenas sobre os pares
dentro do recorte declarado em recorte.py.

Saída:
    coding/lotes_confiabilidade/*.json   lotes no mesmo formato dos originais
    coding/amostra_confiabilidade.csv    registro dos pares sorteados

    python3 coding/amostra_confiabilidade.py
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent

import sys
sys.path.insert(0, str(AQUI.parent))
import recorte

SEMENTE = 20261031
# Estratificado por caso. O conjunto elegível é 65% brasileiro, de modo que um
# sorteio proporcional deixaria o coeficiente do caso norte-americano apoiado
# em poucas dezenas de pares. Partes iguais dão base suficiente aos dois.
ESTRATO = {"FUST": 60, "BEAD": 60}
TAMANHO = sum(ESTRATO.values())
POR_LOTE = 20
SAIDA_LOTES = AQUI / "lotes_confiabilidade_recorte"
SAIDA_REGISTRO = AQUI / "amostra_confiabilidade_recorte.csv"
ELEGIVEIS = {"identico", "so_termos"}


def main() -> None:
    with (AQUI / "delta_singulares.csv").open(encoding="utf-8") as f:
        delta = list(csv.DictReader(f))
    elegiveis = sorted(l["par_id"] for l in delta
                       if l["status"] in ELEGIVEIS and l["ja_codificado"] == "sim")

    pares_por_id = {}
    for arq in sorted((AQUI / "lotes").glob("*_lote_*.json")):
        for par in json.loads(arq.read_text(encoding="utf-8")).get("pares", []):
            pares_por_id[par["par_id"]] = par

    elegiveis = [p for p in elegiveis if p in pares_por_id]
    # Só entram pares dentro do recorte declarado em recorte.py: o sorteio
    # incide sobre a mesma base que a análise, e não sobre a coleta integral.
    elegiveis = [p for p in elegiveis
                 if recorte.manter(pares_por_id[p].get("caso", ""),
                                   pares_por_id[p].get("unit_id", ""))]
    rng = random.Random(SEMENTE)
    amostra = []
    for caso, quantos in sorted(ESTRATO.items()):
        do_caso = [p for p in elegiveis if pares_por_id[p].get("caso", "") == caso]
        amostra.extend(rng.sample(do_caso, min(quantos, len(do_caso))))
    amostra = sorted(amostra)

    # A rodada anterior fica onde está, como registro: esta grava em pasta
    # própria, de modo que as duas amostras permaneçam conferíveis lado a lado.
    SAIDA_LOTES.mkdir(exist_ok=True)

    lotes = [amostra[i:i + POR_LOTE] for i in range(0, len(amostra), POR_LOTE)]
    indice = []
    for n, ids in enumerate(lotes, 1):
        nome = f"confiabilidade_lote_{n:03d}.json"
        (SAIDA_LOTES / nome).write_text(json.dumps(
            {"lote": nome, "pares": [pares_por_id[i] for i in ids]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        indice.append({"arquivo": nome, "n_pares": len(ids)})

    with (SAIDA_LOTES / "_indice_lotes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["arquivo", "n_pares"])
        w.writeheader()
        w.writerows(indice)

    with SAIDA_REGISTRO.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["par_id", "caso", "subcategoria"])
        w.writeheader()
        for i in amostra:
            p = pares_por_id[i]
            w.writerow({"par_id": i, "caso": p["caso"], "subcategoria": p["subcategoria"]})

    print(f"elegíveis (janelas inalteradas, já codificados): {len(elegiveis)}")
    print(f"semente: {SEMENTE}   sorteados: {len(amostra)}   lotes: {len(lotes)}")
    print("por caso:", dict(Counter(pares_por_id[i]["caso"] for i in amostra)))
    ja = set()
    antigo = AQUI / "pares_confiabilidade.csv"
    if antigo.exists():
        with antigo.open(encoding="utf-8") as f:
            ja = {l["par_id"] for l in csv.DictReader(f)}
    pend = [i for i in amostra if i not in ja]
    print(f"já recodificados em rodada anterior: {len(amostra) - len(pend)}")
    print(f"pendentes de segunda leitura: {len(pend)}")
    print(f"gravado: {SAIDA_LOTES.name}/ e {SAIDA_REGISTRO.name}")


if __name__ == "__main__":
    main()
