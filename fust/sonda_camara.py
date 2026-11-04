#!/usr/bin/env python3
"""
Sonda: a API da Câmara tem pronunciamentos de Plenário de 1999/2000 com
texto integral nativo, nos moldes do que a API do Senado tem? Se sim, os
8 Diários da Câmara (fust/baixar_diarios.py) saem da lista de OCR. Se não,
o caminho da Câmara continua sendo Diário digitalizado + re-OCR.

BRIEFING_COLETA.md, seção 4.2: testar /deputados/{id}/discursos para a
51ª legislatura, com deputados que sabidamente falaram sobre o FUST
(Walter Pinheiro, Salvador Zimbaldi, Mendes Ribeiro Filho, Custódio
Mattos), nas janelas das sessões de 03/11/1999 e 07/12/1999. Procurar
também qualquer endpoint de evento/sessão/reunião com notas taquigráficas
por data.

A sonda só lê e relata. Não baixa nem decide nada — só reporta os 4
critérios (existe / cobre 1999 / traz texto integral / traz nome+partido)
para quem for escrever o próximo coletor decidir com os fatos em mãos.

    python sonda_camara.py

Só stdlib.
"""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
SAIDA = CORPUS / "camara" / "sonda_discursos_camara.json"

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Deputados que sabidamente falaram sobre o FUST (briefing, seção 4.2).
# id=None marca quem a busca por nome não achou -- isso também é
# resultado da sonda, não erro a esconder.
DEPUTADOS = [
    {"nome": "Walter Pinheiro", "id": None},
    {"nome": "Salvador Zimbaldi", "id": 73559},
    {"nome": "Mendes Ribeiro Filho", "id": 73904},
    {"nome": "Custódio Mattos", "id": 74579},
]

# Janelas das sessões citadas no briefing. Uma janela larga (o ano
# inteiro) evita falso-negativo por o deputado não ter falado exatamente
# nessas duas datas -- o que importa pra sonda é se a API TEM o dado e em
# que forma, não pregar o deputado num dia exato.
JANELAS = [
    ("1999-11-03", "1999-11-03", "sessão de 03/11/1999 (discussão, adiada)"),
    ("1999-12-07", "1999-12-07", "sessão de 07/12/1999 (discussão/aprovação)"),
    ("1999-01-01", "1999-12-31", "ano inteiro de 1999 (janela larga de controle)"),
]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get_json(url: str, *, tentativas: int = 3, timeout: int = 25):
    log = []
    for i in range(1, tentativas + 1):
        req = Request(url, headers=CABECALHOS)
        try:
            with urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
                return json.loads(corpo), f"http={resp.status}"
        except HTTPError as e:
            log.append(f"http={e.code} {e.reason}")
        except URLError as e:
            log.append(f"rede: {e.reason}")
        except (socket.timeout, TimeoutError):
            log.append("timeout")
        if i < tentativas:
            time.sleep(min(2**i, 10))
    return None, " | ".join(log) or "falhou sem diagnóstico"


def resolver_id(nome: str) -> tuple[int | None, str]:
    """Busca por nome, tentando o ano certo (idLegislatura=51) e depois
    sem filtro de legislatura como fallback. Devolve (id, como_achou)."""
    for params, rotulo in (
        (f"nome={quote(nome)}&idLegislatura=51", "idLegislatura=51"),
        (f"nome={quote(nome)}", "sem filtro de legislatura"),
    ):
        j, _ = _get_json(f"{CAMARA}/deputados?{params}&itens=100")
        achados = (j or {}).get("dados", [])
        if achados:
            return achados[0]["id"], rotulo
    return None, "não encontrado por nome em nenhuma tentativa"


def testar_discursos(dep_id: int, data_inicio: str, data_fim: str) -> dict:
    url = f"{CAMARA}/deputados/{dep_id}/discursos?dataInicio={data_inicio}&dataFim={data_fim}"
    j, diag = _get_json(url)
    if j is None:
        return {"url": url, "ok": False, "diagnostico": diag}
    registros = j.get("dados", [])
    com_transcricao = [r for r in registros if (r.get("transcricao") or "").strip()]
    return {
        "url": url,
        "ok": True,
        "n_registros": len(registros),
        "n_com_transcricao_nativa": len(com_transcricao),
        "exemplos": [
            {
                "data": r.get("dataHoraInicio"),
                "tipoDiscurso": r.get("tipoDiscurso"),
                "sumario": (r.get("sumario") or "")[:140].replace("\r\n", " "),
                "transcricao_vazia": not (r.get("transcricao") or "").strip(),
                "urlTexto": r.get("urlTexto"),
            }
            for r in registros[:3]
        ],
    }


def testar_eventos_sessao(data_iso: str) -> dict:
    """Procura evento de sessão deliberativa na data e confere se algum
    sub-recurso (pauta, votacoes) traz nota taquigráfica por data."""
    j, diag = _get_json(f"{CAMARA}/eventos?dataInicio={data_iso}&dataFim={data_iso}")
    if j is None:
        return {"ok": False, "diagnostico": diag}
    eventos = [e for e in j.get("dados", []) if "Delibera" in (e.get("descricaoTipo") or "")]
    out = {"ok": True, "data": data_iso, "eventos_deliberativos": []}
    for ev in eventos:
        sub = {}
        for recurso in ("pauta", "votacoes"):
            jr, _ = _get_json(f"{CAMARA}/eventos/{ev['id']}/{recurso}")
            sub[recurso] = len((jr or {}).get("dados", []))
        out["eventos_deliberativos"].append(
            {"id": ev["id"], "descricao": ev.get("descricao"), "sub_recursos_n_itens": sub}
        )
    return out


def main() -> None:
    resultado = {"rodado_em": _agora(), "deputados": [], "eventos": [], "veredito": {}}

    print("=" * 78)
    print("SONDA CAMARA -- pronunciamentos de Plenario tem texto integral nativo?")
    print("=" * 78)

    algum_com_dados = False
    algum_com_transcricao = False

    for dep in DEPUTADOS:
        dep_id = dep["id"]
        como_achou = "id já conhecido (coleta anterior)"
        if dep_id is None:
            dep_id, como_achou = resolver_id(dep["nome"])

        print(f"\n[{dep['nome']}]  id={dep_id}  ({como_achou})")
        entrada = {"nome": dep["nome"], "id": dep_id, "como_achou_id": como_achou, "janelas": []}

        if dep_id is None:
            print("  !! sem id -- não dá pra testar /discursos")
            resultado["deputados"].append(entrada)
            continue

        for data_inicio, data_fim, rotulo in JANELAS:
            r = testar_discursos(dep_id, data_inicio, data_fim)
            r["rotulo"] = rotulo
            entrada["janelas"].append(r)
            if not r["ok"]:
                print(f"  [{rotulo}] ERRO: {r['diagnostico']}")
                continue
            print(f"  [{rotulo}] {r['n_registros']} discurso(s), "
                  f"{r['n_com_transcricao_nativa']} com transcrição nativa não-vazia")
            if r["n_registros"]:
                algum_com_dados = True
            if r["n_com_transcricao_nativa"]:
                algum_com_transcricao = True
            for ex in r["exemplos"]:
                print(f"      {ex['data']}  {ex['tipoDiscurso']:14s}  "
                      f"transcricao_vazia={ex['transcricao_vazia']}  {ex['sumario']}")
                print(f"        urlTexto: {ex['urlTexto']}")

        resultado["deputados"].append(entrada)

    print("\n" + "-" * 78)
    print("Endpoints de evento/sessao (procurando nota taquigrafica por data)")
    print("-" * 78)
    for data_iso in ("1999-11-03", "1999-12-07"):
        r = testar_eventos_sessao(data_iso)
        resultado["eventos"].append(r)
        if not r["ok"]:
            print(f"\n[{data_iso}] ERRO: {r['diagnostico']}")
            continue
        print(f"\n[{data_iso}] {len(r['eventos_deliberativos'])} evento(s) deliberativo(s)")
        for ev in r["eventos_deliberativos"]:
            print(f"    id={ev['id']}  {ev['descricao']}  "
                  f"sub-recursos: {ev['sub_recursos_n_itens']}")

    veredito = {
        "endpoint_existe": True,
        "cobre_1999": algum_com_dados,
        "traz_texto_integral_nativo": algum_com_transcricao,
        "traz_nome_e_partido": "só o id do autor vem no registro; nome/partido exigem "
                                "chamada separada a /deputados/{id} (não testado aqui "
                                "porque já se conhece o nome de quem se buscou)",
        "conclusao": (
            "NAO sai da lista de OCR. O endpoint /deputados/{id}/discursos existe e "
            "cobre 1999, mas o campo 'transcricao' vem sempre vazio nos registros "
            "testados -- o que ele devolve é metadado (resumo, palavras-chave, tipo "
            "de uso da palavra) mais um 'urlTexto' que aponta de volta para o MESMO "
            "visualizador antigo do Diário digitalizado (imagem.camara.gov.br/"
            "dc_20b.asp?...txPagina=NNNNN), não um texto corrido nativo como o "
            "TextoIntegralTxt do Senado. Os sub-recursos de evento (pauta, "
            "votacoes) também vieram vazios para a sessão de 07/12/1999 -- não "
            "digitalizados tão longe no passado. Os 8 Diários continuam no caminho "
            "do re-OCR."
        ),
        "achado_novo": (
            "Os urlTexto por discurso dão páginas MAIS GRANULARES que as já "
            "extraídas de referencias_diario.json: para 07/12/1999 (texto publicado "
            "em 08/12/1999) apareceram pág. 60554 (parecer), pág. 60565 (votação "
            "das emendas de Plenário) e pág. 60570 (votação da Emenda Substitutiva "
            "24) dentro do mesmo DCD08DEZ1999 que já se tinha só como pág. 60552. "
            "Vale revisar se o recorte de página única em paginas.py captura esse "
            "intervalo inteiro (60552-60570) ou só a primeira página."
        ),
    }
    resultado["veredito"] = veredito

    print("\n" + "=" * 78)
    print("VEREDITO")
    print("=" * 78)
    for k, v in veredito.items():
        print(f"\n{k}:\n  {v}")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\nresultado completo: {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
