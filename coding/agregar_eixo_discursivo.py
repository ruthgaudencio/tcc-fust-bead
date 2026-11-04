"""
Agrega os pares codificados ao nível da subcategoria por caso, pela regra do
NÍVEL MAIS ALTO ALCANÇADO, e preenche coding/eixo_discursivo.csv.

Regra (INSTRUMENTO_CODIFICACAO.md, item 5):
    estrutural   -> algum par da célula é estrutural
    superficial  -> nenhum estrutural e algum superficial
    ausente      -> nenhum par pertinente

Não inventa nada: célula sem par codificado fica com nivel vazio e é contada
como pendente. Rodar quantas vezes quiser, é idempotente.

Uso:
    python3 coding/agregar_eixo_discursivo.py            # relatório + grava
    python3 coding/agregar_eixo_discursivo.py --so-ver   # só relatório
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import recorte

PARES = "coding/pares_eixo_discursivo.csv"
CELULAS = "coding/eixo_discursivo.csv"

COLS_SAIDA = ["razao_declarada", "dado_ou_diagnostico", "nivel",
              "unit_id_evidencia", "evidencia_verbatim", "notas"]
COLS_CONTAGEM = ["n_pares", "n_pares_estrutural", "n_pares_superficial",
                 "n_pares_falso_positivo", "n_pares_indeterminado"]

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def sim(v: str) -> bool:
    return (v or "").strip().lower() in ("sim", "s", "yes", "true", "1")


def agregar(pares: list[dict]) -> dict:
    """Decide a célula a partir dos seus pares."""
    pertinentes = [p for p in pares if (p.get("pertinencia") or "").strip().lower() == "sim"]
    estruturais = [p for p in pertinentes
                   if (p.get("nivel_do_par") or "").strip().lower() == "estrutural"]
    superficiais = [p for p in pertinentes
                    if (p.get("nivel_do_par") or "").strip().lower() == "superficial"]
    indeterminados = [p for p in pares
                      if (p.get("nivel_do_par") or "").strip().lower() == "indeterminado"]
    falsos = [p for p in pares
              if (p.get("nivel_do_par") or "").strip().lower() == "falso_positivo"]

    if estruturais:
        nivel, fonte = "estrutural", estruturais[0]
    elif superficiais:
        nivel, fonte = "superficial", superficiais[0]
    elif pertinentes:
        # pertinente mas sem nível atribuído: não decide, declara pendência
        nivel, fonte = "", None
    else:
        nivel, fonte = ("ausente", None) if pares else ("", None)

    notas = []
    if indeterminados:
        notas.append(f"{len(indeterminados)} par(es) indeterminado(s)")
    if falsos:
        notas.append(f"{len(falsos)} ocorrência(s) descartada(s) como falso positivo")
    if pertinentes and not nivel:
        notas.append("pares pertinentes sem nivel_do_par: recodificar")

    return {
        "razao_declarada": "sim" if any(sim(p.get("razao_declarada")) for p in pertinentes)
                           else ("nao" if pertinentes else ""),
        "dado_ou_diagnostico": "sim" if any(sim(p.get("dado_ou_diagnostico")) for p in pertinentes)
                               else ("nao" if pertinentes else ""),
        "nivel": nivel,
        "unit_id_evidencia": (fonte or {}).get("unit_id", ""),
        "evidencia_verbatim": (fonte or {}).get("trecho_evidencia", ""),
        "notas": "; ".join(notas),
        "n_pares": len(pares),
        "n_pares_estrutural": len(estruturais),
        "n_pares_superficial": len(superficiais),
        "n_pares_falso_positivo": len(falsos),
        "n_pares_indeterminado": len(indeterminados),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=".")
    ap.add_argument("--so-ver", action="store_true")
    args = ap.parse_args()
    base = Path(args.base).resolve()

    pares_path, celulas_path = base / PARES, base / CELULAS
    if not celulas_path.exists():
        raise SystemExit(f"não encontrei {celulas_path}")
    if not pares_path.exists():
        raise SystemExit(f"não encontrei {pares_path} — a codificação ainda não começou")

    por_celula: dict[tuple[str, str], list[dict]] = defaultdict(list)
    vistos: set[str] = set()
    for p in csv.DictReader(pares_path.open(encoding="utf-8")):
        pid = (p.get("par_id") or "").strip()
        if not pid or pid in vistos:      # última ocorrência vence seria pior: mantém a primeira
            continue
        vistos.add(pid)
        if not recorte.manter(p.get("caso", ""), p.get("unit_id", "")):
            continue                      # fora do recorte declarado em recorte.py
        por_celula[(p.get("caso", "").strip(), (p.get("subcategoria") or "").strip())].append(p)

    celulas = list(csv.DictReader(celulas_path.open(encoding="utf-8")))
    campos = list(celulas[0].keys()) if celulas else []
    for c in COLS_CONTAGEM:
        if c not in campos:
            campos.append(c)

    preenchidas = pendentes = 0
    print(f"{len(vistos)} pares codificados, em {len(por_celula)} células com pares\n")
    print(f"{'caso':5s} {'cod':5s} {'subcategoria':46s} {'nivel':12s} pares  estr  sup  fp  ind")
    for linha in celulas:
        chave = (linha.get("caso", "").strip(), (linha.get("nome_subcategoria") or "").strip())
        res = agregar(por_celula.get(chave, []))
        for k, v in res.items():
            linha[k] = v
        if res["nivel"]:
            preenchidas += 1
        else:
            pendentes += 1
        print(f"{linha.get('caso',''):5s} {linha.get('codigo_subcategoria',''):5s} "
              f"{chave[1][:46]:46s} {res['nivel'] or '(pendente)':12s} "
              f"{res['n_pares']:5d} {res['n_pares_estrutural']:5d} "
              f"{res['n_pares_superficial']:4d} {res['n_pares_falso_positivo']:3d} "
              f"{res['n_pares_indeterminado']:4d}")

    print(f"\n{preenchidas} células decididas, {pendentes} pendentes de {len(celulas)}")

    if args.so_ver:
        print("\n(--so-ver: nada foi gravado)")
        return
    with celulas_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(celulas)
    print(f"gravado: {celulas_path}")


if __name__ == "__main__":
    main()
