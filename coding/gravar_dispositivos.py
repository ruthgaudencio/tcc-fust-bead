#!/usr/bin/env python3
"""Acrescenta decisões (lista de dicts, um por dispositivo) a
coding/dispositivos_eixo_normativo.csv, criando o cabeçalho se o arquivo não
existir. Lê as decisões de um JSON passado como argumento (lista de objetos
com as colunas do item 5 do instrumento normativo)."""
import csv
import json
import sys
from pathlib import Path

COLS = ["disp_id", "caso", "diploma", "codigo", "subcategoria", "pertinencia",
        "mecanismo_tipo", "vinculante", "nivel_do_dispositivo",
        "trecho_evidencia", "justificativa", "notas"]

caminho_csv = Path("coding/dispositivos_eixo_normativo.csv")
decisoes = json.load(open(sys.argv[1], encoding="utf-8"))

existe = caminho_csv.exists()
with caminho_csv.open("a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    if not existe:
        w.writeheader()
    for d in decisoes:
        w.writerow({c: d.get(c, "") for c in COLS})

from collections import Counter
c = Counter(d.get("nivel_do_dispositivo", "") for d in decisoes)
print(f"gravados {len(decisoes)} dispositivos. estrutural={c.get('estrutural',0)} "
      f"superficial={c.get('superficial',0)} falso_positivo={c.get('falso_positivo',0)} "
      f"indeterminado={c.get('indeterminado',0)}")
