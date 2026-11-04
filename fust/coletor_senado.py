#!/usr/bin/env python3
"""
Coletor dos pronunciamentos do Plenário do Senado relevantes ao processo
do PLC 60/1999 (FUST).

Cobertura confirmada até 1999 pela API de discursos (BRIEFING_COLETA.md,
seção 2), com texto integral nativo -- esse pedaço do corpus NÃO passa por
OCR.

MÉTODO (revisado -- a lista de 8/9 datas dos informes legislativos estava
errada por construção: informe legislativo registra ATO PROCESSUAL, não
fala. Prova: 1999-12-14 não estava na lista antiga e tem o primeiro
pronunciamento sobre o FUST achado no Senado, de Roberto Freire):

  Varre DIA A DIA toda a janela de 1999-12-01 a 2000-08-31 (armadilha 11:
  consulta mensal trunca). Um pronunciamento entra no corpus se:
    (a) Resumo ou Indexacao bate uma das TERMOS_CHAVE, OU
    (b) a data é uma das DATAS_PISO -- as 8 datas dos informes legislativos
        + 2000-06-28 (conferência), que continuam valendo como PISO
        GARANTIDO (sempre baixa tudo daquele dia), não como escopo (não
        limitam a varredura).

Armadilha 18: o TipoUsoPalavra da API não é confiável pra classificar o
tipo de fala em 1999-2000 (vem sempre "Discurso" mesmo quando o texto diz
"Pela ordem" no parêntese do marcador). A coluna `unit` sai do PARÊNTESE
DO MARCADOR DE ORADOR no texto baixado, não do campo da API. O valor da
API fica em paralelo, em `tipo_uso_palavra_api`/`sigla_tipo_api`, só para
comparação.

    python coletor_senado.py --listar          # varre e mostra quem bateu, sem baixar texto
    python coletor_senado.py                   # varre e baixa tudo que for candidato
    python coletor_senado.py --so 2000-06-29   # só um dia (depuração)
    python coletor_senado.py --forcar          # rebaixa e re-sonda mesmo o que já tem

Convenções mantidas do resto da coleta (seção 5 do briefing):
  - JSON bruto de cada dia salvo ANTES de qualquer download de texto
  - um arquivo por resposta
  - não sobrescreve .txt nem bruto, versiona
  - pendentes_manuais.json para o que falhar, com motivo legível
  - trabalha sobre cópia (baixa pro corpus, não mexe em nada já coletado)

Nota sobre id_local: NÃO renumero S0001.. em ordem cronológica a cada
rodada. Um pronunciamento já baixado mantém o id_local que recebeu (fica
estável, conforme o manifesto); um achado novo pega o próximo número
livre, mesmo que a data dele seja anterior às já numeradas. A alternativa
(renumerar tudo por data) renomearia os arquivos já existentes toda vez
que uma data mais antiga entrasse, duplicando em vez de corrigir --
contra a convenção de não sobrescrever. `indice.csv` já sai ordenado por
data, então a ordem de leitura não depende do número do id_local.

Só stdlib. Rode da raiz do projeto (a pasta que contém corpus_fust/).
"""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import re
import socket
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
PENDENTES = CORPUS / "pendentes_manuais.json"

DEST = CORPUS / "senado" / "pronunciamentos"
BRUTO = DEST / "_bruto"
MANIFESTO = DEST / "manifesto_pronunciamentos.json"
INDICE_CSV = DEST / "indice.csv"

BASE = "https://legis.senado.leg.br/dadosabertos"

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
CABECALHOS_TEXTO = {**CABECALHOS, "Accept": "text/plain,*/*"}

JANELA_INICIO = date(1999, 12, 1)
JANELA_FIM = date(2000, 8, 31)

# As 8 datas dos informes legislativos + 2000-06-28 (conferência: o informe
# de encerramento da discussão está datado de 28/06, a Ordem do Dia diz
# 29/06). PISO GARANTIDO: baixa tudo desse dia mesmo sem bater palavra-chave
# (é assim que 08/12/1999 -- 2 pronunciamentos, nenhum deles sobre FUST por
# palavra-chave -- continua batendo o teste de aceitação).
DATAS_PISO: dict[str, str] = {
    "1999-12-08": "leitura do PLC 60/1999",
    "1999-12-15": "RQS 802/1999",
    "2000-01-10": "leitura do Parecer 1/2000-CAE",
    "2000-01-12": "RQS 10 e 11/2000, de Jáder Barbalho",
    "2000-01-25": "aprovação do RQ 11/2000, com fala de Sérgio Machado",
    "2000-01-26": "encerramento do prazo de emendas",
    "2000-06-27": "leitura do Parecer 712/2000-CI",
    "2000-06-28": "CONFERÊNCIA: informe de encerramento da discussão aponta esta data",
    "2000-06-29": "discussão e votação em turno único, aprovação do Substitutivo",
}

# Palavra-chave pra filtrar Resumo+Indexacao nos outros ~266 dias da janela.
# Comparação é sem acento e em caixa baixa (ver _normalizar).
TERMOS_CHAVE = [
    "universaliz", "telecomunica", "fust", "fundo", "anatel",
    "concessionaria", "privatiz", "3808", "60, de 1999",
]


# --------------------------------------------------------------------------
# Util (mesmo padrão de fust/baixar_diarios.py)
# --------------------------------------------------------------------------


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ler_json(caminho: Path, padrao):
    if not caminho.exists():
        return padrao
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return padrao


def _gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_pendente(url: str, descricao: str, motivo: str) -> None:
    atual = _ler_json(PENDENTES, [])
    if any(e.get("url") == url and e.get("descricao") == descricao for e in atual):
        return
    atual.append({"url": url, "descricao": descricao, "motivo": motivo})
    _gravar_json(PENDENTES, atual)


def caminho_versionado(base: Path) -> Path:
    """Não sobrescreve: devolve base, ou base_v2, base_v3..."""
    if not base.exists():
        return base
    n = 2
    while True:
        alt = base.with_name(f"{base.stem}_v{n}{base.suffix}")
        if not alt.exists():
            return alt
        n += 1


def _sem_acento(s: str) -> str:
    d = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in d if not unicodedata.combining(c))


def _normalizar(s: str) -> str:
    return _sem_acento(s or "").lower()


def _slug(s: str) -> str:
    s = _sem_acento(s or "")
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s


def termos_que_casam(resumo: str, indexacao: str) -> list[str]:
    blob = _normalizar((resumo or "") + " " + (indexacao or ""))
    return [t for t in TERMOS_CHAVE if _normalizar(t) in blob]


# --------------------------------------------------------------------------
# Rede
# --------------------------------------------------------------------------


def _get(url: str, headers: dict, *, tentativas: int = 3, timeout: int = 60):
    """GET com backoff. Devolve (corpo: bytes|None, diagnostico: str)."""
    log = []
    for i in range(1, tentativas + 1):
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
                log.append(f"[tentativa {i}] http={resp.status} bytes={len(corpo)}")
                return corpo, " | ".join(log)
        except HTTPError as e:
            log.append(f"[tentativa {i}] http={e.code} {e.reason}")
        except URLError as e:
            log.append(f"[tentativa {i}] rede: {e.reason}")
        except (socket.timeout, TimeoutError):
            # No Python 3.9 (o que roda neste Mac) socket.timeout e
            # TimeoutError sao classes DIFERENTES -- so se unificam a
            # partir do 3.10. Os .pyc em fust/__pycache__ sao de 3.10, ou
            # seja esse branch nunca foi exercitado nos testes originais.
            log.append(f"[tentativa {i}] timeout")
        except OSError as e:
            # ConnectionResetError e primos: apareceu de verdade baixando
            # DSF grandes em coletor_dsf.py. Mesma classe de problema do
            # socket.timeout acima -- captura ampla pra nao derrubar a
            # coleta inteira sem log nem retry.
            log.append(f"[tentativa {i}] conexao: {type(e).__name__}: {e}")
        except http.client.IncompleteRead as e:
            # Também apareceu de verdade (DSF de 352MB) e não é OSError.
            log.append(f"[tentativa {i}] incompleto: {len(e.partial)} bytes")
        if i < tentativas:
            time.sleep(min(2**i, 15))
    return None, " | ".join(log)


def get_json(url: str):
    corpo, diag = _get(url, CABECALHOS)
    if corpo is None:
        print(f"    ERRO: {diag}")
        return None, diag
    try:
        return json.loads(corpo), diag
    except json.JSONDecodeError:
        print(f"    resposta não-JSON ({len(corpo)} bytes): {corpo[:120]!r}")
        return None, diag


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pronunciamento:
    codigo: str
    data: str
    casa: str
    tipo_uso_palavra_api: str
    sigla_tipo_api: str
    nome_autor: str
    codigo_parlamentar: str
    partido: str
    uf: str
    resumo: str
    indexacao: str
    url_texto_integral_txt: str
    url_fonte: str
    pagina_inicial: str = ""
    data_publicacao: str = ""
    url_diario: str = ""


def _como_lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def listar_discursos(data_iso: str, *, forcar: bool = False) -> tuple[list[Pronunciamento], dict | None]:
    """Varre UM dia (não intervalo, ver armadilha 11). Salva o bruto antes
    de qualquer outra coisa -- e reaproveita o bruto já salvo em vez de
    reconsultar, a não ser que --forcar peça para sondar de novo."""
    aaaammdd = data_iso.replace("-", "")
    nome_bruto = BRUTO / f"discursos_{aaaammdd}.json"

    if nome_bruto.exists() and not forcar:
        j = _ler_json(nome_bruto, None)
        bruto_path = nome_bruto
    else:
        url = f"{BASE}/plenario/lista/discursos/{aaaammdd}/{aaaammdd}"
        j, diag = get_json(url)
        bruto_path = caminho_versionado(nome_bruto) if nome_bruto.exists() else nome_bruto
        if j is not None:
            _gravar_json(bruto_path, j)
        else:
            registrar_pendente(url, f"Lista de discursos do Senado em {data_iso}",
                               f"falha na API: {diag}")
            return [], None

    raiz = (j or {}).get("DiscursosSessao") or {}
    sessoes = _como_lista((raiz.get("Sessoes") or {}).get("Sessao"))
    out: list[Pronunciamento] = []
    for sessao in sessoes:
        pron = _como_lista((sessao.get("Pronunciamentos") or {}).get("Pronunciamento"))
        for p in pron:
            pubs = _como_lista((p.get("Publicacoes") or {}).get("Publicacao"))
            pub0 = pubs[0] if pubs else {}
            out.append(
                Pronunciamento(
                    codigo=str(p.get("CodigoPronunciamento") or p.get("id") or ""),
                    data=p.get("Data") or data_iso,
                    casa=p.get("Casa") or "",
                    tipo_uso_palavra_api=(p.get("TipoUsoPalavra") or {}).get("Descricao", ""),
                    sigla_tipo_api=(p.get("TipoUsoPalavra") or {}).get("Sigla", ""),
                    nome_autor=p.get("NomeAutor") or "",
                    codigo_parlamentar=str(p.get("CodigoParlamentar") or ""),
                    partido=p.get("Partido") or "",
                    uf=p.get("UF") or "",
                    resumo=p.get("Resumo") or "",
                    indexacao=p.get("Indexacao") or "",
                    url_texto_integral_txt=p.get("TextoIntegralTxt") or "",
                    url_fonte=p.get("TextoIntegral") or "",
                    pagina_inicial=str(pub0.get("PaginaInicial") or ""),
                    data_publicacao=pub0.get("DataPublicacao") or "",
                    url_diario=pub0.get("UrlDiario") or "",
                )
            )
    return out, {"url": str(bruto_path), "n_sessoes": len(sessoes),
                 "arquivo_bruto": str(bruto_path.relative_to(RAIZ))}


def baixar_texto(p: Pronunciamento) -> tuple[bytes | None, str]:
    if not p.url_texto_integral_txt:
        return None, "sem URL de TextoIntegralTxt no registro"
    corpo, diag = _get(p.url_texto_integral_txt, CABECALHOS_TEXTO)
    if corpo is None:
        return None, diag
    amostra = corpo[:200].lstrip()
    if amostra[:1] in (b"<", b"{") and b"O SR." not in corpo[:400] and b"A SR" not in corpo[:400]:
        return None, f"corpo não parece discurso (começa com {amostra[:60]!r})"
    return corpo, diag


# --------------------------------------------------------------------------
# unit -- armadilha 18: sai do parêntese do marcador, não da API
# --------------------------------------------------------------------------

_RE_MARCADOR = re.compile(r"\b[OA]\s+SR[A\xaa]?\.?\s*[^(\n]*\(([^)]*)\)", re.UNICODE)


def extrair_unit(corpo_texto: str) -> str:
    """
    'O SR. ROBERTO FREIRE (Bloco/PPS - PE. Pela ordem. Sem revisão do
    orador.) - Sr. Presidente...' -> 'Pela ordem'.

    O parêntese tem partido-UF primeiro, depois 0+ segmentos de modalidade,
    e quase sempre termina com uma nota de revisão ('Sem/Com revisão do
    orador'/'da oradora'), que não é modalidade e é descartada. Quando não
    acha marcador reconhecível, devolve "" -- não inventa valor.

    Duas pegadinhas reais encontradas rodando contra os 364 pronunciamentos
    (não só contra os exemplos manuais do briefing):
      - Senadoras usam 'A SRª NOME' ou 'A SRA. NOME', não 'O SR.' -- o
        marcador tem que casar os dois gêneros.
      - Boa parte dos textos vem com um timbre antes do marcador
        ('SENADO FEDERAL / SECRETARIA-GERAL DA MESA / SUBSECRETARIA DE
        TAQUIGRAFIA'), então ancorar no início absoluto do texto (^) perde
        o marcador -- procura numa janela maior, não só no começo exato.
    """
    janela = (corpo_texto or "").lstrip()[:1200]
    m = _RE_MARCADOR.search(janela)
    if not m:
        return ""
    partes = [p.strip() for p in re.split(r"\.\s+", m.group(1)) if p.strip()]
    if len(partes) < 2:
        return ""
    modalidade = [p for p in partes[1:] if not re.search(r"revis[aã]o", p, re.IGNORECASE)]
    return "; ".join(modalidade)


# --------------------------------------------------------------------------
# Indexação / saída
# --------------------------------------------------------------------------

COLUNAS_INDICE = [
    "id_local", "codigo_pronunciamento", "data", "casa", "tipo_uso_palavra_api",
    "sigla_tipo_api", "unit", "nome_autor", "codigo_parlamentar", "partido", "uf",
    "pagina_inicial", "data_publicacao", "url_diario", "resumo", "indexacao",
    "termo_que_casou", "arquivo", "url_fonte",
]


def nome_arquivo(id_local: str, p: Pronunciamento) -> str:
    autor = _slug(p.nome_autor) or "autor-desconhecido"
    partido_uf = f"{_slug(p.partido)}-{_slug(p.uf)}".strip("-") or "sem-partido"
    return f"{id_local}_{autor}_{partido_uf}_{p.data}.txt"


def cabecalho_txt(id_local: str, p: Pronunciamento) -> str:
    # Formato inalterado desde a primeira versão (seção 4.1 do briefing não
    # pediu mudança aqui, só no indice.csv) -- os 135 .txt já gravados
    # continuam compatíveis e eu não reabro nenhum deles.
    linhas = [
        f"# {id_local} | {p.nome_autor} | {p.partido}-{p.uf} | "
        f"CodigoPronunciamento {p.codigo}",
        f"# {p.casa} | Sessão de {p.data} | "
        f"TipoUsoPalavra: {p.tipo_uso_palavra_api} ({p.sigla_tipo_api})",
        f"# resumo: {p.resumo}",
        f"# source: {p.url_texto_integral_txt}",
        "",
    ]
    return "\n".join(linhas)


def reescrever_indice(manifesto: list[dict]) -> None:
    """indice.csv é derivado, sempre reescrito do zero -- não é dado bruto
    nem o .txt, reescrever não viola a convenção de não sobrescrever."""
    INDICE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with INDICE_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_INDICE)
        w.writeheader()
        for e in sorted(manifesto, key=lambda e: (e["data"], e["codigo_pronunciamento"])):
            w.writerow({k: e.get(k, "") for k in COLUNAS_INDICE})


def _texto_corpo_de(entrada: dict) -> str | None:
    """Lê o corpo (sem cabeçalho) de um .txt já baixado, para reaproveitar
    sem rebaixar -- usado tanto para extrair `unit` de entradas antigas
    quanto para não bater na rede à toa."""
    caminho = RAIZ / entrada.get("arquivo", "")
    if not caminho.exists():
        return None
    conteudo = caminho.read_text(encoding="utf-8")
    # cabecalho_txt grava exatamente 4 linhas "#..." seguidas DIRETO do
    # corpo (sem linha em branco separando -- "\n".join([...,""]) só
    # fecha a 4a linha). maxsplit=4 corta certo nessa emenda E preserva
    # quebras de linha internas do corpo (um split("\n") straight e
    # rejuntar com "\n" achatava blank lines do discurso original).
    partes = conteudo.split("\n", 4)
    if len(partes) == 5 and all(l.startswith("#") for l in partes[:4]):
        return partes[4]
    return conteudo


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _intervalo_dias(inicio: date, fim: date):
    d = inicio
    while d <= fim:
        yield d.isoformat()
        d += timedelta(days=1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true",
                    help="varre e mostra quem bateu (piso ou palavra-chave), sem baixar texto")
    ap.add_argument("--so", help="só processa um dia (AAAA-MM-DD), para depuração")
    ap.add_argument("--forcar", action="store_true",
                    help="rebaixa texto já baixado e re-sonda dias já cacheados em _bruto/")
    args = ap.parse_args()

    dias = [args.so] if args.so else list(_intervalo_dias(JANELA_INICIO, JANELA_FIM))

    manifesto = _ler_json(MANIFESTO, [])
    por_codigo = {e["codigo_pronunciamento"]: e for e in manifesto}
    numeros_usados = [int(e["id_local"][1:]) for e in por_codigo.values()
                      if e.get("id_local", "").startswith("S")]
    proximo_numero = (max(numeros_usados) + 1) if numeros_usados else 1

    print(f"janela: {JANELA_INICIO} a {JANELA_FIM} ({len(dias)} dia(s)); "
          f"{len(DATAS_PISO)} data(s) de piso garantido; "
          f"{len(por_codigo)} pronunciamento(s) já no manifesto")

    total_dias_com_sessao = 0
    total_candidatos = 0
    total_baixados_agora = 0
    total_falhas = 0

    for data_iso in dias:
        eh_piso = data_iso in DATAS_PISO
        prons, info = listar_discursos(data_iso, forcar=args.forcar)
        if info is None:
            continue
        if not prons:
            continue
        total_dias_com_sessao += 1

        candidatos = []
        for p in prons:
            termos = termos_que_casam(p.resumo, p.indexacao)
            if termos or eh_piso:
                candidatos.append((p, termos))

        if not candidatos:
            continue
        total_candidatos += len(candidatos)

        rotulo = DATAS_PISO.get(data_iso, "")
        print(f"\n[{data_iso}]{'  PISO: ' + rotulo if eh_piso else ''}  "
              f"{len(prons)} no dia, {len(candidatos)} candidato(s)")

        if args.listar:
            for p, termos in candidatos:
                motivo = "+".join(termos) if termos else "(piso, sem termo)"
                print(f"    {p.codigo}  {p.nome_autor} ({p.partido}-{p.uf})  [{motivo}]  "
                      f"-- {p.resumo[:70]}")
            continue

        for p, termos in candidatos:
            existente = por_codigo.get(p.codigo)
            texto_corpo = None
            arq = None
            id_local = None

            if existente and not args.forcar:
                texto_corpo = _texto_corpo_de(existente)
                if texto_corpo is not None:
                    arq = RAIZ / existente["arquivo"]
                    id_local = existente["id_local"]
                else:
                    existente = None  # arquivo sumiu: trata como novo

            if texto_corpo is None:
                corpo, diag = baixar_texto(p)
                if corpo is None:
                    print(f"    FALHOU {p.codigo} ({p.nome_autor}): {diag}")
                    registrar_pendente(
                        p.url_texto_integral_txt or f"<sem URL> discurso {p.codigo}",
                        f"Discurso {p.codigo} ({p.nome_autor}, {p.data})",
                        f"download do texto integral falhou: {diag}",
                    )
                    total_falhas += 1
                    time.sleep(0.15)
                    continue
                texto_corpo = corpo.decode("utf-8", "replace")
                id_local = (existente or {}).get("id_local") or f"S{proximo_numero:04d}"
                if not (existente or {}).get("id_local"):
                    proximo_numero += 1
                arq = caminho_versionado(DEST / nome_arquivo(id_local, p))
                arq.parent.mkdir(parents=True, exist_ok=True)
                arq.write_text(cabecalho_txt(id_local, p) + texto_corpo, encoding="utf-8")
                total_baixados_agora += 1

            unit = extrair_unit(texto_corpo)
            entrada = {
                "id_local": id_local,
                "codigo_pronunciamento": p.codigo,
                "data": p.data,
                "casa": p.casa,
                "tipo_uso_palavra_api": p.tipo_uso_palavra_api,
                "sigla_tipo_api": p.sigla_tipo_api,
                "unit": unit,
                "nome_autor": p.nome_autor,
                "codigo_parlamentar": p.codigo_parlamentar,
                "partido": p.partido,
                "uf": p.uf,
                "pagina_inicial": p.pagina_inicial,
                "data_publicacao": p.data_publicacao,
                "url_diario": p.url_diario,
                "resumo": p.resumo,
                "indexacao": p.indexacao,
                "termo_que_casou": "; ".join(termos),
                "motivo_inclusao": "piso" if eh_piso and not termos else (
                    "piso+palavra-chave" if eh_piso else "palavra-chave"),
                "arquivo": str(arq.relative_to(RAIZ)),
                "url_fonte": p.url_texto_integral_txt,
                "baixado": True,
                "baixado_em": (existente or {}).get("baixado_em") or _agora(),
            }
            por_codigo[p.codigo] = entrada
            # grava a cada item: se a rede cair no meio, o que já foi
            # processado fica rastreado e um rerun não refaz do zero.
            _gravar_json(MANIFESTO, list(por_codigo.values()))
            reescrever_indice(list(por_codigo.values()))
            print(f"    OK {id_local} {p.codigo} {p.nome_autor} ({p.partido}-{p.uf})  "
                  f"unit='{unit}'  termo={entrada['termo_que_casou'] or '(piso)'}")
            time.sleep(0.15)

    if not args.listar:
        print(f"\n{total_dias_com_sessao} dia(s) com sessão na janela, "
              f"{total_candidatos} pronunciamento(s) candidato(s), "
              f"{total_baixados_agora} texto(s) novo(s) baixado(s) agora, "
              f"{total_falhas} falha(s) nesta rodada.")
        print(f"total no manifesto: {len(por_codigo)}")
        print(f"manifesto: {MANIFESTO.relative_to(RAIZ)}")
        print(f"índice: {INDICE_CSV.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
