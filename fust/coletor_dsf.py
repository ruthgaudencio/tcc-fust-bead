#!/usr/bin/env python3
"""
Baixa os Diários do Senado Federal (DSF) das datas de piso do processo do
PLC 60/1999 -- a parte que a base de pronunciamentos não cobre (armadilha
14: Ordem do Dia não está em API, só no Diário).

Rota confirmada, sem anti-bot (BRIEFING_COLETA.md, seção 4.1-b):

    UrlDiario do pronunciamento                                    (302 ->)
      /diarios/BuscaDiario?tipDiario=1&datDiario=DD/MM/AAAA&paginaDireta=N
      /diarios/ver/{codDiario}?pagina=N          metadado (var diario = {...})
      /diarios/BuscaPaginasDiario?codDiario={codigo}&download=true     PDF

Os alvos NÃO são hardcoded: vêm do url_diario já coletado em
manifesto_pronunciamentos.json para cada DATAS_PISO (o mesmo princípio de
fust/baixar_diarios.py, que deriva de referencias_diario.json em vez de
cravar nomes de arquivo no código). Um url_diario por data basta -- todos
os pronunciamentos do mesmo dia apontam pro mesmo Diário.

O metadado embutido na página /diarios/ver (campo "caderno") já declara a
faixa impressa e o deslocamento, então os DSF NÃO precisam de
paginas.calibrar -- só os DCD da Câmara precisam (não tem esse metadado).

    python coletor_dsf.py --listar     # resolve os codDiario e mostra, sem baixar
    python coletor_dsf.py              # baixa os PDFs pendentes

Convenções da seção 5 do briefing: bruto (o JSON "var diario") salvo antes
do PDF, não sobrescreve X versiona, pendentes_manuais.json com motivo.

Só stdlib.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
MANIFESTO_PRON = CORPUS / "senado" / "pronunciamentos" / "manifesto_pronunciamentos.json"
PENDENTES = CORPUS / "pendentes_manuais.json"

DEST = CORPUS / "senado" / "diarios"
BRUTO = DEST / "_bruto"
MANIFESTO = DEST / "manifesto_dsf.json"

CABECALHOS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

ASSINATURAS = {b"%PDF": "pdf"}

# As 9 datas de piso do coletor_senado.py -- aqui só pra rotular; os
# codDiario vêm do url_diario real, não de uma tabela cravada.
DATAS_PISO = {
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
    if not base.exists():
        return base
    n = 2
    while True:
        alt = base.with_name(f"{base.stem}_v{n}{base.suffix}")
        if not alt.exists():
            return alt
        n += 1


def _get(url: str, *, binario=False, tentativas=3, timeout=40):
    log = []
    for i in range(1, tentativas + 1):
        req = Request(url, headers=CABECALHOS)
        try:
            with urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
                return corpo, resp.geturl(), f"http={resp.status} bytes={len(corpo)}"
        except HTTPError as e:
            log.append(f"http={e.code} {e.reason}")
        except URLError as e:
            log.append(f"rede: {e.reason}")
        except (socket.timeout, TimeoutError):
            log.append("timeout")
        except OSError as e:
            # Pega ConnectionResetError e primos -- não é URLError nem
            # timeout, é outra subclasse de OSError. Apareceu de verdade
            # baixando o DSF de 81MB (3/55): a conexão caiu no meio do
            # stream. Sem isso o download inteiro trava sem log nem
            # retry, igual ao socket.timeout vs TimeoutError antes.
            log.append(f"conexao: {type(e).__name__}: {e}")
        except http.client.IncompleteRead as e:
            # NÃO é OSError (é http.client.HTTPException), outra classe
            # de novo. Aconteceu de verdade no DSF de 352MB (202/54):
            # faltaram 1904 bytes de 352.651.253 -- bem perto, mas sem
            # pegar essa exceção o download inteiro se perde e precisa
            # recomeçar do zero.
            log.append(f"incompleto: {len(e.partial)} de "
                       f"{len(e.partial) + (e.expected or 0)} bytes")
        if i < tentativas:
            time.sleep(min(2**i, 10))
    return None, None, " | ".join(log) or "falhou sem diagnóstico"


def resolver_cod_diario(url_diario: str) -> dict | None:
    """Segue BuscaDiario -> /diarios/ver/{cod} e extrai o bloco JSON
    'var diario = {...}' embutido na página, que já declara a faixa
    impressa -- dispensa calibrar por OCR pros DSF."""
    corpo, final_url, diag = _get(url_diario)
    if corpo is None:
        return None
    m = re.search(r"var diario = (\{.*?\});", corpo.decode("utf-8", "replace"))
    if not m:
        return None
    info = json.loads(m.group(1))
    c = info.get("caderno", {})
    return {
        "codigo": c.get("codigo"),
        "numero": c.get("numero"),
        "ano": c.get("ano"),
        "dataSessao": (c.get("dataSessao") or "")[:10],
        "dataDiario": (c.get("dataDiario") or "")[:10],
        "paginaInicial": c.get("paginaInicial"),
        "paginaFinal": c.get("paginaFinal"),
        "qtdPaginas": c.get("qtdPaginas"),
        "qtdBytesArquivo": c.get("qtdBytesArquivo"),
        "url_resolvida": final_url,
    }


def eh_pdf_de_verdade(caminho: Path) -> bool:
    try:
        return caminho.read_bytes()[:4] == b"%PDF"
    except OSError:
        return False


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="só resolve e mostra, sem baixar")
    ap.add_argument("--forcar", action="store_true", help="rebaixa mesmo o que já tem")
    args = ap.parse_args()

    pron = _ler_json(MANIFESTO_PRON, [])
    if not pron:
        raise SystemExit(f"não achei {MANIFESTO_PRON} -- rode coletor_senado.py primeiro")

    # um url_diario por data de piso (o primeiro que aparecer já serve --
    # todo pronunciamento do mesmo dia aponta pro mesmo Diário).
    url_por_data = {}
    for e in pron:
        if e["data"] in DATAS_PISO and e["data"] not in url_por_data and e.get("url_diario"):
            url_por_data[e["data"]] = e["url_diario"]

    faltando = [d for d in DATAS_PISO if d not in url_por_data]
    if faltando:
        print(f"!! sem url_diario pra: {faltando} (coletor_senado.py não achou "
              f"pronunciamento nessa(s) data(s), ou o campo veio vazio)")

    manifesto = _ler_json(MANIFESTO, [])
    por_codigo = {e["codigo"]: e for e in manifesto if e.get("codigo")}

    print(f"{len(url_por_data)} data(s) de piso com url_diario conhecido, "
          f"de {len(DATAS_PISO)} no total")

    resolvidos: dict[int, dict] = {}
    for data_iso, url_diario in url_por_data.items():
        info = resolver_cod_diario(url_diario)
        if info is None or not info.get("codigo"):
            print(f"\n[{data_iso}] !! não resolveu codDiario a partir de {url_diario}")
            registrar_pendente(url_diario, f"DSF da sessão de {data_iso} ({DATAS_PISO[data_iso]})",
                               "BuscaDiario não resolveu codDiario (404 ou corpo sem o bloco "
                               "'var diario'; pode ser edição/suplemento que esse endpoint de "
                               "busca por página não indexa -- ver achado da pág. 13935/27-06)")
            continue
        cod = info["codigo"]
        resolvidos.setdefault(cod, {"datas": [], **info})
        resolvidos[cod]["datas"].append(data_iso)
        time.sleep(0.2)

    print(f"\n{len(resolvidos)} Diário(s) distinto(s) resolvido(s) pras "
          f"{len(url_por_data)} data(s) de piso com url_diario:\n")
    for cod, info in sorted(resolvidos.items()):
        print(f"  codigo={cod}  DSF {info['numero']}/{info['ano']}  "
              f"datas cobertas: {info['datas']}  "
              f"impressa {info['paginaInicial']}-{info['paginaFinal']}  "
              f"({info['qtdBytesArquivo']:,} bytes, {info['qtdPaginas']} pág.)")

    if args.listar:
        return

    destino_dir = DEST
    destino_dir.mkdir(parents=True, exist_ok=True)
    bruto_dir = BRUTO
    bruto_dir.mkdir(parents=True, exist_ok=True)

    ok = falhou = 0
    for cod, info in sorted(resolvidos.items()):
        nome_pdf = f"DSF-{info['numero']}-{info['ano']}.pdf"
        destino = destino_dir / nome_pdf
        _gravar_json(bruto_dir / f"diario_{cod}.json", info)  # bruto antes do download

        if destino.exists() and not args.forcar:
            print(f"  (já existe) {nome_pdf}")
            ok += 1
            continue

        url_download = f"https://legis.senado.leg.br/diarios/BuscaPaginasDiario?codDiario={cod}&download=true"
        print(f"\n[{nome_pdf}] baixando de {url_download}")
        corpo, final_url, diag = _get(url_download, timeout=120)
        if corpo is None:
            print(f"  FALHOU: {diag}")
            registrar_pendente(url_download, f"DSF {info['numero']}/{info['ano']} "
                               f"(datas {info['datas']})", f"download falhou: {diag}")
            falhou += 1
            continue

        tmp = caminho_versionado(destino)
        tmp.write_bytes(corpo)
        if not eh_pdf_de_verdade(tmp):
            suspeito = tmp.with_suffix(tmp.suffix + ".suspeito.html")
            tmp.rename(suspeito)
            print(f"  !! não é PDF de verdade, isolado em {suspeito.name}")
            registrar_pendente(url_download, f"DSF {info['numero']}/{info['ano']}",
                               "HTTP 200 mas corpo não começa com %PDF")
            falhou += 1
            continue

        print(f"  OK {tmp.name}  ({len(corpo):,} bytes)")
        por_codigo[cod] = {
            "codigo": cod, "numero": info["numero"], "ano": info["ano"],
            "datas_cobertas": info["datas"], "arquivo": str(tmp.relative_to(RAIZ)),
            "bytes": len(corpo), "pagina_inicial_impressa": info["paginaInicial"],
            "pagina_final_impressa": info["paginaFinal"], "deslocamento": (
                info["paginaInicial"] - 1 if isinstance(info["paginaInicial"], int) else None
            ),
            "baixado_em": _agora(),
        }
        _gravar_json(MANIFESTO, list(por_codigo.values()))
        ok += 1
        time.sleep(0.3)

    print(f"\n{ok} DSF ok, {falhou} falha(s). manifesto: {MANIFESTO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
