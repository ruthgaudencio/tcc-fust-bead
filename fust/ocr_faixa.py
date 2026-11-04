#!/usr/bin/env python3
"""
Encadeia paginas.extrair_faixa -> pdftoppm -> tesseract -l por --psm 1 ->
mede a densidade de colagem de espaço ANTES (camada nativa) e DEPOIS
(re-OCR), pra comparar com os números da seção 6 do briefing (medidos no
DCD01SET2000: 32->9 colagens por mil caracteres na pág. 100, 15->7 na
pág. 150).

Pros DSF (Diário do Senado): NÃO chama paginas.calibrar. O metadado já
embutido em corpus_fust/senado/diarios/_bruto/diario_{codigo}.json (salvo
pelo coletor_dsf.py a partir do bloco "var diario" da página
/diarios/ver/{cod}) já declara a página impressa inicial -- o
deslocamento é paginaInicial - 1, direto. Chamar calibrar() por cima
disso seria redundante (o Diário não tem ambiguidade de numeração
reiniciada dentro dele mesmo, já vem declarado) e mais lento.
Calibração por cabeçalho (amostrar e votar) continua valendo só pros
DCD da Câmara, que não têm esse metadado.

    python ocr_faixa.py --dsf DSF-108-55.pdf \\
        --pagina-inicial 14200 --pagina-final 14320

Precisa de pdftoppm e tesseract no PATH (poppler + tesseract, com pacote
de português -- armadilha 13). Sem eles, roda só a medição "antes" (usa
pypdf, não precisa de poppler) e avisa exatamente o que falta antes de
parar -- não inventa número de "depois".

léxico de referência pra detectar_colagens: textos nativos digitais já
coletados (MATE_TI_29602.pdf + L9998.pdf), conforme o aviso do próprio
textnorm.py (não alimentar com texto OCRizado, senão a métrica desaba).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
DSF_DIR = CORPUS / "senado" / "diarios"
DSF_BRUTO = DSF_DIR / "_bruto"

LEXICO_FONTES = [
    CORPUS / "senado" / "MATE_TI_29602.pdf",
    RAIZ / "L9998.pdf",
]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paginas  # noqa: E402
import textnorm  # noqa: E402


def _ferramentas_faltando() -> list[str]:
    return [b for b in ("pdftoppm", "tesseract") if shutil.which(b) is None]


def calibracao_de_metadado_dsf(nome_pdf: str) -> "paginas.Calibracao":
    """Constrói a Calibracao a partir do metadado já coletado, sem OCR."""
    cods = list(DSF_BRUTO.glob("diario_*.json"))
    for c in cods:
        info = json.loads(c.read_text(encoding="utf-8"))
        nome_esperado = f"DSF-{info['numero']}-{info['ano']}.pdf"
        if nome_esperado == nome_pdf:
            pdf_path = DSF_DIR / nome_pdf
            n_paginas_real = paginas._n_paginas(pdf_path) if shutil.which("pdfinfo") else info["qtdPaginas"]
            return paginas.Calibracao(
                pdf=str(pdf_path),
                deslocamento=info["paginaInicial"] - 1,
                paginas_pdf=n_paginas_real,
                amostras_validas=info["qtdPaginas"],
                concordancia=1.0,  # do metadado declarado, não amostrado
            )
    raise SystemExit(f"não achei metadado de {nome_pdf} em {DSF_BRUTO} "
                     f"(rode coletor_dsf.py primeiro)")


def extrair_texto_nativo_pypdf(pdf_path: Path, pagina_1based: int) -> str:
    """Substituto de pdftotext quando poppler não está instalado --
    mesmo propósito (texto da camada nativa de 1 página), fonte diferente.
    """
    from pypdf import PdfReader
    r = PdfReader(str(pdf_path))
    return r.pages[pagina_1based - 1].extract_text() or ""


def construir_lexico_de_referencia() -> frozenset[str]:
    from pypdf import PdfReader
    textos = []
    for fonte in LEXICO_FONTES:
        if not fonte.exists():
            print(f"  !! léxico: {fonte} não existe, pulando")
            continue
        r = PdfReader(str(fonte))
        textos.append("\n".join((p.extract_text() or "") for p in r.pages))
    if not textos:
        raise SystemExit("nenhuma fonte de léxico disponível (MATE_TI_29602.pdf / L9998.pdf)")
    return textnorm.construir_lexico(textos)


def medir_colagem(texto: str, lexico: frozenset[str]) -> dict:
    n = textnorm.normalizar(texto, tirar_acentos=True, rebaixar_caixa=False)
    colagens = textnorm.detectar_colagens(n, lexico)
    chars = len(texto)
    por_mil = (len(colagens) / chars * 1000) if chars else 0.0
    return {"chars": chars, "colagens": len(colagens), "colagens_por_mil_chars": round(por_mil, 2)}


def rasterizar_e_ocr(pdf_recortado: Path, saida_txt: Path) -> str:
    """pdftoppm -r 300 -gray -png -> tesseract -l por --psm 1, página a
    página do PDF recortado, concatenado."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        prefixo = Path(tmp) / "pg"
        subprocess.run(
            ["pdftoppm", "-r", "300", "-gray", "-png", str(pdf_recortado), str(prefixo)],
            check=True, capture_output=True,
        )
        pngs = sorted(Path(tmp).glob("pg-*.png"))
        if not pngs:
            raise RuntimeError("pdftoppm não gerou nenhum PNG")
        texto_completo = []
        for png in pngs:
            r = subprocess.run(
                ["tesseract", str(png), "-", "-l", "por", "--psm", "1"],
                capture_output=True, text=True,
            )
            texto_completo.append(r.stdout)
    texto = "\n\n".join(texto_completo)
    saida_txt.write_text(texto, encoding="utf-8")
    return texto


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsf", required=True, help="nome do arquivo em corpus_fust/senado/diarios/")
    ap.add_argument("--pagina-inicial", type=int, required=True, help="página IMPRESSA")
    ap.add_argument("--pagina-final", type=int, help="padrão: igual à inicial")
    args = ap.parse_args()

    pagina_final = args.pagina_final or args.pagina_inicial

    print("=" * 78)
    print(f"OCR_FAIXA -- {args.dsf}, páginas impressas {args.pagina_inicial}-{pagina_final}")
    print("=" * 78)

    cal = calibracao_de_metadado_dsf(args.dsf)
    print(f"\ncalibração (do metadado, sem OCR): deslocamento={cal.deslocamento}  "
          f"faixa impressa declarada {cal.primeira_impressa}-{cal.ultima_impressa}  "
          f"({cal.paginas_pdf} págs no PDF)")

    idx_i = cal.para_pdf(args.pagina_inicial)
    idx_f = cal.para_pdf(pagina_final)
    if idx_i is None or idx_f is None:
        raise SystemExit(f"página fora da faixa do Diário ({cal.primeira_impressa}-"
                         f"{cal.ultima_impressa})")
    print(f"-> índice no PDF: {idx_i} a {idx_f}")

    print("\nconstruindo léxico de referência (textos nativos digitais)...")
    lexico = construir_lexico_de_referencia()
    print(f"  {len(lexico)} palavras no léxico")

    print("\n--- ANTES (camada nativa do PDF) ---")
    pdf_path = DSF_DIR / args.dsf
    texto_antes = "\n\n".join(
        extrair_texto_nativo_pypdf(pdf_path, i) for i in range(idx_i, idx_f + 1)
    )
    m_antes = medir_colagem(texto_antes, lexico)
    print(f"  {m_antes['chars']} caracteres, {m_antes['colagens']} colagens, "
          f"{m_antes['colagens_por_mil_chars']} por mil")

    faltando = _ferramentas_faltando()
    if faltando:
        print(f"\n!! sem {', '.join(faltando)} no PATH -- não dá pra rodar o 'DEPOIS' "
              f"(rasterizar + tesseract -l por --psm 1). Medição 'antes' registrada; "
              f"'depois' pendente de instalar essas ferramentas.")
        resultado = {"dsf": args.dsf, "pagina_inicial": args.pagina_inicial,
                     "pagina_final": pagina_final, "antes": m_antes,
                     "depois": None, "motivo_sem_depois": f"faltam no PATH: {faltando}"}
        _gravar(resultado)
        return

    print("\nrecortando faixa com qpdf...")
    recorte = paginas.extrair_faixa(pdf_path, cal, args.pagina_inicial, pagina_final)
    print(f"  {recorte}")

    print("\nrasterizando (300dpi, escala de cinza) e rodando tesseract -l por --psm 1...")
    saida_txt = recorte.with_suffix(".ocr.txt")
    texto_depois = rasterizar_e_ocr(recorte, saida_txt)

    print("\n--- DEPOIS (re-OCR) ---")
    m_depois = medir_colagem(texto_depois, lexico)
    print(f"  {m_depois['chars']} caracteres, {m_depois['colagens']} colagens, "
          f"{m_depois['colagens_por_mil_chars']} por mil")

    print(f"\ntexto do re-OCR salvo em: {saida_txt}")
    resultado = {"dsf": args.dsf, "pagina_inicial": args.pagina_inicial,
                 "pagina_final": pagina_final, "antes": m_antes, "depois": m_depois}
    _gravar(resultado)


def _gravar(resultado: dict) -> None:
    destino = DSF_DIR / f"ocr_faixa_resultado_{resultado['dsf'].replace('.pdf', '')}.json"
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultado: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
