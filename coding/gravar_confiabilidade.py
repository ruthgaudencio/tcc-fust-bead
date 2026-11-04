#!/usr/bin/env python3
"""Acrescenta decisões (lista de dicts, um por par) a coding/pares_confiabilidade.csv,
criando o cabeçalho se o arquivo não existir. Lê as decisões de um JSON passado
como argumento (lista de objetos com as colunas do item 6 do instrumento).
Uso: python3 gravar_confiabilidade.py <decisoes.json> <nome_do_lote>"""
import csv
import json
import sys
from pathlib import Path
from collections import Counter

COLS = ["par_id", "caso", "unit_id", "subcategoria", "codigo", "pertinencia",
        "razao_declarada", "dado_ou_diagnostico", "nivel_do_par",
        "trecho_evidencia", "justificativa", "notas"]

caminho_csv = Path("coding/pares_confiabilidade.csv")
decisoes = json.load(open(sys.argv[1], encoding="utf-8"))
nome_lote = sys.argv[2] if len(sys.argv) > 2 else "?"

existe = caminho_csv.exists()
with caminho_csv.open("a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    if not existe:
        w.writeheader()
    for d in decisoes:
        w.writerow({c: d.get(c, "") for c in COLS})

c = Counter(d.get("nivel_do_par", "") for d in decisoes)
print(f"{nome_lote}: {len(decisoes)} pares codificados. "
      f"estrutural={c.get('estrutural',0)} superficial={c.get('superficial',0)} "
      f"falso_positivo={c.get('falso_positivo',0)} indeterminado={c.get('indeterminado',0)}")
