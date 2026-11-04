#!/usr/bin/env python3
"""
Teste corrigido da armadilha 23, passo 2, para DCD (Diário da Câmara) --
ver nota de correção registrada em 2026-10-07.

A intercalação nos DCD08DEZ1999/DCD0019991202... NÃO é sangria de coluna
linha a linha (densidade de colagem não serve de proxy aqui, porque as
linhas em si saem inteiras). É ORDEM DE BLOCO INVERTIDA: na mesma página,
um bloco de fala pode aparecer antes do cabeçalho de seção que o precede,
e uma fala pode cortar no meio da palavra sem a continuação aparecer logo
depois -- ela foi deslocada pra outro ponto do fluxo de extração.

Teste: para cada marcador de orador (`O SR. NOME (...)` / `A SRª NOME
(...)`), pega o texto até o PRÓXIMO marcador e verifica se termina em
palavra partida por hífen sem pontuação de fechamento -- sinal de que a
continuação foi parar em outro lugar do texto extraído.

    python classificar_dcd.py corpus_fust/camara/emendas/_compartilhados/DCD08DEZ1999.pdf
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RE_MARCADOR = re.compile(
    r"\b[OoAa]\s+SRA?[Aa\xaa]?\.?\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^\n(]{0,60}?\([^)]*\)",
    re.UNICODE,
)
RE_CORTE = re.compile(r"[a-zà-ú]-\s*$")


def avaliar(pdf_path: Path) -> dict:
    from pypdf import PdfReader
    r = PdfReader(str(pdf_path), strict=False)
    texto = "\n".join((p.extract_text() or "") for p in r.pages)

    marcas = list(RE_MARCADOR.finditer(texto))
    cortes = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        trecho = texto[m.end():fim].rstrip()
        ultimas = trecho[-60:]
        if RE_CORTE.search(ultimas):
            cortes.append({"marcador": m.group(0)[:60], "termina_em": ultimas})

    return {
        "arquivo": pdf_path.name,
        "n_paginas": len(r.pages),
        "n_marcadores": len(marcas),
        "n_falas_cortadas": len(cortes),
        "exemplos_cortes": cortes[:5],
        "veredito": "ocr_obrigatorio" if cortes else "sem_corte_detectado_nesta_amostra",
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("uso: classificar_dcd.py <caminho.pdf> [<caminho2.pdf> ...]")
    for arg in sys.argv[1:]:
        r = avaliar(Path(arg))
        print(f"\n[{r['arquivo']}]  {r['n_paginas']} págs, {r['n_marcadores']} marcadores")
        print(f"  {r['n_falas_cortadas']} fala(s) terminando em palavra cortada sem "
              f"continuação imediata")
        for ex in r["exemplos_cortes"]:
            print(f"    {ex['marcador']!r} ... termina em {ex['termina_em']!r}")
        print(f"  veredito: {r['veredito']}")


if __name__ == "__main__":
    main()
