#!/usr/bin/env python3
"""Mostra os pares de um lote de forma compacta, para leitura antes de codificar."""
import json
import sys
from pathlib import Path

caminho = Path("coding/lotes") / sys.argv[1]
d = json.load(caminho.open(encoding="utf-8"))
print(f"=== {sys.argv[1]} | caso={d['caso']} | {len(d['pares'])} pares ===\n")
for p in d["pares"]:
    print(f"--- par_id={p['par_id']} | codigo={p['codigo']} | lingua={p['lingua']} | "
          f"orador={p['orador']} | n_ocorr={p['n_ocorrencias_no_par']} | "
          f"janelas_mostradas={p['n_janelas_mostradas']} | janelas_omitidas={p['n_janelas_omitidas']}")
    termos = "; ".join(f"{t['termo_da_lista']}->{t['forma_encontrada']}({t['passada']})" for t in p["termos"])
    print(f"    termos: {termos}")
    for i, j in enumerate(p["janelas"], 1):
        print(f"    janela {i} [{j['inicio_corpo']}-{j['fim_corpo']}]: {j['trecho']}")
    print()
