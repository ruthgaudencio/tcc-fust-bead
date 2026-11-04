#!/usr/bin/env python3
"""
Mede a supressão de espaço entre palavras na camada de texto de um PDF.

Regra de decisão, aplicada a cada sequência de letras do documento:

    1. a sequência consta do léxico do português          -> palavra íntegra
    2. não consta, mas se parte em duas sequências que constam, cada uma com
       pelo menos `--min-parte` letras                     -> supressão de espaço
    3. não consta e não se parte                           -> não resolvida

O teste 1 precede o teste 2, e é ele que elimina o falso positivo evidente:
"entretanto" se parte em "entre" e "tanto", ambas palavras, mas "entretanto"
é ela própria palavra do léxico e por isso não chega ao teste de partição.

A exigência de pelo menos `--min-parte` letras de cada lado faz a medida
subcontar deliberadamente: supressões que envolvem palavra curta, como
"deFust", não são detectadas. O resultado é, portanto, um piso.

Antes da contagem, o script refaz a hifenização de fim de linha produzida pela
extração ("universali-\nzação"), que é defeito distinto e contaminaria o
resultado, e informa quantas junções fez.

O léxico é `fust/matriz/lexico_pt.txt`, derivado da lista de português do
pacote pyspellchecker e versionado junto com o código, de modo que a medição
independe de instalação e não muda com a atualização do pacote.

    python3 fust/medir_ocr.py corpus_fust/diarios_camara/DCD17SET1999.pdf
    python3 fust/medir_ocr.py corpus_fust/senado/MATE_TI_29602.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LEXICO = Path(__file__).resolve().parent / "matriz" / "lexico_pt.txt"
SUPLEMENTO = Path(__file__).resolve().parent / "matriz" / "lexico_suplemento_corpus.txt"

LETRAS = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
HIFEN_FIM_DE_LINHA = re.compile(r"([^\W\d_])-[ \t]*\n[ \t]*([^\W\d_])", re.UNICODE)


def _ler(caminho: Path) -> set[str]:
    return {unicodedata.normalize("NFC", l.strip().lower())
            for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()}


def carregar_lexico() -> tuple[set[str], int, int]:
    if not LEXICO.exists():
        sys.exit(f"léxico ausente: {LEXICO}")
    geral = _ler(LEXICO)
    suplemento = _ler(SUPLEMENTO) if SUPLEMENTO.exists() else set()
    return geral | suplemento, len(geral), len(suplemento)


def extrair(pdf: Path) -> tuple[str, int]:
    import pypdf
    leitor = pypdf.PdfReader(str(pdf))
    texto = "\n".join((p.extract_text() or "") for p in leitor.pages)
    texto, n_juncoes = HIFEN_FIM_DE_LINHA.subn(r"\1\2", texto)
    return texto, n_juncoes, len(leitor.pages)


def partir(token: str, lex: set[str], min_parte: int) -> tuple[str, str] | None:
    for i in range(min_parte, len(token) - min_parte + 1):
        a, b = token[:i], token[i:]
        if a in lex and b in lex:
            return a, b
    return None


def medir(texto: str, lex: set[str], min_parte: int,
          ignorar_capitalizadas: bool = True) -> dict:
    integras = nao_resolvidas = capitalizadas = 0
    supressoes: Counter[tuple[str, str]] = Counter()
    total = 0
    for m in LETRAS.finditer(texto):
        bruto = m.group(0)
        token = unicodedata.normalize("NFC", bruto.lower())
        total += 1
        if token in lex:
            integras += 1
            continue
        if ignorar_capitalizadas and bruto[0].isupper() and bruto[1:].islower():
            # forma com inicial maiúscula e resto minúsculo: nome próprio ou
            # início de período. Excluída do teste de partição, o que faz a
            # medida subcontar supressões iniciadas por maiúscula.
            capitalizadas += 1
            continue
        if len(token) >= 2 * min_parte:
            p = partir(token, lex, min_parte)
            if p:
                supressoes[p] += 1
                continue
        nao_resolvidas += 1
    return {"tokens": total, "integras": integras,
            "supressoes": sum(supressoes.values()),
            "tipos_de_supressao": len(supressoes),
            "capitalizadas": capitalizadas,
            "nao_resolvidas": nao_resolvidas, "detalhe": supressoes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="+")
    ap.add_argument("--min-parte", type=int, default=4)
    ap.add_argument("--exemplos", type=int, default=12)
    ap.add_argument("--contar-capitalizadas", action="store_true",
                    help="desliga a trava de nome próprio")
    args = ap.parse_args()

    lex, n_geral, n_sup = carregar_lexico()
    print(f"léxico: {n_geral:,} formas da lista do português".replace(",", ".")
          + f" + {n_sup:,} do corpus nativo digital".replace(",", ".")
          + f" = {len(lex):,} distintas".replace(",", "."))
    print(f"regra: mínimo de {args.min_parte} letras de cada lado da partição; "
          + ("nomes próprios contados" if args.contar_capitalizadas
             else "formas com inicial maiúscula excluídas") + "\n")

    for caminho in args.pdf:
        pdf = Path(caminho)
        if not pdf.is_file():
            print(f"ausente: {pdf}\n")
            continue
        texto, juncoes, paginas = extrair(pdf)
        r = medir(texto, lex, args.min_parte, not args.contar_capitalizadas)
        por_mil = r["supressoes"] / r["tokens"] * 1000 if r["tokens"] else 0
        print(f"=== {pdf.name} ===")
        print(f"  {paginas} páginas, {len(texto):,} caracteres extraídos".replace(",", "."))
        print(f"  hifenizações de fim de linha refeitas: {juncoes:,}".replace(",", "."))
        print(f"  sequências de letras analisadas: {r['tokens']:,}".replace(",", "."))
        print(f"    palavras íntegras:        {r['integras']:,}".replace(",", "."))
        print(f"    SUPRESSÕES DE ESPAÇO:     {r['supressoes']:,}"
              f"   ({por_mil:.2f} por mil sequências, {r['tipos_de_supressao']:,} formas distintas)"
              .replace(",", "."))
        print(f"    inicial maiúscula:        {r['capitalizadas']:,}".replace(",", "."))
        print(f"    não resolvidas:           {r['nao_resolvidas']:,}"
              f"   ({r['nao_resolvidas'] / r['tokens'] * 100:.1f}%)".replace(",", "."))
        if r["detalhe"]:
            print(f"  exemplos mais frequentes:")
            for (a, b), n in r["detalhe"].most_common(args.exemplos):
                print(f"    {a}+{b}  ({a}{b}), {n}x")
        print()


if __name__ == "__main__":
    main()
