"""
Resultados que não dependem de julgamento: cobertura lexical, frequência por
termo, termos sem ocorrência, diferença entre as duas passadas, linha do tempo
das subcategorias e cruzamento por modalidade de fala.

Lê apenas arquivos já existentes e grava tudo em resultados/. Não altera nada do
corpus nem das planilhas de codificação. Idempotente: pode rodar quantas vezes
quiser.

    python3 analise_lexical.py

Decisões de representação, para o caso de alguém conferir:
  - Subcategoria sem termo no léxico de um sistema NÃO é plotada como zero. Ela
    recebe a marca "sem léxico", porque ausência de instrumento e ausência de
    menção são coisas diferentes e confundi-las inverte a leitura da tabela.
  - As duas séries levam cor, hachura e rótulo numérico. A cor sozinha não
    carrega identidade, para a figura continuar legível impressa em preto e
    branco e para leitores com visão de cores atípica.
  - Duas medidas de escalas diferentes nunca compartilham eixo: unidades e
    ocorrências saem em figuras separadas.
"""

from __future__ import annotations

import base64
import csv
import html
import io
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import datetime as dt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

BASE = Path(__file__).resolve().parent

import recorte
SAIDA = BASE / "resultados"

CASOS = {
    "FUST": {"sistema": "BR", "raiz": BASE / "corpus_fust"},
    "BEAD": {"sistema": "US", "raiz": BASE / "corpus_bead"},
}
TERMOS = BASE / "fust" / "matriz" / "termos.csv"
MATRIZ_FUST = BASE / "fust" / "matriz" / "arguments_matrix_fust.csv"

# paleta validada contra a superfície clara: separação CVD 26,1 e visão normal
# 33,4, ambas acima do piso, e contraste acima de 3:1 para as duas séries.
COR = {"FUST": "#2a78d6", "BEAD": "#C8102E"}
HACHURA = {"FUST": "", "BEAD": "///"}
TINTA, TINTA2, SUPERFICIE = "#0b0b0b", "#52514e", "#fcfcfb"
MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun",
            "jul", "ago", "set", "out", "nov", "dez"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    "axes.edgecolor": "#d8d7d2", "axes.labelcolor": TINTA,
    "text.color": TINTA, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#ebeae5", "grid.linewidth": 0.6,
    "savefig.bbox": "tight", "savefig.dpi": 200,
})


def ler(p: Path) -> list[dict]:
    if not p.exists():
        raise SystemExit(f"não encontrei {p}")
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar(nome: str, colunas: list[str], linhas: list[dict]) -> Path:
    p = SAIDA / nome
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        w.writerows(linhas)
    return p


def png_embutido(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- carregamento

def carregar():
    termos = ler(TERMOS)
    lex = defaultdict(set)                       # (codigo, sistema) -> termos
    nomes, categorias = {}, {}
    for t in termos:
        cod, sis = t["codigo"].strip(), t["sistema"].strip().upper()
        lex[(cod, sis)].add(t["termo"].strip())
        nomes[cod] = t["subcategoria"].strip()
        categorias[cod] = t["categoria"].strip()

    dados = {}
    for caso, cfg in CASOS.items():
        occ = ler(cfg["raiz"] / "lexico_ocorrencias.csv")
        idx = {r["id"]: r for r in ler(cfg["raiz"] / "corpus_index.csv")}
        idx = {k: v for k, v in idx.items() if recorte.manter(caso, k)}
        occ = [o for o in occ if o["id"] in idx]
        dados[caso] = {"occ": occ, "idx": idx, "sistema": cfg["sistema"]}
    return lex, nomes, categorias, dados


# -------------------------------------------------------------------- tabela 1

def tabela_cobertura(lex, nomes, categorias, dados):
    codigos = sorted(nomes, key=lambda c: [int(x) for x in c.split(".")])
    linhas = []
    for cod in codigos:
        linha = {"codigo": cod, "categoria": categorias[cod], "subcategoria": nomes[cod]}
        for caso in CASOS:
            sis = dados[caso]["sistema"]
            termos_do_caso = lex.get((cod, sis), set())
            occ = [o for o in dados[caso]["occ"] if o["codigo"].strip() == cod]
            linha[f"{caso}_termos_no_lexico"] = len(termos_do_caso)
            if not termos_do_caso:
                linha[f"{caso}_unidades"] = ""
                linha[f"{caso}_ocorrencias"] = ""
                linha[f"{caso}_situacao"] = "sem léxico"
            else:
                linha[f"{caso}_unidades"] = len({o["id"] for o in occ})
                linha[f"{caso}_ocorrencias"] = len(occ)
                linha[f"{caso}_situacao"] = "com ocorrência" if occ else "sem ocorrência"
        linhas.append(linha)
    cols = ["codigo", "categoria", "subcategoria"]
    for caso in CASOS:
        cols += [f"{caso}_termos_no_lexico", f"{caso}_unidades",
                 f"{caso}_ocorrencias", f"{caso}_situacao"]
    return cols, linhas


# ------------------------------------------------------- termos e passadas

def tabela_termos(lex, nomes, dados):
    linhas = []
    for caso in CASOS:
        sis = dados[caso]["sistema"]
        cont = Counter(o["termo_da_lista"].strip() for o in dados[caso]["occ"])
        for (cod, s), termos in sorted(lex.items()):
            if s != sis:
                continue
            for termo in sorted(termos):
                linhas.append({"caso": caso, "codigo": cod, "subcategoria": nomes[cod],
                               "termo": termo, "ocorrencias": cont.get(termo, 0)})
    return ["caso", "codigo", "subcategoria", "termo", "ocorrencias"], linhas


def tabela_passadas(nomes, dados):
    linhas = []
    for caso in CASOS:
        c = Counter((o["codigo"].strip(), o["passada"].strip()) for o in dados[caso]["occ"])
        codigos = sorted({k[0] for k in c}, key=lambda x: [int(i) for i in x.split(".")])
        for cod in codigos:
            e, t = c.get((cod, "estrita"), 0), c.get((cod, "tolerante"), 0)
            linhas.append({"caso": caso, "codigo": cod, "subcategoria": nomes.get(cod, cod),
                           "estrita": e, "tolerante": t, "total": e + t,
                           "pct_tolerante": round(100 * t / (e + t), 1) if e + t else 0.0})
    return ["caso", "codigo", "subcategoria", "estrita", "tolerante",
            "total", "pct_tolerante"], linhas


def tabela_modalidade(nomes, dados):
    if not MATRIZ_FUST.exists():
        return None, []
    mat = {r["id"]: r for r in ler(MATRIZ_FUST)}

    def normalizar(u: str) -> str:
        u = (u or "").strip().lower()
        if not u:
            return "sem modalidade declarada"
        return {"pela ardem": "pela ordem"}.get(u, u)

    c = Counter()
    for o in dados["FUST"]["occ"]:
        mod = normalizar(mat.get(o["id"], {}).get("unit", ""))
        c[(o["codigo"].strip(), mod)] += 1
    mods = sorted({k[1] for k in c})
    codigos = sorted({k[0] for k in c}, key=lambda x: [int(i) for i in x.split(".")])
    linhas = []
    for cod in codigos:
        linha = {"codigo": cod, "subcategoria": nomes.get(cod, cod)}
        for m in mods:
            linha[m] = c.get((cod, m), 0)
        linha["total"] = sum(c.get((cod, m), 0) for m in mods)
        linhas.append(linha)
    return ["codigo", "subcategoria"] + mods + ["total"], linhas


# -------------------------------------------------------------------- figuras

def fig_cobertura(cols, linhas, medida: str, titulo: str, rotulo_x: str):
    """Barras pareadas horizontais. Célula sem léxico recebe marca, não zero."""
    vis = list(reversed(linhas))
    y = range(len(vis))
    alt = 0.38
    fig, ax = plt.subplots(figsize=(8.2, 0.42 * len(vis) + 1.5))
    for i, caso in enumerate(CASOS):
        desloc = (0.5 - i) * alt * 1.06          # folga entre as barras do par
        vals = [(int(r[f"{caso}_{medida}"]) if str(r[f"{caso}_{medida}"]).strip() != "" else 0)
                for r in vis]
        ax.barh([v + desloc for v in y], vals, height=alt, color=COR[caso],
                hatch=HACHURA[caso], edgecolor=SUPERFICIE, linewidth=1.2,
                label=caso, zorder=3)
        for yy, (v, r) in enumerate(zip(vals, vis)):
            if str(r[f"{caso}_{medida}"]).strip() == "":
                ax.text(0.6, yy + desloc, "sem léxico", va="center", ha="left",
                        fontsize=7.2, style="italic", color=TINTA2, zorder=4)
            elif v:
                ax.text(v + max(vals) * 0.012, yy + desloc, f"{v}", va="center",
                        ha="left", fontsize=7.4, color=TINTA2, zorder=4)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{r['codigo']} {r['subcategoria']}" for r in vis], fontsize=8)
    ax.set_xlabel(rotulo_x)
    ax.set_title(titulo, fontsize=10.5, loc="left", pad=12)
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[Patch(facecolor=COR[c], hatch=HACHURA[c],
                             edgecolor=SUPERFICIE, label=c) for c in CASOS],
              loc="lower right", frameon=False, fontsize=8.5)
    ax.margins(x=0.12)
    fig.tight_layout()
    return fig


def fig_linha_do_tempo(nomes, dados, caso="FUST", marco=None, subtitulo=""):
    """Quando cada subcategoria aparece ao longo do tempo, para um caso.

    `marco` é um par (data ISO, rótulo) desenhado como linha vertical: serve
    para separar o período anterior à promulgação do posterior.
    """
    occ, idx = dados[caso]["occ"], dados[caso]["idx"]
    c = Counter()
    for o in occ:
        rec = idx.get(o["id"], {})
        # o índice brasileiro usa "data" e o norte-americano "date"
        data = (rec.get("data") or rec.get("date") or "").strip()[:10]
        if data:
            c[(data, o["codigo"].strip())] += 1
    if not c:
        return None
    codigos = sorted({k[1] for k in c}, key=lambda x: [int(i) for i in x.split(".")])
    fig, ax = plt.subplots(figsize=(10.5, 0.42 * len(codigos) + 1.8))
    maxn = max(c.values())
    for j, cod in enumerate(reversed(codigos)):
        pares = [(dt.date.fromisoformat(d), c[(d, cod)]) for (d, k) in c if k == cod]
        if not pares:
            continue
        xs, ns = zip(*pares)
        ax.scatter(xs, [j] * len(xs), s=[26 + 230 * (n / maxn) for n in ns],
                   color=COR[caso], alpha=0.72, edgecolor=SUPERFICIE,
                   linewidth=0.8, zorder=3)
    ax.set_yticks(range(len(codigos)))
    ax.set_yticklabels([f"{k} {nomes.get(k, k)}" for k in reversed(codigos)], fontsize=8)
    # eixo de tempo verdadeiro: a distância horizontal é tempo decorrido
    # a marcação acompanha a amplitude: mês a mês numa tramitação de meses,
    # semestral ou anual num corpus de anos, para o eixo continuar legível
    todas = [d for (d, _k) in c]
    amplitude = (dt.date.fromisoformat(max(todas)) - dt.date.fromisoformat(min(todas))).days
    if amplitude <= 730:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        rotulo = lambda x: "{}/{}".format(MESES_PT[mdates.num2date(x).month - 1],
                                          mdates.num2date(x).year)
    elif amplitude <= 2200:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
        rotulo = lambda x: "{}/{}".format(MESES_PT[mdates.num2date(x).month - 1],
                                          mdates.num2date(x).year)
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator())
        rotulo = lambda x: str(mdates.num2date(x).year)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _pos: rotulo(x)))
    for r in ax.get_xticklabels():
        r.set_rotation(45); r.set_horizontalalignment("right"); r.set_fontsize(7.5)
    if marco:
        x = dt.date.fromisoformat(marco[0])
        ax.axvline(x, color=TINTA2, linewidth=1.2, linestyle="--", zorder=2)
        ax.annotate(marco[1], xy=(x, len(codigos) - 0.3), xytext=(6, 0),
                    textcoords="offset points", fontsize=7.6, color=TINTA2,
                    va="top", ha="left")
    ax.set_xlabel("data da sessão")
    ax.set_title(subtitulo or "Quando cada subcategoria é invocada na tramitação do FUST\n"
                 "área do ponto proporcional ao número de ocorrências na sessão",
                 fontsize=10.5, loc="left", pad=12)
    ax.grid(axis="y", visible=False)
    ax.margins(x=0.02)
    fig.tight_layout()
    return fig


# -------------------------------------------------------------------- relatório

def tabela_html(cols, linhas, titulo, nota=""):
    th = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    tr = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in cols) + "</tr>"
        for r in linhas)
    n = f"<p class='nota'>{html.escape(nota)}</p>" if nota else ""
    return (f"<section><h2>{html.escape(titulo)}</h2>{n}"
            f"<div class='rolagem'><table><thead><tr>{th}</tr></thead>"
            f"<tbody>{tr}</tbody></table></div></section>")


def main():
    SAIDA.mkdir(exist_ok=True)
    lex, nomes, categorias, dados = carregar()

    cols1, lin1 = tabela_cobertura(lex, nomes, categorias, dados)
    cols2, lin2 = tabela_termos(lex, nomes, dados)
    cols3, lin3 = tabela_passadas(nomes, dados)
    cols4, lin4 = tabela_modalidade(nomes, dados)
    mortos = [r for r in lin2 if r["ocorrencias"] == 0]

    gravar("tabela1_cobertura.csv", cols1, lin1)
    gravar("tabela_frequencia_termos.csv", cols2, lin2)
    gravar("termos_sem_ocorrencia.csv", cols2, mortos)
    gravar("tabela_passadas.csv", cols3, lin3)
    if cols4:
        gravar("tabela_modalidade_fust.csv", cols4, lin4)

    figs = []
    f1 = fig_cobertura(cols1, lin1, "unidades",
                       "Unidades em que cada subcategoria é invocada",
                       "unidades documentais")
    f1.savefig(SAIDA / "figura_4_cobertura_unidades.png")
    f1.savefig(SAIDA / "figura_4_cobertura_unidades.svg")
    figs.append(("Cobertura por unidades", png_embutido(f1)))

    f2 = fig_cobertura(cols1, lin1, "ocorrencias",
                       "Ocorrências de termos por subcategoria", "ocorrências de termos")
    f2.savefig(SAIDA / "figura_5_ocorrencias_por_subcategoria.png")
    f2.savefig(SAIDA / "figura_5_ocorrencias_por_subcategoria.svg")
    figs.append(("Cobertura por ocorrências", png_embutido(f2)))

    f3 = fig_linha_do_tempo(nomes, dados, "FUST")
    if f3:
        f3.savefig(SAIDA / "figura_6_linha_do_tempo_fust.png")
        f3.savefig(SAIDA / "figura_6_linha_do_tempo_fust.svg")
        figs.append(("Linha do tempo, FUST", png_embutido(f3)))

    f5 = fig_linha_do_tempo(
        nomes, dados, "BEAD", marco=("2021-11-15", "promulgação da IIJA"),
        subtitulo="Quando cada subcategoria é invocada nas audiências do BEAD\n"
                  "área do ponto proporcional ao número de ocorrências na audiência")
    if f5:
        f5.savefig(SAIDA / "figura_7_linha_do_tempo_bead.png")
        f5.savefig(SAIDA / "figura_7_linha_do_tempo_bead.svg")
        figs.append(("Linha do tempo, BEAD", png_embutido(f5)))

    tot = {c: (sum(1 for r in lin3 if r["caso"] == c),
               sum(r["estrita"] for r in lin3 if r["caso"] == c),
               sum(r["tolerante"] for r in lin3 if r["caso"] == c)) for c in CASOS}
    resumo = "".join(
        f"<li><b>{c}</b>: {tot[c][1]} ocorrências na passada estrita, "
        f"{tot[c][2]} acrescentadas pela tolerante "
        f"({100 * tot[c][2] / max(1, tot[c][1] + tot[c][2]):.1f}% do total)</li>"
        for c in CASOS)

    corpo = [
        f"<h1>Resultados lexicais — FUST e BEAD</h1>",
        f"<p class='nota'>Gerado por <code>analise_lexical.py</code>. "
        f"Nenhum número desta página foi digitado à mão: todos saem dos arquivos "
        f"do corpus e da lista de termos, e a página é refeita a cada execução.</p>",
        f"<section><h2>Passadas de busca</h2><ul>{resumo}</ul></section>",
    ]
    for titulo, b64 in figs:
        corpo.append(f"<section><h2>{html.escape(titulo)}</h2>"
                     f"<img src='data:image/png;base64,{b64}' alt='{html.escape(titulo)}'></section>")
    corpo.append(tabela_html(cols1, lin1, "Tabela 1 — Cobertura lexical",
                             "Célula marcada 'sem léxico' significa que o sistema não tem termo "
                             "para a subcategoria: é resultado, não lacuna do instrumento."))
    corpo.append(tabela_html(cols3, lin3, "Diferença entre as duas passadas"))
    if cols4:
        corpo.append(tabela_html(cols4, lin4, "Ocorrências por modalidade de fala, FUST",
                                 "'sem modalidade declarada' é categoria do registro: a ata não "
                                 "qualifica a fala. 'pela ardem' foi normalizada para 'pela ordem'."))
    corpo.append(tabela_html(cols2, mortos, f"Termos sem nenhuma ocorrência ({len(mortos)})"))

    estilo = """
    :root{--s:#fcfcfb;--t:#0b0b0b;--t2:#52514e;--b:#ebeae5}
    *{box-sizing:border-box}
    body{margin:0;padding:32px 24px 72px;background:var(--s);color:var(--t);
      font:15px/1.6 'DejaVu Sans',system-ui,sans-serif;max-width:1100px;margin-inline:auto}
    h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.1rem;margin:36px 0 10px}
    .nota{color:var(--t2);font-size:.86rem;margin:4px 0 0}
    img{max-width:100%;height:auto;display:block;margin:8px 0}
    .rolagem{overflow-x:auto;border:1px solid var(--b);border-radius:8px}
    table{border-collapse:collapse;width:100%;font-size:.8rem}
    th,td{padding:6px 9px;text-align:left;border-bottom:1px solid var(--b);white-space:nowrap}
    th{background:#f4f3ef;font-weight:600;position:sticky;top:0}
    tbody tr:hover{background:#f7f6f2}
    code{background:#f2f1ec;padding:1px 4px;border-radius:3px;font-size:.85em}
    @media print{body{padding:0}.rolagem{overflow:visible;border:0}th{position:static}}
    """
    (SAIDA / "relatorio_lexical.html").write_text(
        f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Resultados lexicais</title><style>{estilo}</style></head>"
        f"<body>{''.join(corpo)}</body></html>", encoding="utf-8")

    print(f"gravado em {SAIDA}:")
    for p in sorted(SAIDA.iterdir()):
        print(f"   {p.name}")
    print(f"\n{len(lin1)} subcategorias | {len(lin2)} termos no léxico | "
          f"{len(mortos)} sem nenhuma ocorrência")


if __name__ == "__main__":
    main()
