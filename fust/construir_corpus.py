#!/usr/bin/env python3
"""
Espelha o `corpus/` + `corpus_index.csv` do BEAD a partir da matriz de
argumentos já gravada (`fust/matriz/arguments_matrix_fust.csv`) -- um .txt
por fala, um `corpus_index.csv` com uma linha por fala. A pasta
`excerpts/` (trechos candidatos para codificação) fica para depois --
depende da regra de entrada no conjunto candidato, que é pendência externa
(item (i) combinado com o orientador, ainda não escrita).

Texto verbatim de cada fala:
  - pronunciamentos da API do Senado: um arquivo = uma fala, texto é tudo
    depois do offset do marcador até o fim do arquivo.
  - blocos de Diário (OCR): uma página pode ter várias falas. O fim de
    cada fala é o início da PRÓXIMA fala da mesma sessão (mesmo que isso
    atravesse página); a última fala do bloco fecha na âncora de fim do
    bloco (`BLOCOS` de `construir_matriz.py`), ou no fim da página final
    se não houver âncora.

    python construir_corpus.py             # só prévia/contagens
    python construir_corpus.py --gravar    # grava corpus/ e corpus_index.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import construir_matriz as cm  # noqa: E402
import coletor_senado as cs  # noqa: E402  -- reaproveita _slug/_sem_acento

MATRIZ_CSV = RAIZ / "fust" / "matriz" / "arguments_matrix_fust.csv"
CORPUS_DIR = RAIZ / "corpus_fust" / "corpus"
INDEX_CSV = RAIZ / "corpus_fust" / "corpus_index.csv"

COLUNAS_INDEX = [
    "id", "legislatura", "casa", "sessao_id", "data", "sessao",
    "orador_bruto", "partido_uf", "source", "needs_review",
    "corpus_file", "text_source", "text_status", "characters",
]

CASA_LABEL = {"senado": "Senado", "camara": "Câmara"}


def ler_matriz() -> list[dict]:
    with MATRIZ_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _pagina_de_corpus_file(corpus_file: str) -> int | None:
    m = re.search(r"p(\d+)\.txt$", corpus_file)
    return int(m.group(1)) if m else None


def extrair_textos(linhas: list[dict]) -> dict[str, str]:
    """devolve {id: texto verbatim da fala}."""
    textos: dict[str, str] = {}
    blocos_por_sessao = {b.sessao_id: b for b in cm.BLOCOS}
    cache_paginas: dict[tuple[str, int], str] = {}

    def texto_pagina(diretorio: Path, pagina: int) -> str:
        chave = (str(diretorio), pagina)
        if chave not in cache_paginas:
            cache_paginas[chave] = (diretorio / f"p{pagina}.txt").read_text(encoding="utf-8")
        return cache_paginas[chave]

    # Fonte 1: pronunciamentos da API -- um arquivo, uma fala
    for linha in linhas:
        if "pronunciamentos/" in linha["corpus_file"]:
            conteudo = (RAIZ / linha["corpus_file"]).read_text(encoding="utf-8")
            textos[linha["id"]] = conteudo[int(linha["offset"]):].strip()

    # Fonte 2: blocos de Diário -- agrupa por sessão, ordena, fecha pela próxima
    por_sessao: dict[str, list[dict]] = {}
    for linha in linhas:
        if "pronunciamentos/" not in linha["corpus_file"]:
            por_sessao.setdefault(linha["sessao_id"], []).append(linha)

    for sid, grupo in por_sessao.items():
        grupo.sort(key=lambda r: int(r["ordem"]))
        bloco = blocos_por_sessao[sid]
        for i, linha in enumerate(grupo):
            pagina_ini = _pagina_de_corpus_file(linha["corpus_file"])
            offset_ini = int(linha["offset"])
            if i + 1 < len(grupo):
                prox = grupo[i + 1]
                pagina_fim = _pagina_de_corpus_file(prox["corpus_file"])
                offset_fim = int(prox["offset"])
            else:
                pagina_fim = bloco.pagina_final
                texto_ultima = texto_pagina(bloco.diretorio, pagina_fim)
                if bloco.ancora_fim:
                    pos = texto_ultima.find(bloco.ancora_fim)
                    offset_fim = pos if pos != -1 else len(texto_ultima)
                else:
                    offset_fim = len(texto_ultima)

            if pagina_ini == pagina_fim:
                texto = texto_pagina(bloco.diretorio, pagina_ini)[offset_ini:offset_fim]
            else:
                partes = [texto_pagina(bloco.diretorio, pagina_ini)[offset_ini:]]
                for p in range(pagina_ini + 1, pagina_fim):
                    partes.append(texto_pagina(bloco.diretorio, p))
                partes.append(texto_pagina(bloco.diretorio, pagina_fim)[:offset_fim])
                texto = "\n".join(partes)
            textos[linha["id"]] = texto.strip()
    return textos


def nome_arquivo(linha: dict) -> str:
    autor = cs._slug(linha["orador_bruto"]) or "autor-desconhecido"
    partido_uf = cs._slug(linha["partido_uf"]) or "sem-partido"
    return f"{linha['id']}_{autor}_{partido_uf}_{linha['data']}.txt"


def cabecalho(linha: dict) -> str:
    casa_label = CASA_LABEL.get(linha["casa"], linha["casa"])
    partes = [
        f"# {linha['id']} | {linha['orador_bruto']} | {linha['partido_uf']}",
        f"# {casa_label} | Sessão de {linha['data']} | unit: {linha['unit']}",
        f"# {linha['sessao']}",
        f"# source: {linha['source']}",
    ]
    return "\n".join(partes) + "\n\n"


def montar_corpus() -> tuple[list[dict], dict[str, str]]:
    linhas = ler_matriz()
    textos = extrair_textos(linhas)
    return linhas, textos


def montar_index(linhas: list[dict], textos: dict[str, str]) -> list[dict]:
    index = []
    for linha in linhas:
        texto = textos.get(linha["id"], "")
        origem = "senado_api" if "pronunciamentos/" in linha["corpus_file"] else "diario_ocr"
        index.append({
            "id": linha["id"],
            "legislatura": "51",
            "casa": linha["casa"],
            "sessao_id": linha["sessao_id"],
            "data": linha["data"],
            "sessao": linha["sessao"],
            "orador_bruto": linha["orador_bruto"],
            "partido_uf": linha["partido_uf"],
            "source": origem,
            "needs_review": linha["needs_review"],
            "corpus_file": f"corpus/{nome_arquivo(linha)}",
            "text_source": linha["source"],
            "text_status": "ok" if texto else "sem texto (vazio após segmentação)",
            "characters": len(texto),
        })
    return index


def imprimir_relatorio(linhas: list[dict], textos: dict[str, str], index: list[dict]) -> None:
    nomes = [cm_i["corpus_file"] for cm_i in index]
    distintos = set(nomes)
    sem_texto = [i for i in index if i["characters"] == 0]

    print(f"linhas na matriz: {len(linhas)}")
    print(f"arquivos a gravar: {len(index)}")
    print(f"nomes de arquivo distintos: {len(distintos)}")
    if len(distintos) != len(nomes):
        colisoes = [n for n in distintos if nomes.count(n) > 1]
        print(f"  COLISÃO -- {len(nomes) - len(distintos)} nome(s) repetido(s): {colisoes}")
    else:
        print("  nenhuma colisão de nome")
    print(f"sem texto: {len(sem_texto)}")
    for i in sem_texto[:10]:
        print(f"  {i['id']}  {i['orador_bruto']!r}  sessao={i['sessao_id']}  corpus_file original={[l['corpus_file'] for l in linhas if l['id']==i['id']][0]}")


def gravar(linhas: list[dict], textos: dict[str, str], index: list[dict]) -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for linha in linhas:
        texto = textos.get(linha["id"], "")
        caminho = CORPUS_DIR / nome_arquivo(linha)
        caminho.write_text(cabecalho(linha) + texto + "\n", encoding="utf-8")

    with INDEX_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_INDEX)
        w.writeheader()
        for i in index:
            w.writerow(i)

    print(f"\ngravado: {len(linhas)} arquivos em {CORPUS_DIR.relative_to(RAIZ)}/")
    print(f"gravado: {INDEX_CSV.relative_to(RAIZ)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gravar", action="store_true")
    args = ap.parse_args()

    linhas, textos = montar_corpus()
    index = montar_index(linhas, textos)
    imprimir_relatorio(linhas, textos, index)

    if args.gravar:
        gravar(linhas, textos, index)
    else:
        print("\n(prévia só -- rode com --gravar para escrever corpus/ e corpus_index.csv)")


if __name__ == "__main__":
    main()
