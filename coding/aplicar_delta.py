#!/usr/bin/env python3
"""
Descarta de `pares_eixo_discursivo.csv` os códigos dos pares cujo material
mudou com a inclusão das formas singulares no léxico US, para que a rodada
seguinte de codificação os refaça.

Lê `delta_singulares.csv` (produzido por delta_singulares.py) e remove as
linhas cujo par está marcado recodificar=sim e ja_codificado=sim. Grava um
backup datado antes de escrever.

    python3 aplicar_delta.py
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DELTA = AQUI / "delta_singulares.csv"
CODIFICADO = AQUI / "pares_eixo_discursivo.csv"


def main() -> None:
    with DELTA.open(encoding="utf-8") as f:
        delta = list(csv.DictReader(f))

    descartar = {l["par_id"] for l in delta
                 if l["recodificar"] == "sim" and l["ja_codificado"] == "sim"}

    with CODIFICADO.open(encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        colunas = leitor.fieldnames
        linhas = list(leitor)

    mantidas = [l for l in linhas if l["par_id"] not in descartar]
    removidas = len(linhas) - len(mantidas)

    if removidas != len(descartar):
        raise SystemExit(f"esperava remover {len(descartar)} linhas, removi {removidas}")

    marca = datetime.now().strftime("%Y%m%d_%H%M")
    backup = AQUI / f"pares_eixo_discursivo_backup_{marca}.csv"
    shutil.copy2(CODIFICADO, backup)

    with CODIFICADO.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        w.writerows(mantidas)

    a_codificar = [l for l in delta if l["recodificar"] == "sim"]
    sem_codigo = {l["par_id"] for l in delta} - {l["par_id"] for l in mantidas}

    print(f"backup: {backup.name}")
    print(f"linhas antes: {len(linhas)}   removidas: {removidas}   agora: {len(mantidas)}")
    print()
    print(f"pares a codificar na próxima rodada: {len(sem_codigo)}")
    print(f"  novos:            {sum(1 for l in a_codificar if l['status'] == 'novo')}")
    print(f"  recodificados:    {sum(1 for l in a_codificar if l['status'] == 'janelas_mudaram')}")
    print(f"  faltaram antes:   {len(sem_codigo) - len(a_codificar)}")


if __name__ == "__main__":
    main()
