#!/usr/bin/env python3
"""
Audita a trilha de evidência das duas codificações.

O instrumento manda copiar, em `trecho_evidencia`, um trecho contíguo de uma
das janelas apresentadas ao codificador naquele item. Este script confere se
isso foi cumprido, e, quando não foi, classifica o desvio.

A verificação é comparação de cadeias de caracteres, sem nenhum julgamento.
Ela responde se a evidência registrada corresponde a texto real do documento
correto. Ela não responde se o nível atribuído a essa evidência está correto:
isso é julgamento, e está fora do que este script mede.

Categorias de resultado, aplicadas na ordem em que aparecem:

    ok_janela_estrito       o trecho está, caractere por caractere, em uma
                            janela do próprio item
    ok_janela_normalizado   idem, após colapsar espaços em branco e unificar
                            variantes tipográficas de aspas e apóstrofos
    fora_da_janela          o trecho está no próprio documento, mas em passagem
                            que não foi apresentada ao codificador
    costurada_real          o trecho une passagens separadas por reticências, e
                            todos os fragmentos existem no próprio documento
    costurada_parcial       idem, mas só parte dos fragmentos foi localizada
    corte_interno           o começo ou o fim do trecho existe no próprio
                            documento, com supressão não sinalizada no meio
    outro_documento         o trecho existe, mas em outro documento do corpus:
                            atribuição ao documento errado
    nao_confere             o trecho não foi localizado em nenhum documento
    sem_trecho              o item não registra trecho
    item_sem_fonte          o item codificado não tem lote de origem

As três últimas linhas da tabela são as que importam para a confiabilidade:
`outro_documento` e `nao_confere` são erro, as demais são desvio de forma sobre
texto real.

    python3 coding/verificar_trechos.py
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent

import sys as _sys
_sys.path.insert(0, str(AQUI.parent))
import recorte
RAIZ = AQUI.parent
SAIDA = AQUI / "verificacao_trechos.csv"
SAIDA_CRITICAS = AQUI / "verificacao_falhas_criticas.csv"

ELIPSE = re.compile(r"\.\.\.|…|\[\.\.\.\]")
MIN_FRAGMENTO = 15
PONTAS = 60

ASPAS = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "´": "'", "`": "'", "′": "'", "″": '"',
}

ORDEM = ["ok_janela_estrito", "ok_janela_normalizado", "fora_da_janela",
         "costurada_real", "costurada_parcial", "corte_interno",
         "outro_documento", "nao_confere", "sem_trecho", "item_sem_fonte"]

ERRO = {"outro_documento", "nao_confere"}
DESVIO = {"fora_da_janela", "costurada_real", "costurada_parcial", "corte_interno"}


def _preparar_lotes():
    spec = importlib.util.spec_from_file_location("pl", AQUI / "preparar_lotes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    for k, v in ASPAS.items():
        s = s.replace(k, v)
    s = s.replace("''", '"')
    return re.sub(r"\s+", " ", s).strip()


def esqueleto(s: str) -> str:
    """Reduz a cadeia a letras e dígitos minúsculos: o teste mais permissivo
    possível, imune a hifenização, quebra de linha e pontuação do extrator."""
    return re.sub(r"[^0-9a-z]", "", unicodedata.normalize("NFKD", s).lower())


def carregar_janelas() -> dict[str, dict]:
    fonte: dict[str, dict] = {}
    for arq in sorted((AQUI / "lotes").glob("*_lote_*.json")):
        for par in json.loads(arq.read_text(encoding="utf-8")).get("pares", []):
            fonte[par["par_id"]] = {
                "janelas": [j["trecho"] for j in par.get("janelas", [])],
                "unit_id": par["unit_id"],
            }
    return fonte


def carregar_dispositivos() -> dict[str, dict]:
    fonte: dict[str, dict] = {}
    for arq in sorted((AQUI / "lotes_normativo").glob("*_lote_*.json")):
        for d in json.loads(arq.read_text(encoding="utf-8")).get("dispositivos", []):
            fonte[d["disp_id"]] = {"janelas": [d.get("trecho", "")],
                                   "unit_id": d.get("diploma", "")}
    return fonte


def carregar_corpos(pl) -> dict[tuple[str, str], str]:
    corpos: dict[tuple[str, str], str] = {}
    for caso, cfg in pl.CASOS.items():
        raiz = RAIZ / cfg["raiz"]
        with (RAIZ / cfg["indice"]).open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                nome = (r.get("corpus_file") or "").strip()
                if not nome:
                    continue
                cf = raiz / nome
                if not cf.is_file():
                    continue
                texto = cf.read_text(encoding="utf-8", errors="replace")
                corpos[(caso, r["id"])] = esqueleto(texto[pl.inicio_do_corpo(texto):])
    return corpos


def classificar(trecho: str, fonte: dict | None, caso: str,
                corpos: dict[tuple[str, str], str]) -> str:
    if fonte is None:
        return "item_sem_fonte"
    if not (trecho or "").strip():
        return "sem_trecho"

    janelas = fonte["janelas"]
    if any(trecho in j for j in janelas):
        return "ok_janela_estrito"
    tn = normalizar(trecho)
    if any(tn in normalizar(j) for j in janelas):
        return "ok_janela_normalizado"

    e = esqueleto(trecho)
    proprio = corpos.get((caso, fonte["unit_id"]))
    if proprio is None:
        proprio = esqueleto(" ".join(janelas))
    if e and e in proprio:
        return "fora_da_janela"

    if ELIPSE.search(trecho):
        frags = [esqueleto(p) for p in ELIPSE.split(trecho)]
        frags = [p for p in frags if len(p) >= MIN_FRAGMENTO]
        if frags and all(p in proprio for p in frags):
            return "costurada_real"
        if frags and any(p in proprio for p in frags):
            return "costurada_parcial"
        return "nao_confere"

    if e and any(e in d for (c, _), d in corpos.items() if c == caso):
        return "outro_documento"
    if e and (e[:PONTAS] in proprio or e[-PONTAS:] in proprio):
        return "corte_interno"
    return "nao_confere"


def auditar(eixo, arquivo, chave, col_nivel, fonte, corpos) -> list[dict]:
    with arquivo.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if "unit_id" in (linhas[0] if linhas else {}):
        linhas = recorte.filtrar_pares(linhas)   # recorte declarado em recorte.py
    saida = []
    for l in linhas:
        ident = l[chave]
        caso = l.get("caso", "")
        status = classificar(l.get("trecho_evidencia", ""), fonte.get(ident), caso, corpos)
        saida.append({
            "eixo": eixo, "id": ident, "caso": caso,
            "pertinencia": l.get("pertinencia", ""),
            "nivel": l.get(col_nivel, ""),
            "status": status,
            "n_caracteres": len(l.get("trecho_evidencia") or ""),
            "trecho_evidencia": l.get("trecho_evidencia", ""),
        })
    return saida


def resumir(nome: str, linhas: list[dict]) -> None:
    print(f"=== {nome}: {len(linhas)} itens codificados ===")
    cont = Counter(l["status"] for l in linhas)
    for st in ORDEM:
        if cont[st]:
            print(f"  {st:24s} {cont[st]:5d}   {cont[st] / len(linhas) * 100:5.1f}%")
    com = [l for l in linhas if l["status"] not in ("sem_trecho", "item_sem_fonte")]
    if not com:
        print()
        return
    ok = sum(1 for l in com if l["status"].startswith("ok_janela"))
    desvio = sum(1 for l in com if l["status"] in DESVIO)
    erro = sum(1 for l in com if l["status"] in ERRO)
    print(f"  ---- sobre os {len(com)} itens com trecho registrado:")
    print(f"       casam com a janela apresentada:      {ok:5d}  {ok / len(com) * 100:6.2f}%")
    print(f"       texto real do documento correto:     {ok + desvio:5d}  {(ok + desvio) / len(com) * 100:6.2f}%")
    print(f"       erro de evidência:                   {erro:5d}  {erro / len(com) * 100:6.2f}%")
    print()


def main() -> None:
    pl = _preparar_lotes()
    corpos = carregar_corpos(pl)
    print(f"documentos do corpus carregados: {len(corpos)}\n")

    disc = auditar("discursivo", AQUI / "pares_eixo_discursivo.csv", "par_id",
                   "nivel_do_par", carregar_janelas(), corpos)
    norm = auditar("normativo", AQUI / "dispositivos_eixo_normativo.csv", "disp_id",
                   "nivel_do_dispositivo", carregar_dispositivos(), corpos)

    resumir("eixo discursivo", disc)
    resumir("eixo normativo", norm)

    todas = disc + norm
    cols = [c for c in todas[0] if c != "trecho_evidencia"]
    with SAIDA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(todas)

    criticas = [l for l in todas if l["status"] in ERRO]
    with SAIDA_CRITICAS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(todas[0].keys()))
        w.writeheader()
        w.writerows(criticas)

    print(f"itens com erro de evidência: {len(criticas)}")
    for l in criticas:
        print(f"  [{l['caso']}] {l['id']}  ({l['status']}, nível {l['nivel']})")
        print(f"      {l['trecho_evidencia'][:150]}")
    print(f"\ngravado: {SAIDA.name}  e  {SAIDA_CRITICAS.name}")


if __name__ == "__main__":
    main()
