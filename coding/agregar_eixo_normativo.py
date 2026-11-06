"""
Agrega os dispositivos codificados ao nível da subcategoria por caso, pela regra
do nível mais alto alcançado, dentro do ESCOPO escolhido.

O escopo é parâmetro: a mesma codificação produz resultados diferentes conforme
o que se conta como texto aprovado, e essa escolha é da pesquisadora.

    python3 coding/agregar_eixo_normativo.py --escopo estreito
    python3 coding/agregar_eixo_normativo.py --escopo com-dea
    python3 coding/agregar_eixo_normativo.py --escopo amplo
    python3 coding/agregar_eixo_normativo.py --comparar     # os três lado a lado
"""
from __future__ import annotations
import argparse, csv, sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
COD = BASE / "coding"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# O glossário do Título 47 saiu dos escopos: as suas definições já constam da
# SEC. 60302, dentro do Digital Equity Act operativo, e contá-las duas vezes
# inflaria o lado norte-americano com o mesmo conteúdo.
ESCOPOS = {
    "estreito": {"Lei 9.998/2000", "IIJA SEC. 60102"},
    "com-dea": {"Lei 9.998/2000", "IIJA SEC. 60102", "IIJA Digital Equity Act"},
    "amplo": {"Lei 9.998/2000", "Lei 9.472/1997, arts. 79-81",
              "IIJA SEC. 60102", "IIJA Digital Equity Act", "IIJA Division F"},
}


def agregar(disps, diplomas):
    no_escopo = [d for d in disps if d["diploma"] in diplomas]
    pert = [d for d in no_escopo if d.get("pertinencia", "").strip().lower() == "sim"]
    est = [d for d in pert if d.get("nivel_do_dispositivo", "").strip().lower() == "estrutural"]
    sup = [d for d in pert if d.get("nivel_do_dispositivo", "").strip().lower() == "superficial"]
    ind = [d for d in no_escopo if d.get("nivel_do_dispositivo", "").strip().lower() == "indeterminado"]
    if est:
        nivel, fonte = "estrutural", est[0]
    elif sup:
        nivel, fonte = "superficial", sup[0]
    elif pert:
        nivel, fonte = "", None
    else:
        nivel, fonte = "ausente", None
    # A coluna de mecanismo informa o mecanismo VINCULANTE instituído, que é
    # como o texto a lê. O campo mecanismo_tipo do dispositivo guarda o formato
    # da cláusula, e uma cláusula de definição pode ter formato de critério de
    # elegibilidade sem obrigar (vinculante = não), caso em que a célula é
    # superficial. Emitir o formato ali faria o quadro contradizer a regra de
    # 3.3, então a célula superficial declara "nenhum".
    mecanismo = (fonte or {}).get("mecanismo_tipo", "") if nivel == "estrutural" else (
        "nenhum" if nivel == "superficial" else "")
    return {"nivel": nivel,
            "mecanismo_tipo": mecanismo,
            "diploma_evidencia": (fonte or {}).get("diploma", ""),
            "evidencia_verbatim": (fonte or {}).get("trecho_evidencia", ""),
            "n_dispositivos": len(no_escopo), "n_estrutural": len(est),
            "n_superficial": len(sup), "n_indeterminado": len(ind)}


def carregar():
    p = COD / "dispositivos_eixo_normativo.csv"
    if not p.exists():
        raise SystemExit(f"não encontrei {p} — a codificação do eixo normativo ainda não começou")
    por = defaultdict(list)
    for d in csv.DictReader(p.open(encoding="utf-8")):
        por[(d.get("caso", "").strip(), (d.get("subcategoria") or "").strip())].append(d)
    cob = list(csv.DictReader((COD / "normativo_cobertura.csv").open(encoding="utf-8")))
    return por, cob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escopo", choices=sorted(ESCOPOS), default="estreito")
    ap.add_argument("--comparar", action="store_true")
    ap.add_argument("--so-ver", action="store_true")
    a = ap.parse_args()
    por, cob = carregar()

    if a.comparar:
        print(f"{'caso':5s} {'cod':5s} {'subcategoria':44s} " +
              " ".join(f"{e:>12s}" for e in ESCOPOS))
        for c in cob:
            ch = (c["caso"], c["subcategoria"])
            vals = [agregar(por.get(ch, []), ESCOPOS[e])["nivel"] or "(pendente)" for e in ESCOPOS]
            print(f"{c['caso']:5s} {c['codigo']:5s} {c['subcategoria'][:44]:44s} " +
                  " ".join(f"{v:>12s}" for v in vals))
        return

    dip = ESCOPOS[a.escopo]
    linhas, dec = [], 0
    print(f"escopo '{a.escopo}': {', '.join(sorted(dip))}\n")
    print(f"{'caso':5s} {'cod':5s} {'subcategoria':44s} {'nivel':12s} disp estr sup ind")
    for c in cob:
        r = agregar(por.get((c["caso"], c["subcategoria"]), []), dip)
        linha = {**{k: c[k] for k in ("caso", "codigo", "subcategoria")}, **r, "escopo": a.escopo}
        linhas.append(linha)
        dec += bool(r["nivel"])
        print(f"{c['caso']:5s} {c['codigo']:5s} {c['subcategoria'][:44]:44s} "
              f"{r['nivel'] or '(pendente)':12s} {r['n_dispositivos']:4d} {r['n_estrutural']:4d} "
              f"{r['n_superficial']:3d} {r['n_indeterminado']:3d}")
    print(f"\n{dec} de {len(cob)} células decididas")
    if a.so_ver:
        return
    p = COD / f"eixo_normativo_{a.escopo}.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader(); w.writerows(linhas)
    print(f"gravado: {p}")


if __name__ == "__main__":
    main()
