"""
Tabela 4: cruza o nível discursivo com o nível normativo, por subcategoria e
caso, e classifica cada célula nas nove posições possíveis.

Não há julgamento aqui: é cálculo sobre as duas tabelas já codificadas. Quatro
das nove posições interessam à hipótese, conforme a seção 4.5.

    python3 coding/tabela4_divergencia.py --escopo com-dea
"""
from __future__ import annotations
import argparse, csv, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
COD = BASE / "coding"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

NIVEIS = ["ausente", "superficial", "estrutural"]
NOME = {
    ("estrutural", "ausente"): "retórica sem arquitetura",
    ("ausente", "estrutural"): "arquitetura sem retórica",
    ("estrutural", "estrutural"): "coerência",
    ("ausente", "ausente"): "ausência em ambos",
}


def posicao(disc: str, norm: str, tem_lexico: bool = True) -> str:
    """Distingue três ausências de posição, que não são a mesma coisa:
    sem léxico no sistema (a célula não existe no desenho), célula ainda não
    codificada, e combinação sem denominação própria."""
    if not tem_lexico:
        return "não aplicável (sem léxico no sistema)"
    if not disc or not norm:
        return "(pendente)"
    return NOME.get((disc, norm), f"{disc} / {norm}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escopo", default="com-dea")
    a = ap.parse_args()

    pd_, pn = COD / "eixo_discursivo.csv", COD / f"eixo_normativo_{a.escopo}.csv"
    for p in (pd_, pn):
        if not p.exists():
            raise SystemExit(f"não encontrei {p}. Rode os dois agregadores antes.")

    disc = {(r["caso"], r["nome_subcategoria"]): r
            for r in csv.DictReader(pd_.open(encoding="utf-8"))}
    norm = {(r["caso"], r["subcategoria"]): r
            for r in csv.DictReader(pn.open(encoding="utf-8"))}

    linhas, pend = [], 0
    for ch in sorted(set(disc) | set(norm)):
        d = (disc.get(ch, {}).get("nivel") or "").strip().lower()
        n = (norm.get(ch, {}).get("nivel") or "").strip().lower()
        # a célula sem entrada no eixo discursivo é a que não tem termo no
        # léxico daquele sistema: é resultado do desenho, não pendência
        pos = posicao(d, n, tem_lexico=ch in disc)
        pend += pos == "(pendente)"
        linhas.append({
            "caso": ch[0],
            "codigo": (disc.get(ch) or norm.get(ch, {})).get("codigo_subcategoria")
                      or norm.get(ch, {}).get("codigo", ""),
            "subcategoria": ch[1],
            "nivel_discursivo": d or ("não aplicável" if ch not in disc else "(pendente)"),
            "nivel_normativo": n or "(pendente)",
            "posicao": pos,
            "mecanismo_tipo": norm.get(ch, {}).get("mecanismo_tipo", ""),
            "evidencia_discursiva": (disc.get(ch, {}).get("evidencia_verbatim") or "")[:200],
            "evidencia_normativa": (norm.get(ch, {}).get("evidencia_verbatim") or "")[:200],
        })

    p = COD / f"tabela4_divergencia_{a.escopo}.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader(); w.writerows(linhas)

    print(f"{'caso':5s} {'cod':5s} {'subcategoria':42s} {'discursivo':12s} {'normativo':12s} posição")
    for r in linhas:
        print(f"{r['caso']:5s} {r['codigo']:5s} {r['subcategoria'][:42]:42s} "
              f"{r['nivel_discursivo']:12s} {r['nivel_normativo']:12s} {r['posicao']}")

    print(f"\n{len(linhas) - pend} de {len(linhas)} células classificadas"
          f" ({sum(1 for r in linhas if r['posicao'].startswith('não aplicável'))} não aplicáveis)")
    print("\nposições que interessam à hipótese:")
    for k in ("retórica sem arquitetura", "arquitetura sem retórica", "coerência", "ausência em ambos"):
        qs = [r for r in linhas if r["posicao"] == k]
        print(f"   {len(qs):3d}  {k}")
        for r in qs:
            print(f"        {r['caso']} {r['codigo']} {r['subcategoria']}")
    print(f"\ngravado: {p}")


if __name__ == "__main__":
    main()
