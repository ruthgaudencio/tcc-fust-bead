#!/usr/bin/env python3
"""
Baixa as 31 emendas do PL 3808/1997 que a API da Câmara lista como
proposições próprias (BRIEFING_COLETA.md, seção 2 e 4.3):

    EMC 1 a 6/1998    ids 68753 a 68758   apresentadas 19/03/1998
    EMC 7/1999        id  68759           apresentada  02/12/1999
    EMP 1 a 24/1999   ids 68760 a 68783   todas de     07/12/1999

Para cada id: GET /proposicoes/{id} (salva bruto ANTES de qualquer
download), extrai urlInteiroTeor, baixa o PDF com sniff de magic bytes
(armadilha 1: HTTP 200 não garante PDF).

Algumas podem ter o mesmo problema do codteor da proposição principal
(armadilha 9): resolve em HTML com meta-refresh em vez de PDF direto. Por
isso usa a mesma cadeia de resolução já confirmada em coleta_brasil.py
(Wicket -> dc_20.asp/dc_20b.asp -> montaPdf.asp -> PDF final), reescrita
aqui em stdlib puro.

Discrepância conhecida, registrada e NÃO resolvida (não é desta coleta
decidir o motivo): as tramitações descrevem ~50 emendas ao longo do
processo (7 em 03/1998, 8 ao substitutivo em 11/1998, 5 em 03/1999, 30 ao
substitutivo em 08/1999), e a API só lista 31 como proposições próprias.
Provavelmente emenda retirada ou renumerada -- anotado em
emendas_discrepancia.json, sem tentar reconciliar.

    python coletor_emendas_camara.py --listar     # só mostra o plano
    python coletor_emendas_camara.py              # baixa tudo que falta
    python coletor_emendas_camara.py --forcar     # rebaixa mesmo o que já tem

Convenções da seção 5: bruto salvo antes do download, não sobrescreve
(versiona), pendentes_manuais.json com motivo, retry com backoff
(armadilha 8: a API da Câmara já ficou fora do ar no meio da coleta).

Só stdlib.
"""

from __future__ import annotations

import argparse
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
PENDENTES = CORPUS / "pendentes_manuais.json"

DEST = CORPUS / "camara" / "emendas"
MANIFESTO = DEST / "manifesto_emendas.json"
NOTA_DISCREPANCIA = DEST / "emendas_discrepancia.json"

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}
CABECALHOS_JSON = {**CABECALHOS, "Accept": "application/json"}

ASSINATURAS = {
    b"%PDF": "pdf",
    b"{\\rt": "rtf",
    b"PK\x03\x04": "zip/ooxml",
    b"\xd0\xcf\x11\xe0": "ole/doc",
}

# Faixa confirmada contra a API real (seção 2 do briefing).
IDS_EMENDAS: list[tuple[int, str]] = (
    [(68753 + i, f"EMC {i + 1}/1998") for i in range(6)]
    + [(68759, "EMC 7/1999")]
    + [(68760 + i, f"EMP {i + 1}/1999") for i in range(24)]
)


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


def _get(url: str, headers: dict, *, tentativas: int = 4, timeout: int = 40):
    """GET com backoff -- armadilha 8: a API da Câmara já caiu no meio da
    coleta (DNS resolvia, as 3 IPs recusavam conexão)."""
    log = []
    for i in range(1, tentativas + 1):
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
                return corpo, resp.geturl(), f"[tentativa {i}] http={resp.status} bytes={len(corpo)}"
        except HTTPError as e:
            log.append(f"[tentativa {i}] http={e.code} {e.reason}")
        except URLError as e:
            log.append(f"[tentativa {i}] rede: {e.reason}")
        except (socket.timeout, TimeoutError):
            log.append(f"[tentativa {i}] timeout")
        except http.client.IncompleteRead as e:
            log.append(f"[tentativa {i}] incompleto: {len(e.partial)} bytes")
        except OSError as e:
            log.append(f"[tentativa {i}] conexao: {type(e).__name__}: {e}")
        if i < tentativas:
            time.sleep(min(2**i, 20))
    return None, None, " | ".join(log) or "falhou sem diagnóstico"


def get_json(url: str):
    corpo, _, diag = _get(url, CABECALHOS_JSON)
    if corpo is None:
        return None, diag
    try:
        return json.loads(corpo), diag
    except json.JSONDecodeError:
        return None, f"resposta não-JSON: {diag}"


def identificar(corpo: bytes) -> str | None:
    for assinatura, nome in ASSINATURAS.items():
        if corpo.startswith(assinatura):
            return nome
    return None


_RE_REFRESH = re.compile(r'URL=([^"\'>]+)', re.IGNORECASE)


def resolver_meta_refresh(html: str) -> str | None:
    m = _RE_REFRESH.search(html)
    return m.group(1).strip() if m else None


def resolver_inteiro_teor(url_it: str) -> tuple[str | None, str]:
    """Mesma cadeia de coleta_brasil.py (armadilha 9), reescrita em stdlib:
    proposições antigas devolvem HTML com meta-refresh em vez de PDF
    direto. Devolve (url_pdf_final_ou_None, diagnostico)."""
    corpo, _, diag = _get(url_it, CABECALHOS)
    if corpo is None:
        return None, diag
    if corpo[:4] == b"%PDF":
        return url_it, "PDF direto"

    alvo1 = resolver_meta_refresh(corpo.decode("utf-8", "replace"))
    if not alvo1:
        return None, "sem meta-refresh reconhecível na página de inteiro teor"
    corpo2, url_final2, diag2 = _get(alvo1, CABECALHOS)
    if corpo2 is None:
        return None, f"1o redirecionamento falhou: {diag2}"
    if corpo2[:4] == b"%PDF":
        return url_final2, "PDF após 1 redirecionamento"

    alvo2 = resolver_meta_refresh(corpo2.decode("utf-8", "replace"))
    if not alvo2:
        return None, "sem 2o meta-refresh (página montaPdf.asp mudou de formato?)"
    return alvo2.split("#")[0], "resolvido via 2 redirecionamentos (cadeia de codteor antigo)"


def baixar_pdf(url: str, destino: Path, descricao: str) -> Path | None:
    corpo, _, diag = _get(url, CABECALHOS)
    if corpo is None:
        registrar_pendente(url, descricao, f"download falhou: {diag}")
        return None
    tipo = identificar(corpo)
    if tipo is None:
        amostra = corpo[:200].decode("utf-8", "replace").replace("\n", " ")
        suspeito = caminho_versionado(destino.with_suffix(destino.suffix + ".suspeito.html"))
        suspeito.parent.mkdir(parents=True, exist_ok=True)
        suspeito.write_bytes(corpo)
        registrar_pendente(url, descricao,
                           f"HTTP 200 mas corpo não é arquivo reconhecido (começa com "
                           f"{amostra[:120]!r}); isolado em {suspeito.name}")
        return None
    final = caminho_versionado(destino)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(corpo)
    return final


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="só mostra o plano, sem baixar")
    ap.add_argument("--forcar", action="store_true", help="rebaixa mesmo o que já tem")
    args = ap.parse_args()

    manifesto = _ler_json(MANIFESTO, [])
    por_id = {e["id"]: e for e in manifesto}

    if args.listar:
        for id_, rotulo in IDS_EMENDAS:
            feito = "ok" if por_id.get(id_, {}).get("pdf_baixado") else "--"
            print(f"  [{feito}] {id_}  {rotulo}")
        print(f"\n{len(IDS_EMENDAS)} emendas no total, "
              f"{sum(1 for e in por_id.values() if e.get('pdf_baixado'))} já com PDF")
        return

    ok = falhou = ja_tinha = 0
    for id_, rotulo in IDS_EMENDAS:
        existente = por_id.get(id_)
        if existente and existente.get("pdf_baixado") and not args.forcar:
            ja_tinha += 1
            continue

        print(f"\n[{rotulo}] id={id_}")
        sub = DEST / str(id_)

        j, diag = get_json(f"{CAMARA}/proposicoes/{id_}")
        if j is None or not j.get("dados"):
            print(f"  !! não consegui buscar a proposição: {diag}")
            registrar_pendente(f"{CAMARA}/proposicoes/{id_}", f"{rotulo} (id={id_})",
                               f"GET /proposicoes/{id_} falhou: {diag}")
            falhou += 1
            continue

        dados = j["dados"]
        _gravar_json(sub / "proposicao.json", dados)  # bruto ANTES do download
        ementa = (dados.get("ementa") or "")[:100]
        print(f"  {dados.get('siglaTipo')} {dados.get('numero')}/{dados.get('ano')} -- {ementa}")

        url_it = dados.get("urlInteiroTeor")
        if not url_it:
            print("  !! sem urlInteiroTeor")
            registrar_pendente(f"{CAMARA}/proposicoes/{id_}", f"{rotulo} (id={id_})",
                               "proposição sem campo urlInteiroTeor")
            por_id[id_] = {"id": id_, "rotulo": rotulo, "pdf_baixado": False,
                           "motivo": "sem urlInteiroTeor", "atualizado_em": _agora()}
            _gravar_json(MANIFESTO, list(por_id.values()))
            falhou += 1
            continue

        url_pdf, diag_resolucao = resolver_inteiro_teor(url_it)
        if not url_pdf:
            print(f"  !! não resolveu PDF: {diag_resolucao}")
            registrar_pendente(url_it, f"{rotulo} (id={id_})",
                               f"resolução do inteiro teor falhou: {diag_resolucao}")
            por_id[id_] = {"id": id_, "rotulo": rotulo, "pdf_baixado": False,
                           "motivo": diag_resolucao, "atualizado_em": _agora()}
            _gravar_json(MANIFESTO, list(por_id.values()))
            falhou += 1
            continue

        nome_pdf = f"emenda_{id_}.pdf"
        destino = sub / nome_pdf
        resultado = baixar_pdf(url_pdf, destino, f"{rotulo} (id={id_})")
        if resultado is None:
            print(f"  !! download/sniff falhou (ver pendentes_manuais.json)")
            por_id[id_] = {"id": id_, "rotulo": rotulo, "pdf_baixado": False,
                           "motivo": "download ou magic-bytes falhou", "atualizado_em": _agora()}
            _gravar_json(MANIFESTO, list(por_id.values()))
            falhou += 1
            continue

        print(f"  OK {resultado.name} ({resultado.stat().st_size:,} bytes) -- {diag_resolucao}")
        por_id[id_] = {
            "id": id_, "rotulo": rotulo,
            "sigla_tipo": dados.get("siglaTipo"), "numero": dados.get("numero"),
            "ano": dados.get("ano"), "ementa": dados.get("ementa"),
            "url_inteiro_teor_api": url_it, "url_pdf_resolvida": url_pdf,
            "estrategia_resolucao": diag_resolucao,
            "arquivo": str(resultado.relative_to(RAIZ)),
            "bytes": resultado.stat().st_size,
            "pdf_baixado": True, "atualizado_em": _agora(),
        }
        _gravar_json(MANIFESTO, list(por_id.values()))
        ok += 1
        time.sleep(0.3)

    nota = {
        "achado": ("As tramitações descrevem cerca de 50 emendas ao longo do processo: "
                   "7 em 03/1998, 8 ao substitutivo em 11/1998, 5 em 03/1999, 30 ao "
                   "substitutivo em 08/1999."),
        "api_lista": f"{len(IDS_EMENDAS)} proposições próprias (ids "
                     f"{IDS_EMENDAS[0][0]} a {IDS_EMENDAS[-1][0]})",
        "hipotese_nao_verificada": "emenda retirada ou renumerada ao longo do processo",
        "decisao": "não reconciliado por esta coleta -- registrado para quem for escrever "
                   "a metodologia decidir o que fazer com a diferença",
    }
    _gravar_json(NOTA_DISCREPANCIA, nota)

    print(f"\n{ok} baixada(s) agora, {ja_tinha} já tinha(m), {falhou} falha(s) "
          f"de {len(IDS_EMENDAS)} emenda(s) no total.")
    print(f"manifesto: {MANIFESTO.relative_to(RAIZ)}")
    print(f"nota de discrepância: {NOTA_DISCREPANCIA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
