#!/usr/bin/env python3
"""
Matriz de argumentos do corpus FUST — espelha `arguments_matrix.xlsx` do
projeto BEAD (~/bead-witnesses/), mesma aba "matrix", mesmas convenções de
`text_status`/`needs_review`. Unidade: uma linha por FALA, não por pessoa
por sessão — o equivalente direto do "um documento de depoimento" do BEAD,
onde o mesmo par testemunha/audiência se repete várias vezes.

As 5 colunas de codificação (problem_framing, main_arguments,
specific_asks, position, verbatim_quote) saem VAZIAS -- são o passo
seguinte, de leitura humana do texto. Este script produz só o arcabouço:
identificação, origem e rastreabilidade.

Fontes:
  1. corpus_fust/senado/pronunciamentos/indice.csv (364 pronunciamentos,
     coletados por palavra-chave, API do Senado).
  2. fust/segmentar_oradores.py::segmentar_corpo, rodado sobre os 3
     Diários que metodologia_validacao_segmentacao.md confirmou terem
     debate com orador nomeado: DCD08DEZ1999 (p. 60552-60574),
     DCD27OUT1999 (p. 51004-51006, recortado por âncora de texto) e
     DSF-202-54 (p. 35110-35114, excluindo 35108-35109, que são
     inteiramente sobre outra matéria, a Lei Kandir).

O ponto crítico é `orador_id`: o mesmo deputado/senador aparece com grafia
diferente a cada fala (ruído de OCR), então a chave tem que normalizar
acento/caixa e resolver variante próxima contra o rol de parlamentares da
legislatura (`corpus_fust/camara/roster/` e `corpus_fust/senado/roster/`,
baixados da API). Resolução duvidosa vira `needs_review=True`, nunca um
`orador_id` silenciosamente errado.

    python construir_matriz.py            # mostra a prévia, não grava
    python construir_matriz.py --gravar   # grava .csv e .xlsx

Depende de `openpyxl` para o .xlsx (único módulo fora da stdlib usado
aqui -- é o que o BEAD também usa por baixo do pandas, e escrever .xlsx
cru em stdlib não compensa para um script de uso único).
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
SAIDA_DIR = RAIZ / "fust" / "matriz"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import segmentar_oradores as so  # noqa: E402

COLUNAS = [
    "id", "orador_id", "orador_bruto", "partido_uf",
    "actor_type", "sessao_id", "sessao", "data",
    "casa", "unit", "ordem",
    "problem_framing", "main_arguments", "specific_asks",
    "position", "verbatim_quote",
    "source", "text_status", "corpus_file",
    "offset", "needs_review",
]
COLUNAS_VAZIAS = ["problem_framing", "main_arguments", "specific_asks",
                   "position", "verbatim_quote"]

UFS_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}
PARTIDOS_CONHECIDOS = {
    "PT", "PFL", "PMDB", "PSDB", "PPB", "PDT", "PTB", "PL", "PPS", "PSB",
    "PCDOB", "PV", "PSC", "PSL", "PST", "PMN", "PSD", "PRN", "PTN", "PSN",
    "PAN", "PSDC", "PRONA", "PGT", "PTDOB",
}


def limpar_quebra_ocr(texto: str) -> str:
    """Junta palavra cortada por hifenização de quebra de linha
    ("Maga-\\nlhães" -> "Magalhães") antes de colapsar o resto do espaço em
    branco (quebra de linha SEM hífen vira espaço simples). Sem isso,
    "pela\\nordem" não bate contra o padrão "pela ordem" em extrair_unit,
    e "Antonio Carlos Maga-\\nlhães" perde o sobrenome em nome_presidencia."""
    texto = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar(s: str) -> str:
    """Acento fora, caixa alta, só letras/número/espaço, espaço colapsado."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --------------------------------------------------------------------------
# Rol de parlamentares (resolução de orador_id)
# --------------------------------------------------------------------------


@dataclass
class Candidato:
    orador_id: str
    nome: str
    partido: str
    uf: str


def carregar_roster_camara() -> list[Candidato]:
    caminho = CORPUS / "camara" / "roster" / "deputados_legislatura51.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))["dados"]
    return [
        Candidato(orador_id=f"CAM-{d['id']}", nome=d["nome"],
                  partido=d.get("siglaPartido") or "", uf=d.get("siglaUf") or "")
        for d in dados
    ]


def carregar_roster_senado() -> list[Candidato]:
    caminho = CORPUS / "senado" / "roster" / "senadores_legislatura51.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))["dados"]
    cands = []
    for d in dados:
        ident = d["IdentificacaoParlamentar"]
        uf = ""
        mandatos = d.get("Mandatos", {}).get("Mandato", [])
        if mandatos:
            uf = mandatos[0].get("UfParlamentar", "")
        cands.append(Candidato(
            orador_id=f"SEN-{ident['CodigoParlamentar']}",
            nome=ident["NomeParlamentar"],
            partido=ident.get("SiglaPartidoParlamentar") or "",
            uf=uf,
        ))
    return cands


def resolver_orador(nome_bruto: str, candidatos: list[Candidato]) -> tuple[str, str, bool]:
    """devolve (orador_id, nome_resolvido, needs_review)."""
    alvo = normalizar(nome_bruto)
    if not alvo:
        return "SEMRESOLVER-VAZIO", nome_bruto, True

    exatos = [c for c in candidatos if normalizar(c.nome) == alvo]
    if len(exatos) == 1:
        return exatos[0].orador_id, exatos[0].nome, False
    if len(exatos) > 1:
        # homônimo de verdade dentro do rol -- usa o primeiro, mas sinaliza
        return exatos[0].orador_id, exatos[0].nome, True

    nomes_norm = [normalizar(c.nome) for c in candidatos]
    proximos = difflib.get_close_matches(alvo, nomes_norm, n=1, cutoff=0.82)
    if proximos:
        for c, n in zip(candidatos, nomes_norm):
            if n == proximos[0]:
                return c.orador_id, c.nome, True

    # nada no rol bate nem de perto -- chave própria, sempre sinalizada
    return f"SEMRESOLVER-{alvo.replace(' ', '-')}", nome_bruto, True


# --------------------------------------------------------------------------
# Partido/UF e unit, a partir do parêntese do marcador
# --------------------------------------------------------------------------

_RE_PARTIDO_UF = re.compile(r"^([A-Za-zÇç/]{2,20}?)\s*[-–—:']+\s*([A-Za-z]{2})\b")
_RE_REVISAO = re.compile(r"(sem|com)\s+revis[aã]o d[ao] orador", re.I)

_UNIT_PATTERNS = [
    (re.compile(r"pela ordem|questão de ordem", re.I), "pela ordem"),
    (re.compile(r"encaminh", re.I), "encaminhamento"),
    (re.compile(r"orienta[cç][aã]o|como l[ií]der", re.I), "orientação de bancada"),
    (re.compile(r"\baparte", re.I), "aparte"),
    (re.compile(r"parecer", re.I), "parecer"),
    (re.compile(r"comunica[cç][aã]o inadi[aá]vel", re.I), "comunicação inadiável"),
    (re.compile(r"pronuncia o seguinte discurso", re.I), "discurso"),
]


def extrair_partido_uf(parenteses: str) -> tuple[str, bool]:
    """devolve (partido_uf, suspeito) a partir do parêntese bruto do marcador."""
    if not parenteses:
        return "", False
    primeira_clausula = re.split(r"\.\s*", parenteses, maxsplit=1)[0]
    m = _RE_PARTIDO_UF.search(primeira_clausula)
    if not m:
        return "", True
    partido = re.sub(r"\s+", "", m.group(1))
    uf = m.group(2).upper()
    suspeito = (uf not in UFS_VALIDAS) or (partido.upper().replace("BLOCO/", "") not in PARTIDOS_CONHECIDOS
                                           and "/" not in partido)
    return f"{partido}-{uf}", suspeito


def extrair_unit(texto_modalidade: str) -> str:
    """`texto_modalidade` já é só as cláusulas depois do partido-UF (ou,
    pro Senado vindo do indice.csv, o campo `unit` inteiro, cru)."""
    texto_modalidade = limpar_quebra_ocr(texto_modalidade)
    clausulas = [c.strip() for c in re.split(r"\.\s*", texto_modalidade) if c.strip()]
    clausulas = [c for c in clausulas if not _RE_REVISAO.search(c)]
    if not clausulas:
        return ""
    bruto = clausulas[0]
    for pat, label in _UNIT_PATTERNS:
        if pat.search(bruto):
            return label
    return bruto.lower()


def unit_do_marcador_camara(parenteses: str) -> str:
    """Não corta no primeiro ponto do texto -- achado construindo a
    matriz: o OCR às vezes engole o ponto depois da UF ("PT — SP Pela
    ordem. Sem revisão do orador.", sem ponto depois de "SP"), e um corte
    ingênuo por "." pega "PT — SP Pela ordem" inteiro como se fosse só o
    partido-UF, jogando fora a modalidade junto. Em vez disso, acha onde o
    próprio regex de partido-UF termina de casar, e usa tudo que vem
    depois disso -- não importa se tem ponto ali ou não."""
    m = _RE_PARTIDO_UF.search(parenteses)
    resto = parenteses[m.end():] if m else parenteses
    return extrair_unit(resto)


def nome_presidencia(bruto: str) -> tuple[str, bool]:
    """O parêntese da Presidência é só um nome curto -- "(Michel Temer)".
    Achado construindo a matriz: quando o OCR engole o ")" de fechamento
    (ex. "(Michel Temer — Tem V. Exa.\\na palavra.\\n\\nO SR. SILAS CÂMARA
    (PTB - AM...."), o `[^)]*` do regex do marcador vira guloso até achar o
    PRÓXIMO ")" de verdade, várias linhas depois, e o "nome" sai um trecho
    de texto absurdamente longo. Corta no primeiro quebra-de-linha ou
    traço, que é onde o nome de verdade termina mesmo no caso quebrado."""
    bruto = bruto.strip()
    limpo = limpar_quebra_ocr(bruto)
    candidato = re.split(r"\s*[—–]\s*|\s+-\s+", limpo, maxsplit=1)[0].strip()
    suspeito = candidato != limpo or len(bruto) > 40
    return candidato, suspeito


# --------------------------------------------------------------------------
# URLs de citação (fonte), reconstruídas pelo padrão já confirmado no
# BRIEFING_COLETA.md -- não é um link clicável testado um a um, é o mesmo
# padrão usado em referencias_diario_discursos.json
# --------------------------------------------------------------------------


def url_dcd(data_publicacao: str, pagina: int) -> str:
    dd, mm, aaaa = data_publicacao.split("/")
    return (f"https://imagem.camara.gov.br/dc_20b.asp?largura=&altura=&tipoForm=diarios&"
            f"selCodColecaoCsv=D&Datain={dd}%2F{mm}%2F{aaaa}&txPagina={pagina}&"
            f"txSuplemento=&enviar=Pesquisar")


def url_dsf(data_publicacao: str, pagina: int) -> str:
    dd, mm, aaaa = data_publicacao.split("/")
    return f"https://legis.senado.leg.br/diarios/BuscaDiario?tipDiario=1&datDiario={dd}/{mm}/{aaaa}&paginaDireta={pagina}"


# --------------------------------------------------------------------------
# Fonte 1: pronunciamentos do Senado (API, indice.csv)
# --------------------------------------------------------------------------


def ler_pronunciamentos_senado(candidatos_senado: list[Candidato]) -> list[dict]:
    caminho = CORPUS / "senado" / "pronunciamentos" / "indice.csv"
    with caminho.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    for linha in linhas:
        linha["_pagina_ord"] = int(linha["pagina_inicial"] or 0)
    linhas.sort(key=lambda r: (r["data"], r["_pagina_ord"], r["codigo_pronunciamento"]))

    por_data: dict[str, list[dict]] = {}
    for linha in linhas:
        por_data.setdefault(linha["data"], []).append(linha)

    falas = []
    for data, grupo in sorted(por_data.items()):
        for ordem, linha in enumerate(grupo, start=1):
            orador_id, nome_resolvido, duvidoso = resolver_orador(linha["nome_autor"], candidatos_senado)
            arquivo_txt = RAIZ / linha["arquivo"]
            offset = 0
            if arquivo_txt.exists():
                texto = arquivo_txt.read_text(encoding="utf-8")
                m = so._RE_MARCADOR_CORPO.search(texto)
                offset = m.start() if m else 0
            falas.append({
                "orador_id": orador_id,
                "orador_bruto": linha["nome_autor"],
                "partido_uf": f"{linha['partido']}-{linha['uf']}" if linha["partido"] else "",
                "actor_type": "parlamentar",
                "sessao_id": f"SEN-{data}",
                "sessao": f"Sessão do Senado Federal de {data}",
                "data": data,
                "casa": "senado",
                "unit": extrair_unit(linha["unit"]) if linha["unit"] else "",
                "ordem": ordem,
                "source": linha["url_fonte"],
                "text_status": "ok",
                "corpus_file": linha["arquivo"],
                "_pagina_inicial": linha["_pagina_ord"],
                "offset": offset,
                "needs_review": duvidoso,
            })
    return falas


# --------------------------------------------------------------------------
# Fonte 2: segmentação dos Diários com debate
# --------------------------------------------------------------------------


@dataclass
class BlocoDebate:
    casa: str                      # "camara" ou "senado"
    diretorio: Path
    pagina_inicial: int
    pagina_final: int
    data_sessao: str                # YYYY-MM-DD, data da SESSÃO
    data_publicacao: str             # DD/MM/AAAA, data do DIÁRIO (p/ URL)
    sessao_id: str
    sessao_label: str
    ancora_inicio: str | None = None
    ancora_fim: str | None = None


BLOCOS = [
    BlocoDebate(
        casa="camara",
        diretorio=CORPUS / "camara" / "emendas" / "_compartilhados" / "DCD08DEZ1999_p60552-60574_paginas",
        pagina_inicial=60552, pagina_final=60574,
        data_sessao="1999-12-07", data_publicacao="08/12/1999",
        sessao_id="CAM-DCD08DEZ1999",
        sessao_label="Sessão ordinária da Câmara, 07/12/1999 — discussão, "
                      "pareceres e votação do PL 3808/1997",
    ),
    BlocoDebate(
        casa="camara",
        diretorio=CORPUS / "diarios_camara" / "DCD27OUT1999_p50995-51025_paginas",
        pagina_inicial=51004, pagina_final=51006,
        data_sessao="1999-10-26", data_publicacao="27/10/1999",
        sessao_id="CAM-DCD27OUT1999",
        sessao_label="Sessão da Câmara, 26/10/1999 — votação do requerimento "
                      "de urgência do PL 3808/1997",
        ancora_inicio="O SR. PRESIDENTE (Michel Temer) — Sobre a\nmesa o seguinte requerimento:",
        ancora_fim="O SR. PRESIDENTE (Michel Temer) —\nApresentação de proposições.",
    ),
    BlocoDebate(
        casa="senado",
        diretorio=CORPUS / "senado" / "diarios" / "DSF-202-54_paginas",
        pagina_inicial=35110, pagina_final=35114,
        data_sessao="1999-12-15", data_publicacao="16/12/1999",
        sessao_id="SEN-DSF202-54",
        sessao_label="Sessão do Senado, 15/12/1999 — debate sobre adiar a "
                      "votação de urgência do FUST para janeiro",
    ),
    BlocoDebate(
        casa="senado",
        diretorio=CORPUS / "senado" / "diarios" / "DSF-201-54_p34747-34945_paginas",
        pagina_inicial=34847, pagina_final=34848,
        data_sessao="1999-12-14", data_publicacao="15/12/1999",
        sessao_id="SEN-DSF201-54",
        sessao_label="Sessão do Senado, 14/12/1999 — votação dos quatro "
                      "requerimentos de urgência (Lei Kandir, Rondônia, "
                      "Aeroporto de Teresina, FUST); nenhum aprovado",
        ancora_inicio="O SR. PRESIDENTE (Antonio Carlos Maga-\nlhães) - O "
                       "requerimento lido será despachado à",
        ancora_fim="O SR. PRESIDENTE (Antonio Carlos Maga-\nlhães) — "
                    "Passa-se à",
    ),
]


def ler_blocos_debate(candidatos_camara: list[Candidato],
                      candidatos_senado: list[Candidato]) -> list[dict]:
    falas = []
    for bloco in BLOCOS:
        candidatos = candidatos_camara if bloco.casa == "camara" else candidatos_senado
        brutas = so.segmentar_corpo(
            bloco.diretorio, bloco.pagina_inicial, bloco.pagina_final,
            ancora_inicio=bloco.ancora_inicio, ancora_fim=bloco.ancora_fim,
        )
        url_fn = url_dcd if bloco.casa == "camara" else url_dsf

        for ordem, fala in enumerate(brutas, start=1):
            e_presidencia = fala["nome"].strip().upper().startswith("PRESIDENTE")
            if e_presidencia:
                nome_bruto, nome_suspeito = nome_presidencia(fala["parenteses"] or fala["nome"])
                orador_id, nome_resolvido, duvidoso = resolver_orador(nome_bruto, candidatos)
                duvidoso = duvidoso or nome_suspeito
                partido_uf = ""
                unit = "presidencia"
                partido_suspeito = False
            else:
                nome_bruto = fala["nome"]
                orador_id, nome_resolvido, duvidoso = resolver_orador(nome_bruto, candidatos)
                partido_uf, partido_suspeito = extrair_partido_uf(fala["parenteses"])
                unit = unit_do_marcador_camara(fala["parenteses"]) if fala["parenteses"] else ""

            corpus_file = str(Path(fala["arquivo"]).resolve().relative_to(RAIZ))
            falas.append({
                "orador_id": orador_id,
                "orador_bruto": nome_bruto,
                "partido_uf": partido_uf,
                "actor_type": "parlamentar",
                "sessao_id": bloco.sessao_id,
                "sessao": bloco.sessao_label,
                "data": bloco.data_sessao,
                "casa": bloco.casa,
                "unit": unit,
                "ordem": ordem,
                "source": url_fn(bloco.data_publicacao, fala["pagina"]),
                "text_status": "ok",
                "corpus_file": corpus_file,
                "offset": fala["offset"],
                "needs_review": duvidoso or partido_suspeito or fala.get("sem_parenteses", False) and not e_presidencia,
                "_pagina": fala["pagina"],
            })
    return falas


# --------------------------------------------------------------------------
# Montagem final, prévia e gravação
# --------------------------------------------------------------------------


def checar_sobreposicao_com_api(falas_senado_api: list[dict], falas_debates: list[dict]) -> None:
    """Salvaguarda permanente contra duplicação entre fontes (achado
    pedindo pra conferir: a API cobre Grande Expediente, os blocos de
    Diário cobrem Ordem do Dia -- estruturalmente não deveriam se
    sobrepor, mas 'estruturalmente não deveriam' não é a mesma coisa que
    testado). Página de origem IGUAL, no mesmo Diário/data, é o sinal
    forte de que a mesma fala entrou pelos dois caminhos."""
    paginas_api = {
        (f["data"], int(f.get("_pagina_inicial", -1)))
        for f in falas_senado_api
    }
    for f in falas_debates:
        if f["casa"] != "senado":
            continue  # a Câmara não tem fonte API comparável (armadilha 15) -- nada pra sobrepor
        chave = (f["data"], f["_pagina"])
        if chave in paginas_api:
            print(f"AVISO -- possível duplicata com a API: {f['orador_bruto']} "
                  f"em {f['data']}, página {f['_pagina']} (bloco {f['sessao_id']})",
                  file=sys.stderr)


def montar_linhas() -> list[dict]:
    cand_cam = carregar_roster_camara()
    cand_sen = carregar_roster_senado()

    falas_senado_api = ler_pronunciamentos_senado(cand_sen)
    falas_debates = ler_blocos_debate(cand_cam, cand_sen)
    checar_sobreposicao_com_api(falas_senado_api, falas_debates)

    todas = falas_senado_api + falas_debates

    por_casa: dict[str, list[dict]] = {"camara": [], "senado": []}
    for f in todas:
        por_casa[f["casa"]].append(f)

    linhas = []
    for casa, prefixo in (("senado", "S"), ("camara", "C")):
        grupo = por_casa[casa]
        grupo.sort(key=lambda f: (f["sessao_id"], f["ordem"]))
        for i, f in enumerate(grupo, start=1):
            linha = {col: f.get(col, "") for col in COLUNAS}  # só COLUNAS -- descarta chaves
            linha["id"] = f"{prefixo}{i:04d}"                  # internas tipo _pagina, _pagina_inicial
            for col in COLUNAS_VAZIAS:
                linha[col] = ""
            linhas.append(linha)

    linhas.sort(key=lambda r: r["id"][0] == "C")  # Senado primeiro, depois Câmara, cada um já ordenado
    return linhas


def imprimir_previa(linhas: list[dict]) -> None:
    from collections import Counter

    print("=" * 100)
    print("PRÉVIA — 10 primeiras linhas")
    print("=" * 100)
    for linha in linhas[:10]:
        print(f"\n[{linha['id']}] {linha['orador_bruto']!r} -> orador_id={linha['orador_id']}")
        for col in ("partido_uf", "actor_type", "sessao_id", "data", "casa",
                    "unit", "ordem", "text_status", "needs_review", "offset"):
            print(f"    {col}: {linha[col]!r}")
        print(f"    corpus_file: {linha['corpus_file']}")
        print(f"    source: {linha['source']}")

    print("\n" + "=" * 100)
    print("CONTAGENS")
    print("=" * 100)
    print("\npor casa:", dict(Counter(l["casa"] for l in linhas)))
    print("\npor unit:")
    for u, n in Counter(l["unit"] for l in linhas).most_common():
        print(f"  {u!r}: {n}")
    print("\npor needs_review:", dict(Counter(l["needs_review"] for l in linhas)))

    print("\n" + "=" * 100)
    print("TESTE DA NORMALIZAÇÃO")
    print("=" * 100)
    distintos = {l["orador_id"] for l in linhas}
    duvidosos = [l for l in linhas if l["needs_review"]]
    print(f"orador_id distintos no total: {len(distintos)}")
    print(f"falas com needs_review=True: {len(duvidosos)} de {len(linhas)}")

    print("\npor sessão, pessoas distintas vs falas (sessões com debate nomeado):")
    por_sessao: dict[str, set] = {}
    falas_por_sessao: dict[str, int] = {}
    for l in linhas:
        if l["unit"] == "presidencia":
            continue
        por_sessao.setdefault(l["sessao_id"], set()).add(l["orador_id"])
        falas_por_sessao[l["sessao_id"]] = falas_por_sessao.get(l["sessao_id"], 0) + 1
    for sid in sorted(falas_por_sessao):
        if falas_por_sessao[sid] >= 5:
            print(f"  {sid}: {len(por_sessao[sid])} orador_id distintos, {falas_por_sessao[sid]} falas")

    nao_resolvidos = sorted({l["orador_bruto"] for l in linhas if l["orador_id"].startswith("SEMRESOLVER")})
    if nao_resolvidos:
        print(f"\nnomes sem candidato nenhum no rol ({len(nao_resolvidos)}):")
        for n in nao_resolvidos:
            print(f"  {n!r}")


def gravar(linhas: list[dict]) -> None:
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    caminho_csv = SAIDA_DIR / "arguments_matrix_fust.csv"
    with caminho_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        for linha in linhas:
            w.writerow(linha)
    print(f"gravado: {caminho_csv.relative_to(RAIZ)}")

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "matrix"
    ws.append(COLUNAS)
    for linha in linhas:
        ws.append([linha[c] for c in COLUNAS])
    caminho_xlsx = SAIDA_DIR / "arguments_matrix_fust.xlsx"
    wb.save(caminho_xlsx)
    print(f"gravado: {caminho_xlsx.relative_to(RAIZ)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gravar", action="store_true",
                    help="grava .csv e .xlsx; sem essa flag só mostra a prévia")
    args = ap.parse_args()

    linhas = montar_linhas()
    imprimir_previa(linhas)

    if args.gravar:
        print()
        gravar(linhas)
    else:
        print("\n(prévia só -- rode com --gravar para escrever o .csv e o .xlsx)")


if __name__ == "__main__":
    main()
