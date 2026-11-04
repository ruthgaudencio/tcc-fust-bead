"""
Prepara os lotes de codificação do eixo discursivo.

A unidade codificada é o PAR (fala, subcategoria): para cada fala em que uma
subcategoria foi invocada, decide-se se há razão declarada e se há dado ou
diagnóstico. O nível da subcategoria por caso é agregado depois, por
agregar_eixo_discursivo.py, pela regra do nível mais alto alcançado.

O offset de lexico_ocorrencias.csv é relativo ao CORPO do arquivo do corpus,
isto é, ao texto que começa depois da última linha de cabeçalho ('# source:').
Verificado em amostra: o deslocamento entre o offset e a posição real no arquivo
é igual à posição de início do corpo, em todos os casos testados.

Uso:
    python3 preparar_lotes.py                 # os dois casos
    python3 preparar_lotes.py --caso FUST
    python3 preparar_lotes.py --pares-por-lote 15 --janelas-por-par 8

Saída:
    coding/lotes/<CASO>_lote_0001.json ...    um arquivo por lote
    coding/lotes/_indice_lotes.csv            quantos pares e janelas em cada lote
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

CASOS = {
    "FUST": {"raiz": "corpus_fust", "ocorrencias": "corpus_fust/lexico_ocorrencias.csv",
             "indice": "corpus_fust/corpus_index.csv", "lingua": "pt"},
    "BEAD": {"raiz": "corpus_bead", "ocorrencias": "corpus_bead/lexico_ocorrencias.csv",
             "indice": "corpus_bead/corpus_index.csv", "lingua": "en"},
}

MARCA_FIM_CABECALHO = "# source:"
JANELA = 900          # caracteres de cada lado, antes de ajustar para fronteira de frase
FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def inicio_do_corpo(texto: str) -> int:
    """Primeira posição do corpo: depois da linha '# source:' e dos brancos seguintes."""
    p = texto.rfind(MARCA_FIM_CABECALHO)
    if p == -1:
        # arquivo sem cabeçalho conhecido: o corpo é o arquivo todo
        return 0
    fim = texto.find("\n", p)
    if fim == -1:
        return len(texto)
    j = fim + 1
    while j < len(texto) and texto[j] in " \t\r\n":
        j += 1
    return j


def recortar(corpo: str, inicio: int, fim: int, janela: int = JANELA) -> tuple[int, int, str]:
    """Janela em volta de [inicio, fim), ajustada para fronteira de frase quando possível."""
    a = max(0, inicio - janela)
    b = min(len(corpo), fim + janela)
    # recua 'a' até depois do fim de frase mais próximo, para não começar no meio
    if a > 0:
        m = list(FIM_DE_FRASE.finditer(corpo, a, inicio))
        if m:
            a = m[0].end()
    # avança 'b' até o fim de frase mais próximo
    if b < len(corpo):
        m = FIM_DE_FRASE.search(corpo, fim, b + 400)
        if m:
            b = m.end()
    return a, b, " ".join(corpo[a:b].split())


def fundir(intervalos: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Funde intervalos que se sobrepõem, para não mostrar o mesmo trecho duas vezes."""
    if not intervalos:
        return []
    intervalos = sorted(intervalos)
    saida = [list(intervalos[0])]
    for a, b in intervalos[1:]:
        if a <= saida[-1][1]:
            saida[-1][1] = max(saida[-1][1], b)
        else:
            saida.append([a, b])
    return [(a, b) for a, b in saida]


def carregar(caso: str, base: Path):
    cfg = CASOS[caso]
    occ_path = base / cfg["ocorrencias"]
    idx_path = base / cfg["indice"]
    if not occ_path.exists():
        raise SystemExit(f"não encontrei {occ_path}")
    idx = {r["id"]: r for r in csv.DictReader(idx_path.open(encoding="utf-8"))}
    ocorrencias = list(csv.DictReader(occ_path.open(encoding="utf-8")))
    return cfg, idx, ocorrencias


def construir(caso: str, base: Path, janelas_por_par: int):
    cfg, idx, ocorrencias = carregar(caso, base)
    raiz = base / cfg["raiz"]

    por_par: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for o in ocorrencias:
        por_par[(o["id"], o["subcategoria"])].append(o)

    cache_corpo: dict[str, str] = {}
    pares = []
    sem_arquivo = 0

    for (uid, sub), occs in sorted(por_par.items()):
        rec = idx.get(uid)
        if not rec:
            sem_arquivo += 1
            continue
        if uid not in cache_corpo:
            cf = raiz / rec["corpus_file"]
            if not cf.exists():
                sem_arquivo += 1
                cache_corpo[uid] = ""
            else:
                texto = cf.read_text(encoding="utf-8", errors="replace")
                cache_corpo[uid] = texto[inicio_do_corpo(texto):]
        corpo = cache_corpo[uid]
        if not corpo:
            continue

        intervalos, termos = [], []
        for o in occs:
            try:
                off = int(o["offset"])
            except (ValueError, KeyError):
                continue
            forma = o.get("forma_encontrada") or ""
            intervalos.append((off, off + max(1, len(forma))))
            termos.append({"termo_da_lista": o.get("termo_da_lista", ""),
                           "forma_encontrada": forma,
                           "passada": o.get("passada", "")})

        fundidos = fundir(intervalos)
        janelas = []
        for a, b in fundidos[:janelas_por_par]:
            ja, jb, trecho = recortar(corpo, a, b)
            janelas.append({"inicio_corpo": ja, "fim_corpo": jb, "trecho": trecho})

        pares.append({
            "caso": caso,
            "par_id": f"{uid}::{sub}",
            "unit_id": uid,
            "subcategoria": sub,
            "categoria": occs[0].get("categoria", ""),
            "codigo": occs[0].get("codigo", ""),
            "lingua": cfg["lingua"],
            "casa_ou_camara": rec.get("casa") or rec.get("chamber", ""),
            "data": rec.get("data", ""),
            "orador": rec.get("orador_bruto") or rec.get("witness", ""),
            "n_ocorrencias_no_par": len(occs),
            "n_janelas_mostradas": len(janelas),
            "n_janelas_omitidas": max(0, len(fundidos) - len(janelas)),
            "passadas": sorted({t["passada"] for t in termos if t["passada"]}),
            "termos": termos[:12],
            "janelas": janelas,
        })

    if sem_arquivo:
        print(f"  aviso: {sem_arquivo} pares sem arquivo de corpus correspondente")
    return pares


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=".", help="pasta que contém corpus_fust/ e corpus_bead/")
    ap.add_argument("--caso", choices=sorted(CASOS), action="append")
    ap.add_argument("--pares-por-lote", type=int, default=20)
    ap.add_argument("--janelas-por-par", type=int, default=6)
    ap.add_argument("--saida", default="coding/lotes")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    saida = base / args.saida
    saida.mkdir(parents=True, exist_ok=True)

    linhas_indice = []
    for caso in (args.caso or sorted(CASOS)):
        print(f"=== {caso}")
        pares = construir(caso, base, args.janelas_por_par)
        print(f"  {len(pares)} pares")
        dist = sorted((p["n_ocorrencias_no_par"] for p in pares), reverse=True)
        if dist:
            print(f"  ocorrências por par: max={dist[0]} mediana={dist[len(dist)//2]} "
                  f"pares com janela omitida={sum(1 for p in pares if p['n_janelas_omitidas'])}")
        for i in range(0, len(pares), args.pares_por_lote):
            lote = pares[i:i + args.pares_por_lote]
            n = i // args.pares_por_lote + 1
            nome = f"{caso}_lote_{n:04d}.json"
            (saida / nome).write_text(
                json.dumps({"caso": caso, "lote": n, "pares": lote}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            linhas_indice.append({"arquivo": nome, "caso": caso, "lote": n,
                                  "n_pares": len(lote),
                                  "n_janelas": sum(p["n_janelas_mostradas"] for p in lote)})
        print(f"  {linhas_indice[-1]['lote'] if linhas_indice else 0} lotes gravados em {saida}")

    with (saida / "_indice_lotes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arquivo", "caso", "lote", "n_pares", "n_janelas"])
        w.writeheader()
        w.writerows(linhas_indice)
    print(f"\nindice: {saida / '_indice_lotes.csv'}  ({len(linhas_indice)} lotes)")


if __name__ == "__main__":
    main()
