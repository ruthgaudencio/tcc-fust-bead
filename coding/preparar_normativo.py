"""
Eixo normativo: identifica, no texto APROVADO de cada caso, quais subcategorias
são nomeadas e onde.

Resolve um problema do desenho anterior. A lista `normative_candidatos.csv` foi
montada a partir de termos de MECANISMO, de modo que ela encontra o dispositivo
que institui percentual, elegibilidade, meta ou monitoramento, mas não encontra
o dispositivo que apenas NOMEIA um grupo sem mecanismo algum. Essa é exatamente
a fronteira entre o nível ausente e o superficial da seção 3.3, e sem varrer o
texto da lei com a lista de termos não há como distingui-los: uma subcategoria
sem candidato seria lida como ausente mesmo quando a lei a nomeia.

A varredura reusa `fust/matriz/lexico.py`, o mesmo módulo da passada principal,
para que a régua aplicada à lei seja a mesma aplicada ao debate.

ESCOLHA METODOLÓGICA EM ABERTO: o que conta como "texto aprovado" de cada caso.
Este script NÃO decide por você. Ele varre todos os textos disponíveis e grava a
procedência de cada menção em coluna própria, de modo que a definição do escopo
continue sendo sua e possa ser feita depois, filtrando por arquivo. Do lado
brasileiro a questão é se a Lei Geral de Telecomunicações entra ao lado da Lei
do Fust; do lado norte-americano, se as definições do Digital Equity Act entram
ao lado da seção que cria o BEAD. A segunda decisão é a que mais muda o
resultado, porque é no Digital Equity Act que idade, deficiência, raça e etnia e
barreira linguística aparecem nomeadas.

    python3 coding/preparar_normativo.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "fust" / "matriz"))
import lexico  # noqa: E402

TERMOS = BASE / "fust" / "matriz" / "termos.csv"
EXCECOES = BASE / "fust" / "matriz" / "termos_excecao.csv"
SAIDA = BASE / "coding"

TEXTOS = {
    "FUST": [("Lei 9.998/2000", BASE / "corpus_fust" / "lei9998_texto_original.txt"),
             ("Lei 9.472/1997, arts. 79-81", BASE / "corpus_fust" / "lei9472_arts79-81.txt")],
    "BEAD": [("IIJA SEC. 60102", BASE / "corpus_bead" / "iija_sec60102.txt"),
             ("IIJA Digital Equity Act", BASE / "corpus_bead" / "iija_digital_equity_act.txt"),
             ("IIJA Division F", BASE / "corpus_bead" / "iija_division_f.txt")],
}
SISTEMA = {"FUST": "BR", "BEAD": "US"}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def corpo_de_lei(texto: str) -> str:
    """Tira só as linhas de cabeçalho que começam com '#'. O texto de lei não tem
    a mesma estrutura dos arquivos do corpus, então extrair_corpo() não serve:
    ela cortaria no primeiro parágrafo em branco e perderia a ementa."""
    linhas = texto.splitlines(keepends=True)
    i = 0
    while i < len(linhas) and (linhas[i].lstrip().startswith("#") or not linhas[i].strip()):
        i += 1
    return "".join(linhas[i:])


def main():
    excecoes = lexico.ler_excecoes(EXCECOES)
    mencoes, faltando = [], []

    for caso, arquivos in TEXTOS.items():
        termos = lexico.ler_termos(TERMOS, SISTEMA[caso])
        for rotulo, caminho in arquivos:
            if not caminho.exists():
                faltando.append(str(caminho))
                continue
            corpo = corpo_de_lei(caminho.read_text(encoding="utf-8", errors="replace"))
            occs, _ = lexico.escanear_arquivo(corpo, termos, excecoes)
            for o in occs:
                mencoes.append({
                    "caso": caso, "diploma": rotulo, "arquivo": caminho.name,
                    "codigo": o.codigo, "subcategoria": o.subcategoria,
                    "termo_da_lista": o.termo_da_lista,
                    "forma_encontrada": o.forma_encontrada,
                    "passada": o.passada, "offset": o.offset,
                    "contexto": " ".join(o.contexto.split()),
                })
            print(f"  {caso:5s} {rotulo:28s} {len(occs):5d} menções")

    if faltando:
        print("\naviso: arquivos não encontrados:")
        for f in faltando:
            print("   ", f)

    cols = ["caso", "diploma", "arquivo", "codigo", "subcategoria", "termo_da_lista",
            "forma_encontrada", "passada", "offset", "contexto"]
    p = SAIDA / "normativo_mencoes.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(mencoes)

    # cobertura: a lei nomeia a subcategoria? e em que diploma?
    nomes = {}
    for t in csv.DictReader(TERMOS.open(encoding="utf-8")):
        nomes[t["codigo"]] = t["subcategoria"]
    por = defaultdict(lambda: defaultdict(int))
    for m in mencoes:
        por[(m["caso"], m["codigo"])][m["diploma"]] += 1

    linhas = []
    for caso in TEXTOS:
        for cod in sorted(nomes, key=lambda c: [int(x) for x in c.split(".")]):
            d = por.get((caso, cod), {})
            linhas.append({
                "caso": caso, "codigo": cod, "subcategoria": nomes[cod],
                "nomeada_no_texto_aprovado": "sim" if d else "nao",
                "diplomas": "; ".join(f"{k} ({v})" for k, v in sorted(d.items())),
                "total_mencoes": sum(d.values()),
            })
    p2 = SAIDA / "normativo_cobertura.csv"
    with p2.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["caso", "codigo", "subcategoria",
                                          "nomeada_no_texto_aprovado", "diplomas",
                                          "total_mencoes"])
        w.writeheader()
        w.writerows(linhas)

    print(f"\n{len(mencoes)} menções -> {p.name}")
    print(f"{len(linhas)} células -> {p2.name}")
    for caso in TEXTOS:
        s = sum(1 for x in linhas if x["caso"] == caso and x["nomeada_no_texto_aprovado"] == "sim")
        print(f"   {caso}: {s} de 18 subcategorias nomeadas no texto aprovado")


if __name__ == "__main__":
    main()
