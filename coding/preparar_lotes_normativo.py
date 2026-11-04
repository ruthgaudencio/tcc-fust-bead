"""
Monta os lotes do eixo normativo a partir de coding/normativo_mencoes.csv.

A unidade codificada é o DISPOSITIVO: o trecho da lei em que uma subcategoria é
nomeada. Para cada um, decide-se se ele apenas nomeia o grupo ou se lhe atribui
mecanismo vinculante, e de que tipo.

Os lotes carregam a procedência (diploma) de cada dispositivo, e a agregação
filtra por escopo depois. A codificação, portanto, não depende da decisão sobre
o que conta como texto aprovado: ela vale para qualquer escopo escolhido.

    python3 coding/preparar_lotes_normativo.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
COD = BASE / "coding"
SAIDA = COD / "lotes_normativo"
JANELA = 700
FIM_FRASE = re.compile(r"(?<=[.;:])\s")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

TEXTOS = {
    "Lei 9.998/2000": BASE / "corpus_fust" / "lei9998_texto_original.txt",
    "Lei 9.472/1997, arts. 79-81": BASE / "corpus_fust" / "lei9472_arts79-81.txt",
    "IIJA SEC. 60102": BASE / "corpus_bead" / "iija_sec60102.txt",
    "IIJA Digital Equity Act": BASE / "corpus_bead" / "iija_digital_equity_act.txt",
    "IIJA Division F": BASE / "corpus_bead" / "iija_division_f.txt",
}


def corpo_de_lei(t: str) -> str:
    ls = t.splitlines(keepends=True)
    i = 0
    while i < len(ls) and (ls[i].lstrip().startswith("#") or not ls[i].strip()):
        i += 1
    return "".join(ls[i:])


def janela(corpo: str, ini: int, fim: int) -> str:
    a, b = max(0, ini - JANELA), min(len(corpo), fim + JANELA)
    if a > 0:
        m = list(FIM_FRASE.finditer(corpo, a, ini))
        if m:
            a = m[0].end()
    if b < len(corpo):
        m = FIM_FRASE.search(corpo, fim, b + 300)
        if m:
            b = m.end()
    return " ".join(corpo[a:b].split())


def main():
    mencoes = list(csv.DictReader((COD / "normativo_mencoes.csv").open(encoding="utf-8")))
    cache = {}
    for rot, p in TEXTOS.items():
        if p.exists():
            cache[rot] = corpo_de_lei(p.read_text(encoding="utf-8", errors="replace"))

    # funde menções próximas no mesmo diploma: um dispositivo pode disparar
    # vários termos, e cada dispositivo deve ser julgado uma vez só
    por_dip = defaultdict(list)
    for m in mencoes:
        por_dip[(m["caso"], m["diploma"], m["codigo"])].append(m)

    itens = []
    for (caso, dip, cod), ms in sorted(por_dip.items()):
        corpo = cache.get(dip, "")
        ms.sort(key=lambda x: int(x["offset"]))
        grupos, atual = [], [ms[0]]
        for x in ms[1:]:
            if int(x["offset"]) - int(atual[-1]["offset"]) <= 2 * JANELA:
                atual.append(x)
            else:
                grupos.append(atual); atual = [x]
        grupos.append(atual)
        for i, g in enumerate(grupos, 1):
            ini, fim = int(g[0]["offset"]), int(g[-1]["offset"]) + len(g[-1]["forma_encontrada"])
            itens.append({
                "disp_id": f"{caso}::{cod}::{dip}::{i}",
                "caso": caso, "diploma": dip, "codigo": cod,
                "subcategoria": g[0]["subcategoria"],
                "termos_encontrados": sorted({x["forma_encontrada"] for x in g}),
                "n_mencoes": len(g),
                "trecho": janela(corpo, ini, fim) if corpo else g[0]["contexto"],
            })

    SAIDA.mkdir(parents=True, exist_ok=True)
    tam = 12
    idx = []
    for i in range(0, len(itens), tam):
        lote = itens[i:i + tam]
        n = i // tam + 1
        nome = f"normativo_lote_{n:03d}.json"
        (SAIDA / nome).write_text(json.dumps({"lote": n, "dispositivos": lote},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
        idx.append({"arquivo": nome, "lote": n, "n_dispositivos": len(lote)})
    with (SAIDA / "_indice_lotes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arquivo", "lote", "n_dispositivos"])
        w.writeheader(); w.writerows(idx)

    print(f"{len(mencoes)} menções -> {len(itens)} dispositivos -> {len(idx)} lotes")
    for caso in ("FUST", "BEAD"):
        n = sum(1 for x in itens if x["caso"] == caso)
        print(f"   {caso}: {n} dispositivos")


if __name__ == "__main__":
    main()
