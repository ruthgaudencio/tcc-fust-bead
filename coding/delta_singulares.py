#!/usr/bin/env python3
"""
Mede o efeito da inclusão das 23 formas singulares no léxico US sobre os
pares do eixo discursivo já codificados.

Compara os lotes construídos antes da inclusão (coding/lotes_antes_singulares)
com os construídos depois (coding/lotes), par por par, e classifica cada par:

    novo              o par não existia antes
    janelas_mudaram   o par existia, mas o texto mostrado ao codificador mudou
    so_termos         o texto é idêntico; mudou só a lista de termos casados
    identico          nada mudou

O critério de recodificação é `novo` ou `janelas_mudaram`: são os casos em que
o material submetido ao julgamento é diferente do que foi julgado. Em
`so_termos` o trecho de evidência é literalmente o mesmo, então a codificação
anterior permanece válida.

    python3 delta_singulares.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ANTES = AQUI / "lotes_antes_singulares"
DEPOIS = AQUI / "lotes"
CODIFICADO = AQUI / "pares_eixo_discursivo.csv"
SAIDA = AQUI / "delta_singulares.csv"


def carregar_pares(diretorio: Path) -> dict[str, dict]:
    pares: dict[str, dict] = {}
    for arq in sorted(diretorio.glob("*_lote_*.json")):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        for par in dados.get("pares", []):
            janelas = tuple((j["inicio_corpo"], j["fim_corpo"])
                            for j in par.get("janelas", []))
            termos = frozenset(t.get("forma_encontrada", "")
                               for t in par.get("termos", []))
            pares[par["par_id"]] = {
                "caso": par["caso"],
                "subcategoria": par["subcategoria"],
                "unit_id": par["unit_id"],
                "janelas": janelas,
                "termos": termos,
                "n_ocorrencias": par.get("n_ocorrencias_no_par", 0),
            }
    return pares


def classificar(par_id: str, novo: dict, antes: dict[str, dict]) -> str:
    velho = antes.get(par_id)
    if velho is None:
        return "novo"
    if novo["janelas"] != velho["janelas"]:
        return "janelas_mudaram"
    if novo["termos"] != velho["termos"]:
        return "so_termos"
    return "identico"


def main() -> None:
    antes = carregar_pares(ANTES)
    depois = carregar_pares(DEPOIS)

    with CODIFICADO.open(encoding="utf-8") as f:
        codificados = {r["par_id"] for r in csv.DictReader(f)}

    linhas = []
    for par_id, novo in sorted(depois.items()):
        status = classificar(par_id, novo, antes)
        linhas.append({
            "par_id": par_id,
            "caso": novo["caso"],
            "unit_id": novo["unit_id"],
            "subcategoria": novo["subcategoria"],
            "status": status,
            "ja_codificado": "sim" if par_id in codificados else "nao",
            "recodificar": "sim" if status in ("novo", "janelas_mudaram") else "nao",
        })

    with SAIDA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    print(f"pares antes: {len(antes)}   pares depois: {len(depois)}")
    print(f"pares codificados em {CODIFICADO.name}: {len(codificados)}")
    print()
    for caso in ("FUST", "BEAD"):
        do_caso = [l for l in linhas if l["caso"] == caso]
        print(f"=== {caso} ({len(do_caso)} pares) ===")
        for status in ("novo", "janelas_mudaram", "so_termos", "identico"):
            n = sum(1 for l in do_caso if l["status"] == status)
            if n:
                ja = sum(1 for l in do_caso
                         if l["status"] == status and l["ja_codificado"] == "sim")
                print(f"  {status:17s} {n:5d}   (já codificados: {ja})")
        print()

    recod = [l for l in linhas if l["recodificar"] == "sim"]
    a_remover = [l for l in recod if l["ja_codificado"] == "sim"]
    print(f"A CODIFICAR: {len(recod)} pares")
    print(f"  dos quais já têm código antigo que precisa ser descartado: {len(a_remover)}")
    desaparecidos = sorted(set(antes) - set(depois))
    if desaparecidos:
        print(f"ATENÇÃO: {len(desaparecidos)} pares existiam antes e não existem depois")
        for p in desaparecidos[:10]:
            print(f"    {p}")
    print(f"\ngravado: {SAIDA}")


if __name__ == "__main__":
    main()
