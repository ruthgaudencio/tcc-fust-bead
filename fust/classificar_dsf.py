#!/usr/bin/env python3
"""
Aplica o teste da armadilha 23 (BRIEFING_COLETA.md) a cada DSF em
corpus_fust/senado/diarios/, nesta ordem:

  1. Há camada de texto? Amostra ~8 páginas, conta caracteres.
     Zero em todas = scan puro, OCR obrigatório.
  2. Há intercalação de coluna? Proxy: densidade de colagem
     (textnorm.detectar_colagens) contra o léxico de referência. O
     precedente conhecido (armadilha 23): DCD01SET2000 intercalado dá
     15-32 por mil; DSF-108-55 limpo dá ~2 por mil. Dezenas por mil ->
     suspeita de intercalação -> OCR obrigatório pra poder segmentar.
  3. Passando os dois: usar a camada nativa, pular o OCR.

Não decide corte nem roda OCR -- só classifica e grava o veredito, pra
`ocr_faixa.py` rodar somente onde a armadilha 23 reprovar (seção 4.5).

Não analisa arquivos cujo qtdPaginas/faixa impressa não bate com o PDF
real (ex. DSF-3-55, que mistura DSF de 13/01 com DCN de 28/01num só
arquivo, iText 2011): esses precisam de re-resolução antes de qualquer
teste de camada de texto fazer sentido, e entram como "escopo_incorreto".

    python classificar_dsf.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
DSF_DIR = CORPUS / "senado" / "diarios"
BRUTO = DSF_DIR / "_bruto"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import textnorm  # noqa: E402

LEXICO_FONTES = [CORPUS / "senado" / "MATE_TI_29602.pdf", RAIZ / "L9998.pdf"]

# Limiar de corte entre "limpo" e "intercalado", a meio caminho entre o
# precedente limpo (~2/mil) e o corrompido (15-32/mil) -- ver armadilha 23.
LIMIAR_COLAGEM_POR_MIL = 8.0

# DSF cujo conteúdo já foi verificado manualmente como fora de escopo (ver
# achado desta rodada: mistura DSF 13/01/2000 com DCN 28/01/2000 num só
# PDF iText de 2011). Marcado aqui porque amostrar texto desse arquivo sem
# saber qual trecho pertence a qual edição não serve de teste.
ESCOPO_INCORRETO = {
    "DSF-3-55.pdf": (
        "iText 2.1.3 (2011), paginaInicial/paginaFinal declarados (113-3437, "
        "3325 págs) não batem com a contagem real do PDF (2097 págs). Amostra "
        "manual: índices ~0-190 são DSF de 13/01/2000 (bate com o esperado), "
        "índices ~200+ são DIÁRIO DO CONGRESSO NACIONAL de 28/01/2000 -- "
        "outra publicação, outra data. codDiario=6331 resolveu um volume "
        "encadernado que cruza DSF e DCN. Não classificado; precisa de "
        "re-resolução (achar a faixa de índice certa dentro do volume) antes "
        "de qualquer teste de camada de texto."
    ),
}


def _n_paginas_reais(pdf_path: Path) -> int:
    from pypdf import PdfReader
    return len(PdfReader(str(pdf_path), strict=False).pages)


def _amostra_paginas(n_paginas: int, k: int = 8) -> list[int]:
    if n_paginas <= k:
        return list(range(n_paginas))
    passo = n_paginas / k
    return sorted({int(i * passo) for i in range(k)})


def passo1_tem_texto(pdf_path: Path) -> dict:
    from pypdf import PdfReader
    r = PdfReader(str(pdf_path), strict=False)
    n = len(r.pages)
    indices = _amostra_paginas(n)
    chars_por_pagina = {}
    for i in indices:
        t = r.pages[i].extract_text() or ""
        chars_por_pagina[i] = len(t)
    algum_com_texto = any(c > 0 for c in chars_por_pagina.values())
    return {
        "n_paginas": n,
        "indices_amostrados": indices,
        "chars_por_pagina_amostrada": chars_por_pagina,
        "tem_camada_de_texto": algum_com_texto,
    }


def _lexico() -> frozenset[str]:
    from pypdf import PdfReader
    textos = []
    for fonte in LEXICO_FONTES:
        if fonte.exists():
            r = PdfReader(str(fonte))
            textos.append("\n".join((p.extract_text() or "") for p in r.pages))
    return textnorm.construir_lexico(textos)


def passo2_densidade_colagem(pdf_path: Path, indices: list[int], lexico: frozenset[str]) -> dict:
    from pypdf import PdfReader
    r = PdfReader(str(pdf_path), strict=False)
    texto = "\n\n".join((r.pages[i].extract_text() or "") for i in indices)
    if not texto.strip():
        return {"aplicavel": False, "motivo": "sem camada de texto (passo 1 já reprovou)"}
    n = textnorm.normalizar(texto, tirar_acentos=True, rebaixar_caixa=False)
    colagens = textnorm.detectar_colagens(n, lexico)
    por_mil = (len(colagens) / len(texto) * 1000) if texto else 0.0
    return {
        "aplicavel": True,
        "chars_amostrados": len(texto),
        "colagens": len(colagens),
        "colagens_por_mil": round(por_mil, 2),
        "suspeita_intercalacao": por_mil >= LIMIAR_COLAGEM_POR_MIL,
    }


def classificar(pdf_path: Path, lexico: frozenset[str]) -> dict:
    nome = pdf_path.name
    if nome in ESCOPO_INCORRETO:
        return {"arquivo": nome, "veredito": "escopo_incorreto",
                "motivo": ESCOPO_INCORRETO[nome]}

    p1 = passo1_tem_texto(pdf_path)
    if not p1["tem_camada_de_texto"]:
        return {"arquivo": nome, "veredito": "ocr_obrigatorio",
                "motivo": f"passo 1: 0 caracteres em todas as {len(p1['indices_amostrados'])} "
                         f"páginas amostradas (scan puro)",
                "passo1": p1}

    p2 = passo2_densidade_colagem(pdf_path, p1["indices_amostrados"], lexico)
    if p2["suspeita_intercalacao"]:
        veredito = "ocr_obrigatorio"
        motivo = (f"passo 2: {p2['colagens_por_mil']} colagens/mil >= limiar "
                 f"{LIMIAR_COLAGEM_POR_MIL} -- suspeita de intercalação de coluna")
    else:
        veredito = "camada_nativa_ok"
        motivo = f"passo 2: {p2['colagens_por_mil']} colagens/mil, abaixo do limiar -- sem OCR"

    return {"arquivo": nome, "veredito": veredito, "motivo": motivo, "passo1": p1, "passo2": p2}


def main() -> None:
    pdfs = sorted(DSF_DIR.glob("DSF-*.pdf"))
    if not pdfs:
        raise SystemExit(f"nenhum DSF em {DSF_DIR}")

    print("=" * 78)
    print("CLASSIFICAR DSF -- teste da armadilha 23, por arquivo")
    print("=" * 78)

    print("\nconstruindo léxico de referência...")
    lexico = _lexico()
    print(f"  {len(lexico)} palavras")

    resultados = []
    for pdf in pdfs:
        print(f"\n[{pdf.name}]  ({pdf.stat().st_size:,} bytes)")
        r = classificar(pdf, lexico)
        resultados.append(r)
        print(f"  veredito: {r['veredito']}")
        print(f"  {r['motivo']}")

    saida = DSF_DIR / "classificacao_dsf.json"
    saida.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 78)
    print("RESUMO")
    print("=" * 78)
    for r in resultados:
        print(f"  {r['arquivo']:<16} {r['veredito']}")
    print(f"\nresultado: {saida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
