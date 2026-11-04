#!/usr/bin/env python3
"""Acrescenta decisões (lista de dicts, um por par) a coding/pares_eixo_discursivo.csv,
criando o cabeçalho se o arquivo não existir. Lê as decisões de um JSON passado
como argumento (lista de objetos com as colunas do item 6 do instrumento)."""
import csv
import json
import sys
from pathlib import Path

COLS = ["par_id", "caso", "unit_id", "subcategoria", "codigo", "pertinencia",
        "razao_declarada", "dado_ou_diagnostico", "nivel_do_par",
        "trecho_evidencia", "justificativa", "notas"]

caminho_csv = Path("coding/pares_eixo_discursivo.csv")
decisoes = json.load(open(sys.argv[1], encoding="utf-8"))

existe = caminho_csv.exists()
with caminho_csv.open("a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    if not existe:
        w.writeheader()
    for d in decisoes:
        w.writerow({c: d.get(c, "") for c in COLS})

from collections import Counter
c = Counter(d.get("nivel_do_par", "") for d in decisoes)
print(f"gravadas {len(decisoes)} linhas. estrutural={c.get('estrutural',0)} "
      f"superficial={c.get('superficial',0)} falso_positivo={c.get('falso_positivo',0)} "
      f"indeterminado={c.get('indeterminado',0)}")
