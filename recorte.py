#!/usr/bin/env python3
"""
Declara o recorte temporal dos dois corpora e é o único lugar onde ele é
fixado. Todos os scripts de análise importam daqui, de modo que o corte seja
conferível em um ponto só e não fique espalhado por condição repetida.

A regra. A análise de cada caso termina no texto aprovado. No caso brasileiro
isso é consequência do próprio objeto: o corpus acompanha a tramitação do
Projeto de Lei nº 3.808, de 1997, até a Lei nº 9.998, de 2000, e as alterações
posteriores, entre elas a Lei nº 14.109, de 2020, ficam fora da análise, ainda
que mencionadas na revisão. No caso norte-americano o corte precisa ser
declarado, porque a coleta foi mais larga: as audiências foram recolhidas para
outra pesquisa e cobrem também a execução e a fiscalização do programa.

Por isso o corpus norte-americano é delimitado na promulgação da Infrastructure
Investment and Jobs Act, em 15 de novembro de 2021. O que vem depois é
acompanhamento de execução, e comparar fiscalização de um lado com deliberação
legislativa do outro não responde à pergunta da pesquisa, que é sobre o que cada
processo legislativo produziu.

As unidades excluídas continuam no corpus em disco e permanecem codificadas. O
recorte opera na leitura, não no dado, de sorte que a decisão é reversível e o
material anterior continua disponível para conferência.

    python3 recorte.py        # imprime o efeito do recorte sobre a base
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Promulgação da IIJA, Lei Pública 117-58. Unidades desta data em diante ficam
# fora da análise.
MARCO_IIJA = dt.date(2021, 11, 15)

_INDICES = {"BEAD": BASE / "corpus_bead" / "corpus_index.csv"}
_cache: dict[str, set[str]] = {}


def _data_de(registro: dict) -> dt.date | None:
    bruto = (registro.get("data") or registro.get("date") or "").strip()[:10]
    try:
        return dt.date.fromisoformat(bruto)
    except ValueError:
        return None


def excluidas(caso: str) -> set[str]:
    """Identificadores de unidade que o recorte deixa de fora, para um caso."""
    caso = caso.strip().upper()
    if caso in _cache:
        return _cache[caso]
    fora: set[str] = set()
    caminho = _INDICES.get(caso)
    if caminho and caminho.exists():
        with caminho.open(encoding="utf-8") as f:
            for reg in csv.DictReader(f):
                d = _data_de(reg)
                if d and d >= MARCO_IIJA:
                    fora.add(reg["id"])
    _cache[caso] = fora
    return fora


def manter(caso: str, unit_id: str) -> bool:
    """Verdadeiro se a unidade está dentro do recorte."""
    return unit_id not in excluidas(caso)


def filtrar_pares(pares: list[dict], campo_caso: str = "caso",
                  campo_unidade: str = "unit_id") -> list[dict]:
    """Remove de uma lista de pares codificados os que caem fora do recorte."""
    return [p for p in pares
            if manter(p.get(campo_caso, ""), p.get(campo_unidade, ""))]


def main() -> None:
    fora = excluidas("BEAD")
    print(f"marco do recorte norte-americano: {MARCO_IIJA.isoformat()}")
    print(f"unidades do BEAD fora do recorte: {len(fora)}")
    p = BASE / "coding" / "pares_eixo_discursivo.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            pares = list(csv.DictReader(f))
        dentro = filtrar_pares(pares)
        print(f"pares na base: {len(pares)}  ->  dentro do recorte: {len(dentro)}")
        for caso in ("FUST", "BEAD"):
            a = sum(1 for x in pares if x["caso"] == caso)
            b = sum(1 for x in dentro if x["caso"] == caso)
            print(f"  {caso}: {a} -> {b}")


if __name__ == "__main__":
    main()
