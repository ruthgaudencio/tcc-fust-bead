#!/usr/bin/env python3
"""
OCR página a página (não concatenado) -- preserva a atribuição de página,
que `ocr_faixa.py` perde ao juntar tudo com "\\n\\n".join(...). Serve tanto
pra localizar em que página um termo aparece (--termos) quanto só pra
gerar o texto por página que a segmentação por orador (seção 4.6) precisa
-- nesse caso --termos é opcional, não busca nada, só grava.

Aceita DSF (corpus_fust/senado/diarios/) e DCD (corpus_fust/diarios_camara/
ou qualquer recorte, ex. em camara/emendas/_compartilhados/) -- se --pdf
não for um nome simples, procura nos dois lugares, depois tenta como
caminho relativo à raiz do projeto.

    python ocr_pagina_a_pagina.py --pdf DSF-201-54_p34747-34945.pdf \\
        --pagina-inicial-impressa 34747 \\
        --termos ANATEL "Navarro Guerreiro" "Pimenta da Veiga" universalização FUST

    python ocr_pagina_a_pagina.py \\
        --pdf camara/emendas/_compartilhados/DCD08DEZ1999_p60552-60574.pdf \\
        --pagina-inicial-impressa 60552
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
DSF_DIR = CORPUS / "senado" / "diarios"
DCD_DIR = CORPUS / "diarios_camara"


def _resolver_pdf(nome_ou_caminho: str) -> Path:
    direto = Path(nome_ou_caminho)
    if direto.is_absolute() and direto.exists():
        return direto
    for base in (DSF_DIR, DCD_DIR, CORPUS, RAIZ):
        candidato = base / nome_ou_caminho
        if candidato.exists():
            return candidato
    raise SystemExit(f"não achei {nome_ou_caminho!r} em {DSF_DIR}, {DCD_DIR}, {CORPUS} nem {RAIZ}")


def _sem_acento(s: str) -> str:
    d = unicodedata.normalize("NFD", s)
    return "".join(c for c in d if not unicodedata.combining(c))


def _n_paginas(pdf: Path) -> int:
    r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    for linha in r.stdout.splitlines():
        if linha.startswith("Pages:"):
            return int(linha.split()[1])
    raise RuntimeError(f"pdfinfo não devolveu contagem de páginas para {pdf}")


def ocr_pagina(pdf: Path, pagina_pdf: int, tmp: Path, *, psm: str = "1") -> str:
    """psm 1 (automático com OSD) linhariza certo o corpo de texto normal,
    mas quebra o layout de 2 colunas do SUMÁRIO (texto + coluna de número
    de página): tesseract separa isso em blocos e joga todos os números
    pro final, desgrudados da linha de cada um. Testado: psm 4 (coluna
    única de tamanho variável) e psm 6 (bloco único uniforme) mantêm o
    número colado na linha certa nessas páginas. Usar psm 4 pro sumário,
    psm 1 (padrão) pro corpo."""
    prefixo = tmp / f"pg{pagina_pdf}"
    subprocess.run(
        ["pdftoppm", "-f", str(pagina_pdf), "-l", str(pagina_pdf),
         "-r", "300", "-gray", "-png", str(pdf), str(prefixo)],
        check=True, capture_output=True,
    )
    pngs = sorted(tmp.glob(f"pg{pagina_pdf}-*.png")) or sorted(tmp.glob(f"pg{pagina_pdf}.png"))
    if not pngs:
        return ""
    r = subprocess.run(
        ["tesseract", str(pngs[0]), "-", "-l", "por", "--psm", psm],
        capture_output=True, text=True,
    )
    pngs[0].unlink(missing_ok=True)
    return r.stdout


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True,
                    help="nome em corpus_fust/senado/diarios/, corpus_fust/diarios_camara/, "
                         "ou caminho relativo/absoluto")
    ap.add_argument("--pagina-inicial-impressa", type=int, required=True)
    ap.add_argument("--termos", nargs="+", default=[],
                    help="opcional -- sem isso, só gera o texto por página")
    ap.add_argument("--saida-dir", default=None,
                    help="onde salvar um .txt por página (padrão: <pdf>_paginas/)")
    ap.add_argument("--psm", default="1",
                    help="modo de segmentação do tesseract. padrão 1 (bom pro corpo); "
                         "use 4 pra páginas de SUMÁRIO (2 colunas texto+página -- "
                         "psm 1 desgruda o número da linha)")
    args = ap.parse_args()

    pdf_path = _resolver_pdf(args.pdf)
    n = _n_paginas(pdf_path)
    if args.saida_dir:
        saida_dir = Path(args.saida_dir)
        if not saida_dir.is_absolute():
            saida_dir = RAIZ / saida_dir
    else:
        saida_dir = pdf_path.parent / f"{pdf_path.stem}_paginas"
    saida_dir.mkdir(parents=True, exist_ok=True)

    termos_norm = [(_sem_acento(t).lower(), t) for t in args.termos]
    achados = {t: [] for _, t in termos_norm}

    print(f"[{args.pdf}] {n} páginas, páginas impressas a partir de "
          f"{args.pagina_inicial_impressa}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        for i in range(1, n + 1):
            pagina_impressa = args.pagina_inicial_impressa + (i - 1)
            texto = ocr_pagina(pdf_path, i, tmp, psm=args.psm)
            (saida_dir / f"p{pagina_impressa}.txt").write_text(texto, encoding="utf-8")

            texto_norm = _sem_acento(texto).lower()
            for chave, original in termos_norm:
                if chave in texto_norm:
                    idx = texto_norm.find(chave)
                    contexto = texto[max(0, idx - 80):idx + len(chave) + 80].replace("\n", " ")
                    achados[original].append({"pagina_impressa": pagina_impressa, "contexto": contexto})

            if i % 20 == 0 or i == n:
                print(f"  ... {i}/{n} páginas processadas")

    if termos_norm:
        print("\n" + "=" * 78)
        print("RESULTADO DA BUSCA")
        print("=" * 78)
        for termo, ocorrencias in achados.items():
            if ocorrencias:
                paginas = sorted({o["pagina_impressa"] for o in ocorrencias})
                print(f"\n'{termo}': achado na(s) página(s) {paginas}")
                for o in ocorrencias[:3]:
                    print(f"    pág {o['pagina_impressa']}: ...{o['contexto']}...")
            else:
                print(f"\n'{termo}': NÃO apareceu em nenhuma página")

        import json
        resultado = {t: v for t, v in achados.items()}
        destino = pdf_path.parent / f"busca_termos_{pdf_path.stem}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nresultado da busca: {destino.relative_to(RAIZ)}")

    print(f"\ntexto por página salvo em: {saida_dir.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
