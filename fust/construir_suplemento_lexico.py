#!/usr/bin/env python3
"""
Constrói o suplemento de léxico usado pela medição de OCR.

A lista geral do português desconhece o vocabulário parlamentar e os nomes
próprios dos parlamentares, e isso produz falso positivo na detecção de
supressão de espaço: "relatora" e "Batochio" não constam da lista, partem-se em
pares de palavras que constam, e seriam contadas como espaço faltando.

O suplemento é extraído das 364 unidades do corpus do FUST provenientes da API
de dados abertos do Senado, que são texto nativo digital, sem camada de OCR, e
portanto não introduzem no léxico os defeitos que a medição procura. Exige-se
ocorrência mínima para que erro isolado de digitação não entre.

    python3 fust/construir_suplemento_lexico.py
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDICE = RAIZ / "corpus_fust" / "corpus_index.csv"
SAIDA = RAIZ / "fust" / "matriz" / "lexico_suplemento_corpus.txt"
FONTE_LIMPA = "legis.senado.leg.br/dadosabertos"
MIN_OCORRENCIAS = 3
MIN_LETRAS = 4

LETRAS = re.compile(r"[^\W\d_]{%d,}" % MIN_LETRAS, re.UNICODE)
MARCA = "# source:"


def corpo(texto: str) -> str:
    i = texto.find(MARCA)
    if i == -1:
        return texto
    fim = texto.find("\n", i)
    return texto[fim + 1:] if fim != -1 else texto


def main() -> None:
    with INDICE.open(encoding="utf-8") as f:
        registros = list(csv.DictReader(f))

    limpos = [r for r in registros if FONTE_LIMPA in (r.get("text_source") or "")]
    contagem: Counter[str] = Counter()
    lidos = 0
    for r in limpos:
        nome = (r.get("corpus_file") or "").strip()
        if not nome:
            continue
        caminho = RAIZ / "corpus_fust" / nome
        if not caminho.is_file():
            continue
        lidos += 1
        texto = corpo(caminho.read_text(encoding="utf-8", errors="replace"))
        for m in LETRAS.finditer(texto):
            contagem[unicodedata.normalize("NFC", m.group(0).lower())] += 1

    palavras = sorted(p for p, n in contagem.items() if n >= MIN_OCORRENCIAS)
    SAIDA.write_text("\n".join(palavras) + "\n", encoding="utf-8")

    print(f"unidades nativas digitais no índice: {len(limpos)}, lidas: {lidos}")
    print(f"formas distintas encontradas: {len(contagem):,}".replace(",", "."))
    print(f"formas com pelo menos {MIN_OCORRENCIAS} ocorrências: {len(palavras):,}".replace(",", "."))
    print(f"gravado: {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
