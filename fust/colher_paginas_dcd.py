#!/usr/bin/env python3
"""
Generaliza o achado da sonda da Câmara (fust/sonda_camara.py): para
07/12/1999, o urlTexto por discurso deu páginas mais granulares (60554,
60565, 60570) que a única página que vinha do despacho (60552) -- a
faixa real do DCD08DEZ1999 é 60552 a 60570, não um ponto só.

Este script repete a coleta para as 8 datas de DCD do escopo (até a
sanção), não só 07/12/1999, e grava a faixa real de cada uma.

NÃO decide nada sobre corte de página ou OCR -- só coleta e relata. NÃO
toca em referencias_diario.json (convenção: trabalhar sobre cópia); grava
num arquivo irmão.

Limitação igual à da sonda: /deputados/{id}/discursos é por deputado, não
tem rota de "todos os discursos de uma data" na API da Câmara (testado:
/discursos e /eventos/{id}/discursos devolvem 405, não existem pra
leitura). Então a cobertura aqui é dos deputados conhecidamente ligados
ao PL 3808 -- autor, relatores ao longo do processo, autor da Emenda 24
-- não de QUALQUER deputado que tenha discursado naquele dia. Pode faltar
gente; não pode sobrar (um discurso desses sempre é sobre o processo,
porque é assim que a sonda achou os de 07/12/1999).

    python colher_paginas_dcd.py

Só stdlib.
"""

from __future__ import annotations

import json
import re
import socket
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
ORIGINAL = CORPUS / "camara" / "referencias_diario.json"
SAIDA = CORPUS / "camara" / "referencias_diario_discursos.json"  # arquivo irmão

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Deputados conhecidamente ligados ao processo (autor, relatores em cada
# fase, autor da Emenda 24). Ids confirmados contra a API:
#   - Walter Pinheiro: achado via /proposicoes/68783/autores (armadilha 16
#     do briefing -- busca por nome não resolve esse deputado).
#   - José Pimentel: de camara/autores.json (coleta anterior).
#   - Zimbaldi, Mendes Ribeiro Filho, Custódio Mattos: da sonda anterior.
# Paulo Bornhausen (relator 12/1997-03/1999) também não resolve por nome
# na API e eu não achei um atalho por autoria a tempo; nenhuma das 8
# datas cai bem no meio do mandato dele como relator (a primeira, 14/11/97,
# é só leitura e publicação), então não deveria faltar nada essencial --
# mas é uma lacuna de cobertura, não um "não existe".
DEPUTADOS = {
    "José Pimentel (autor)": 74298,
    "Walter Pinheiro (autor Emenda 24 / relator substituto CFT)": 74218,
    "Salvador Zimbaldi (relator 1999)": 73559,
    "Mendes Ribeiro Filho (relator CFT 07/12/1999)": 73904,
    "Custódio Mattos (relator CCJR)": 74579,
}

# As 8 datas de DCD do escopo (briefing, seção 4.4), com a data de SESSÃO
# (um dia antes da publicação, na maioria) usada para consultar a API.
DATAS_DCD = [
    {"arquivo": "DCD14NOV1997.pdf", "data_sessao": "1997-11-14", "pagina_despacho": 36602},
    {"arquivo": "DCD17SET1999.pdf", "data_sessao": "1999-09-16", "pagina_despacho": 42741},
    {"arquivo": "DCD24SET1999.pdf", "data_sessao": "1999-09-21", "pagina_despacho": 44216},
    {"arquivo": "DCD02DEZ1999.pdf", "data_sessao": "1999-09-21", "pagina_despacho": 2340,
     "nota": "republicação do parecer de 24/09; sessão original é a mesma, numeração "
             "de página reiniciada (provável novo volume)"},
    {"arquivo": "DCD27OUT1999.pdf", "data_sessao": "1999-10-26", "pagina_despacho": 51004},
    {"arquivo": "DCD04NOV1999.pdf", "data_sessao": "1999-11-03", "pagina_despacho": 52165},
    {"arquivo": "DCD25NOV1999.pdf", "data_sessao": "1999-11-25", "pagina_despacho": 57254},
    {"arquivo": "DCD08DEZ1999.pdf", "data_sessao": "1999-12-07", "pagina_despacho": 60552},
]

RE_PAGINA = re.compile(r"txPagina=(\d+)")

TERMOS_FUST = ("3808", "9998", "FUST", "TELECOMUNICA", "UNIVERSALIZA", "PLC 60", "PLC 00060")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get_json(url: str, *, tentativas: int = 3, timeout: int = 25):
    log = []
    for i in range(1, tentativas + 1):
        req = Request(url, headers=CABECALHOS)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read()), "ok"
        except HTTPError as e:
            log.append(f"http={e.code} {e.reason}")
        except URLError as e:
            log.append(f"rede: {e.reason}")
        except (socket.timeout, TimeoutError):
            # mesma correção do coletor_senado.py: no Python 3.9 socket.timeout
            # e TimeoutError são classes diferentes.
            log.append("timeout")
        if i < tentativas:
            time.sleep(min(2**i, 10))
    return None, " | ".join(log) or "falhou sem diagnóstico"


def eh_sobre_fust(registro: dict) -> bool:
    blob = ((registro.get("sumario") or "") + " " + (registro.get("keywords") or "")).upper()
    return any(t in blob for t in TERMOS_FUST)


def main() -> None:
    if not ORIGINAL.exists():
        raise SystemExit(f"não achei {ORIGINAL} -- rode a coleta da Câmara primeiro")

    resultado = {"rodado_em": _agora(), "origem": str(ORIGINAL.relative_to(RAIZ)),
                 "nota": "arquivo irmão -- referencias_diario.json não foi alterado",
                 "cobertura": "so os deputados listados em DEPUTADOS, nao todo mundo que falou "
                              "naquele dia (API nao tem rota de busca por data sem ser por "
                              "deputado -- ver docstring)",
                 "diarios": []}

    print("=" * 78)
    print("COLHER PAGINAS POR DISCURSO -- as 8 datas de DCD do escopo")
    print("=" * 78)

    for alvo in DATAS_DCD:
        print(f"\n[{alvo['arquivo']}]  sessão {alvo['data_sessao']}  "
              f"(despacho só tinha pág. {alvo['pagina_despacho']})")
        if alvo.get("nota"):
            print(f"  nota: {alvo['nota']}")

        d0 = date.fromisoformat(alvo["data_sessao"])
        data_inicio = d0.isoformat()
        data_fim = (d0 + timedelta(days=1)).isoformat()

        achados = []
        for nome_dep, dep_id in DEPUTADOS.items():
            url = (f"{CAMARA}/deputados/{dep_id}/discursos"
                   f"?dataInicio={data_inicio}&dataFim={data_fim}")
            j, diag = _get_json(url)
            if j is None:
                print(f"    !! {nome_dep}: ERRO ({diag})")
                continue
            registros = j.get("dados", [])
            for r in registros:
                m = RE_PAGINA.search(r.get("urlTexto") or "")
                pagina = int(m.group(1)) if m else None
                sobre_fust = eh_sobre_fust(r)
                achados.append({
                    "deputado": nome_dep,
                    "data": r.get("dataHoraInicio"),
                    "tipoDiscurso": r.get("tipoDiscurso"),
                    "pagina": pagina,
                    "sobre_fust_por_palavra_chave": sobre_fust,
                    "sumario": r.get("sumario"),
                    "urlTexto": r.get("urlTexto"),
                })
            time.sleep(0.3)

        relevantes = [a for a in achados if a["sobre_fust_por_palavra_chave"]]
        paginas_relevantes = sorted({a["pagina"] for a in relevantes if a["pagina"]})
        paginas_todas = sorted({a["pagina"] for a in achados if a["pagina"]})

        print(f"  {len(achados)} discurso(s) no total dos {len(DEPUTADOS)} deputados "
              f"consultados, {len(relevantes)} batendo palavra-chave do FUST")
        if paginas_relevantes:
            faixa = (min(paginas_relevantes), max(paginas_relevantes))
            print(f"  páginas (só FUST): {paginas_relevantes}  "
                  f"-> faixa {faixa[0]}-{faixa[1]}"
                  + ("  [IGUAL ao despacho, nada novo]"
                     if faixa == (alvo["pagina_despacho"], alvo["pagina_despacho"])
                     else "  [MAIS AMPLA que o despacho]"))
            for a in relevantes:
                print(f"    pág {a['pagina']:>6}  {a['tipoDiscurso']:16s} {a['deputado']}")
        else:
            print("  nenhum discurso batendo palavra-chave do FUST entre os deputados "
                  "consultados -- faixa continua sendo só a página do despacho "
                  f"({alvo['pagina_despacho']})")
        if paginas_todas and paginas_todas != paginas_relevantes:
            print(f"  (outras páginas desses deputados nesse dia, não ligadas ao FUST "
                  f"por palavra-chave: {sorted(set(paginas_todas) - set(paginas_relevantes))})")

        resultado["diarios"].append({
            "arquivo": alvo["arquivo"],
            "data_sessao": alvo["data_sessao"],
            "pagina_despacho_original": alvo["pagina_despacho"],
            "paginas_fust_encontradas": paginas_relevantes,
            "faixa_fust": [min(paginas_relevantes), max(paginas_relevantes)] if paginas_relevantes else None,
            "discursos": achados,
        })

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\narquivo irmão gravado em: {SAIDA.relative_to(RAIZ)}")
    print(f"original NÃO alterado: {ORIGINAL.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
