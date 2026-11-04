#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coleta das fontes primarias brasileiras do FUST (1997-2000).

  PL 3808/1997 (Camara, idProposicao=38109)
    -> PLC 60/1999 (Senado, materia=42696)
      -> Lei 9.998/2000

O que faz:
  1. Baixa metadados e tramitacoes pela API da Camara e do Senado
     (Senado via /processo/*, que substitui /materia/* -- descontinuado em
     2025-03-18, com desativacao completa prevista para 2026-02-01)
  2. Resolve o inteiro teor da proposicao: para proposicoes antigas a API
     da Camara nao devolve um PDF direto, devolve uma pagina HTML com
     meta-refresh ate o visualizador antigo de Diarios, que por sua vez
     redireciona (HTTP) e depois meta-refresh de novo ate o PDF real do
     Diario onde o texto foi publicado. O script segue essa cadeia.
  3. Deriva as datas de sessao das tramitacoes e monta as URLs dos Diarios
  4. Baixa os Diarios (so com --baixar-diarios)
  5. Opcionalmente roda OCR (--redo-ocr -l por) nos Diarios baixados, porque
     a camada de texto original desses PDFs vem com palavras coladas e
     e inutilizavel para busca (medido: busca por "universalização" e
     "telecomunicações" num Diario de 2000 nao encontrou quase nada)
  6. Escreve um manifesto JSON com procedencia, sha256, tamanho, paginas e
     qualidade da camada de texto de cada arquivo

Todo download e verificado por magic bytes antes de entrar no manifesto:
se o servidor devolver uma pagina de erro/redirecionamento/desafio
anti-bot com HTTP 200 (como acontece com o inteiro teor antigo da Camara
e, hoje, com o endpoint de documentos do Senado), o arquivo e isolado com
sufixo .suspeito.html em vez de ser salvo como se fosse um PDF valido.

Uso:
    pip install requests pypdf
    python3 coleta_brasil.py                      # so metadados + lista o que existe
    python3 coleta_brasil.py --baixar-diarios     # baixa tambem os Diarios (pesado)
    python3 coleta_brasil.py --baixar-diarios --ocr-diarios  # + reOCR em portugues
    python3 coleta_brasil.py --ate 2000-12-31     # limita o periodo

Para o reOCR e preciso ter o binario ocrmypdf instalado (que por sua vez
precisa de tesseract com o pacote de idioma "por"):
    macOS:  brew install ocrmypdf tesseract-lang
    Debian: apt install ocrmypdf tesseract-ocr-por

Tudo vai para ./corpus_fust/ e o script e retomavel: nao rebaixa o que ja tem.

LIMITACAO CONHECIDA (nao resolvida por este script): o endpoint de
documentos do Senado (sdleg-getter/documento?dm=...), que e o link real
por tras de todo "urlDocumento"/"UrlTexto" retornado pela API, hoje exige
passar por um desafio de verificacao anti-bot em JavaScript ("Verificação
de segurança — Senado Federal") antes de liberar o PDF. Uma requisicao
simples (requests/curl) recebe sempre essa pagina de desafio, nunca o
PDF -- isso nao e um bug deste script, e uma barreira anti-scraping do
lado do servidor. A rota recomendada e baixar esses documentos manualmente
num navegador (a lista de URLs pendentes aparece no fim da execucao) e
colocar os arquivos em corpus_fust/senado/documentos_manuais/.
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit("Falta requests. Rode: pip install requests")

RAIZ = "corpus_fust"
UA = {"User-Agent": "pesquisa-academica-tcc/1.0 (contato: ruthgs@al.insper.edu.br)"}
TIMEOUT = 60

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
ID_PROPOSICAO = 38109          # PL 3808/1997
ID_MATERIA_SENADO = 42696      # PLC 60/1999

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
         "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

MANIFESTO = []
PENDENTES_MANUAIS = []   # URLs que exigiram navegador (desafio anti-bot etc.)


def pasta(*partes):
    p = os.path.join(RAIZ, *partes)
    os.makedirs(p, exist_ok=True)
    return p


def titulo(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def get_json(url, **kw):
    try:
        r = requests.get(url, headers={**UA, "Accept": "application/json"},
                         timeout=TIMEOUT, **kw)
    except Exception as e:
        print(f"  ERRO rede: {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}  {url}")
        return None
    try:
        return r.json()
    except Exception:
        print(f"  resposta nao-JSON em {url} ({len(r.text)} chars)")
        return None


def qualidade_pdf(caminho):
    """Mede a camada de texto. Retorna dict ou None."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        r = PdfReader(caminho)
    except Exception as e:
        return {"erro": str(e)}
    n = len(r.pages)
    if n == 0:
        return {"paginas": 0}
    idx = sorted(set([0, n // 4, n // 2, (3 * n) // 4, n - 1]))
    idx = [i for i in idx if 0 <= i < n]
    chars = 0
    colados = 0
    for i in idx:
        try:
            t = r.pages[i].extract_text() or ""
        except Exception:
            t = ""
        chars += len(t)
        colados += len(re.findall(r"[a-zà-ÿ]{18,}", t))
    media = chars / len(idx)
    if media < 200:
        v = "sem_texto_precisa_ocr"
    elif colados > 3:
        v = "texto_sujo_precisa_reocr"
    else:
        v = "texto_utilizavel"
    return {"paginas": n, "chars_por_pagina": round(media), "tokens_colados": colados,
            "veredito": v}


def _eh_pdf_de_verdade(caminho):
    """Confere o cabecalho magico, nao so a extensao do arquivo."""
    try:
        with open(caminho, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def resolver_meta_refresh(html):
    """Acha a URL de destino num <meta http-equiv="refresh" content="N;URL=...">."""
    m = re.search(r'URL=([^"\'>]+)', html, re.I)
    return m.group(1).strip() if m else None


def baixar_inteiro_teor_camara(url_it, pasta_destino):
    """
    urlInteiroTeor de proposicoes antigas (anos 1990) nao devolve PDF
    direto: devolve uma pagina Wicket com meta-refresh para o visualizador
    antigo (imagem.camara.gov.br/dc_20.asp...), que redireciona por HTTP
    ate montaPdf.asp, que por sua vez tem um SEGUNDO meta-refresh ate o
    PDF real do Diario onde o texto foi publicado, com um fragmento
    #page=N indicando a pagina. Essa cadeia so existe por causa do jeito
    como a Camara arquivou textos antigos; retorna (url_pdf_final, pagina).
    """
    try:
        r1 = requests.get(url_it, headers=UA, timeout=TIMEOUT)
    except Exception as e:
        print(f"  ERRO ao abrir urlInteiroTeor: {e}")
        return None, None
    if r1.content[:5] == b"%PDF-":
        return url_it, None   # proposicoes mais novas ja devolvem o PDF direto

    alvo1 = resolver_meta_refresh(r1.text)
    if not alvo1:
        print("  !! pagina de inteiro teor sem meta-refresh reconhecivel "
              "(o formato pode ter mudado de novo)")
        return None, None
    print(f"  (1o redirecionamento) {alvo1}")

    try:
        r2 = requests.get(alvo1, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        print(f"  ERRO ao seguir 1o redirecionamento: {e}")
        return None, None
    if r2.content[:5] == b"%PDF-":
        return r2.url, None

    alvo2 = resolver_meta_refresh(r2.text)
    if not alvo2:
        print("  !! 2o meta-refresh (pagina montaPdf.asp) nao encontrado")
        return None, None
    print(f"  (2o redirecionamento) {alvo2}")

    pagina = None
    m = re.search(r"#page=(\d+)", alvo2)
    if m:
        pagina = int(m.group(1))
    url_pdf = alvo2.split("#")[0]
    return url_pdf, pagina


def baixar(url, destino, descricao, origem):
    """Baixa se nao existir. Registra no manifesto. Retorna caminho ou None."""
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        print(f"  (ja existe) {os.path.basename(destino)}")
    else:
        try:
            r = requests.get(url, headers=UA, timeout=180, stream=True)
        except Exception as e:
            print(f"  ERRO ao baixar {url}: {e}")
            return None
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}  {url}")
            return None
        tmp = destino + ".parcial"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        os.replace(tmp, destino)
        print(f"  baixado {os.path.basename(destino)} "
              f"({os.path.getsize(destino)/1_000_000:.1f} MB)")

    if destino.lower().endswith(".pdf") and not _eh_pdf_de_verdade(destino):
        with open(destino, "rb") as f:
            inicio = f.read(200)
        suspeito = destino + ".suspeito.html"
        os.replace(destino, suspeito)
        eh_desafio = b"sdleg-getter" in url.encode() and (
            b"desafio" in inicio.lower() or b"seguran" in inicio.lower()
            or b"_challenge" in inicio.lower() or b"<!doctype" in inicio.lower()
        )
        print(f"  !! {os.path.basename(destino)} nao e um PDF de verdade "
              f"(comeca com {inicio[:40]!r}). Provavelmente pagina de "
              f"erro/redirecionamento HTML ou desafio anti-bot, nao o "
              f"documento. Isolado em {os.path.basename(suspeito)}, "
              f"NAO registrado no manifesto como PDF valido.")
        if "sdleg-getter" in url:
            print("     -> este e o padrao do desafio anti-bot do Senado "
                  "(verificacao em JavaScript). Baixe manualmente num "
                  "navegador e salve em "
                  "corpus_fust/senado/documentos_manuais/.")
            PENDENTES_MANUAIS.append({"url": url, "descricao": descricao,
                                       "motivo": "desafio anti-bot (sdleg-getter)"})
        else:
            PENDENTES_MANUAIS.append({"url": url, "descricao": descricao,
                                       "motivo": "HTTP 200 com conteudo nao-PDF"})
        return None

    h = hashlib.sha256()
    with open(destino, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    reg = {
        "arquivo": os.path.relpath(destino, RAIZ),
        "descricao": descricao,
        "origem": origem,
        "url": url,
        "bytes": os.path.getsize(destino),
        "sha256": h.hexdigest(),
        "baixado_em": datetime.now().isoformat(timespec="seconds"),
    }
    if destino.lower().endswith(".pdf"):
        q = qualidade_pdf(destino)
        if q:
            reg["pdf"] = q
            print(f"    -> {q.get('paginas')} pag | {q.get('veredito')}")
    MANIFESTO.append(reg)
    return destino


# ------------------------------------------------------------------ CAMARA
#
# id ja confirmado da Emenda Substitutiva de Plenario no 24: e o texto que
# de fato foi aprovado na Camara e virou PLC 60/1999 no Senado (confirmado
# no parecer MATE_TI_29602.pdf da Comissao de Infraestrutura: "a proposicao
# que agora analisamos foi votada na Camara dos Deputados, na forma de uma
# Emenda Substitutiva de Plenario (No 24)"). Aparece em /relacionadas como
# "EMP 24/0" com id=68783; guardamos aqui como fallback caso /relacionadas
# por algum motivo nao traga de novo.
ID_EMENDA_SUBSTITUTIVA_24 = 68783


def _salvar(d, nome, obj):
    with open(os.path.join(d, nome), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return os.path.join(d, nome)


def buscar_proposicao_por_numero(sigla_tipo, numero, ano):
    """Acha o idProposicao a partir de sigla+numero+ano (p.ex. PL 3938/1997).
    Nao aparece em /relacionadas (que so lista emendas), por isso precisa
    de busca separada."""
    j = get_json(f"{CAMARA}/proposicoes",
                 params={"siglaTipo": sigla_tipo, "numero": numero, "ano": ano})
    if j and isinstance(j.get("dados"), list) and j["dados"]:
        return j["dados"][0].get("id")
    return None


def extrair_referencias_diario(despacho):
    """
    Acha citacoes a Diario dentro do texto livre do campo despacho, tipo
    'DCD 14 11 97 PAG 36602 COL 01' -- confirmado contra despachos reais
    desta proposicao (DCD = Diario da Camara; tambem aparecem DOFC e DCN
    para a publicacao da lei/veto). Formatos variam (data com espaco ou
    barra, ano com 2 ou 4 digitos, PAG/PÁG/pág., com ou sem pontuacao) e
    um despacho pode ter mais de uma citacao (ex: publicacao + republicacao
    "REP:"). Da data E pagina exatas -- evita abrir o Diario inteiro so
    para achar o trecho certo.
    """
    padrao = re.compile(
        r"(DCD|DOFC|DCN)\s+(\d{1,2})[/\s]+(\d{1,2})[/\s]+(\d{2,4}),?\s*"
        r"P[ÁA]G\.?\s*(\d+)(?:,?\s*COL\.?\s*(\d+))?",
        re.IGNORECASE,
    )
    refs = []
    for m in padrao.finditer(despacho or ""):
        serie, dd, mm, yy, pag, col = m.groups()
        yy = int(yy)
        ano = yy if yy >= 100 else (1900 + yy if yy >= 50 else 2000 + yy)
        try:
            data_iso = f"{ano:04d}-{int(mm):02d}-{int(dd):02d}"
            datetime.strptime(data_iso, "%Y-%m-%d")
        except ValueError:
            continue
        refs.append({"serie": serie.upper(), "data": data_iso, "pagina": int(pag),
                     "coluna": col, "trecho_despacho": m.group(0)})
    return refs


def buscar_e_salvar_proposicao_relacionada(id_prop, partes_pasta, descricao):
    """Busca proposicao + tramitacoes de uma proposicao relacionada (emenda,
    apensado etc.) e grava assim que cada parte chega -- nada pendente
    para o final."""
    sub = pasta(*partes_pasta)
    j = get_json(f"{CAMARA}/proposicoes/{id_prop}")
    if not (j and j.get("dados")):
        print(f"  !! nao consegui buscar {descricao} (id={id_prop})")
        return
    dd = j["dados"]
    _salvar(sub, "proposicao.json", dd)
    print(f"  {descricao}: {dd.get('siglaTipo')} {dd.get('numero')}/{dd.get('ano')} "
          f"(id={id_prop})")
    print(f"    ementa: {str(dd.get('ementa'))[:140]}")
    j = get_json(f"{CAMARA}/proposicoes/{id_prop}/tramitacoes")
    if j and isinstance(j.get("dados"), list):
        _salvar(sub, "tramitacoes.json", j["dados"])
        print(f"    {len(j['dados'])} tramitacoes")


def camara(args):
    titulo("CAMARA DOS DEPUTADOS - PL 3808/1997 (id %d)" % ID_PROPOSICAO)
    d = pasta("camara")
    datas = set()
    refs_diario = []

    # 1) os JSONs baratos e confiaveis primeiro -- cada um gravado assim
    #    que chega, nenhum download ainda.
    dados = None
    j = get_json(f"{CAMARA}/proposicoes/{ID_PROPOSICAO}")
    if j and j.get("dados"):
        dados = j["dados"]
        _salvar(d, "proposicao.json", dados)
        print(f"  {dados.get('siglaTipo')} {dados.get('numero')}/{dados.get('ano')}")
        print(f"  ementa: {str(dados.get('ementa'))[:140]}")

    tr = []
    j = get_json(f"{CAMARA}/proposicoes/{ID_PROPOSICAO}/tramitacoes")
    if j and isinstance(j.get("dados"), list):
        tr = j["dados"]
        _salvar(d, "tramitacoes.json", tr)
        print(f"\n  {len(tr)} tramitacoes registradas")
        com_despacho = [t for t in tr if (t.get("despacho") or "").strip()]
        print(f"  {len(com_despacho)} com despacho textual")
        for t in tr:
            dh = (t.get("dataHora") or "")[:10]
            if dh:
                datas.add(dh)
            for ref in extrair_referencias_diario(t.get("despacho")):
                ref["tramitacao_data"] = dh
                ref["tramitacao_descricao"] = t.get("descricaoTramitacao")
                refs_diario.append(ref)
        if datas:
            print(f"  periodo: {min(datas)} a {max(datas)}")
        print("\n  primeiras tramitacoes:")
        for t in tr[:6]:
            print(f"    {(t.get('dataHora') or '')[:10]}  {t.get('siglaOrgao',''):12s} "
                  f"{str(t.get('descricaoTramitacao'))[:60]}")
        if refs_diario:
            _salvar(d, "referencias_diario.json", refs_diario)
            print(f"\n  {len(refs_diario)} referencia(s) a Diario extraidas dos "
                  f"despachos (data + pagina exata, sem adivinhar):")
            for r in refs_diario:
                print(f"    {r['serie']}  {r['data']}  pag {r['pagina']}"
                      + (f" col {r['coluna']}" if r['coluna'] else ""))

    autores = []
    j = get_json(f"{CAMARA}/proposicoes/{ID_PROPOSICAO}/autores")
    if j and isinstance(j.get("dados"), list):
        autores = j["dados"]
        _salvar(d, "autores.json", autores)
        print(f"\n  autores: " + ", ".join(a.get("nome", "?") for a in autores[:5]))

    relacionadas = []
    j = get_json(f"{CAMARA}/proposicoes/{ID_PROPOSICAO}/relacionadas")
    if j and isinstance(j.get("dados"), list):
        relacionadas = j["dados"]
        _salvar(d, "relacionadas.json", relacionadas)
        print(f"  relacionadas: {len(relacionadas)}")
        for p in relacionadas[:10]:
            print(f"    {p.get('siglaTipo')} {p.get('numero')}/{p.get('ano')}  id={p.get('id')}")

    # 2) inteiro teor: resolve a cadeia de redirecionamentos mas NAO baixa
    #    o PDF. Ja verificamos (OCR do PDF resolvido, DCD01SET1997.pdf,
    #    buscando "3808" e "9998" tolerando ruido) que o arquivo apontado
    #    nao contem o texto do PL 3808/1997 -- ou a pagina indicada esta
    #    errada, ou o codteor da API esta associado ao Diario errado.
    #    Guardamos so a resolucao, com aviso explicito, para nao duplicar
    #    um PDF de 20MB que sabemos ser o arquivo errado.
    print()
    url_it = (dados or {}).get("urlInteiroTeor")
    if url_it:
        print(f"  inteiro teor (link da API): {url_it}")
        url_pdf, pagina = baixar_inteiro_teor_camara(url_it, pasta("diarios_camara"))
        nota = {
            "url_api_original": url_it,
            "url_pdf_resolvida": url_pdf,
            "pagina_no_diario": pagina,
            "pdf_baixado": False,
            "nota": ("Cadeia de redirecionamentos resolvida, mas o PDF NAO foi "
                     "baixado de proposito. Verificacao manual (OCR + busca por "
                     "'3808' e '9998' tolerando ruido) mostrou que o arquivo "
                     "resolvido NAO contem o texto do PL 3808/1997 e o sumario "
                     "do Diario nao lista nada de telecomunicacoes -- ou a "
                     "pagina resolvida esta errada, ou o codteor da API aponta "
                     "para o Diario errado. NAO usar este link como fonte do "
                     "inteiro teor sem conferir manualmente antes."),
        }
        if url_pdf:
            print(f"  -> cadeia resolvida para {url_pdf} (pagina {pagina}) -- "
                  f"NAO baixado, ver aviso em inteiro_teor_resolucao.json")
        else:
            print("  !! nao consegui resolver a cadeia de redirecionamentos")
        _salvar(d, "inteiro_teor_resolucao.json", nota)
    else:
        print("  !! a API nao trouxe urlInteiroTeor para esta proposicao")

    # 3) PL 3938/1997 (Poder Executivo), apensado ao PL 3808/1997 -- citado
    #    no parecer MATE_TI_29602.pdf; nao aparece em /relacionadas (que so
    #    lista emendas), por isso precisa de busca por sigla+numero+ano.
    print()
    id_pl3938 = buscar_proposicao_por_numero("PL", 3938, 1997)
    if id_pl3938:
        buscar_e_salvar_proposicao_relacionada(
            id_pl3938, ("camara", "pl3938_1997_apensado"),
            "PL 3938/1997 (Poder Executivo, apensado)")
    else:
        print("  !! nao achei PL 3938/1997 pela busca /proposicoes "
              "(API fora do ar agora, ou os parametros de busca mudaram)")

    # 4) Emenda Substitutiva de Plenario no 24 -- o texto que de fato foi
    #    aprovado na Camara e virou PLC 60/1999 no Senado.
    print()
    id_emp24 = next(
        (p["id"] for p in relacionadas
         if p.get("siglaTipo") == "EMP" and str(p.get("numero")) == "24"),
        ID_EMENDA_SUBSTITUTIVA_24,
    )
    buscar_e_salvar_proposicao_relacionada(
        id_emp24, ("camara", "emp24_substitutivo"),
        "Emenda Substitutiva de Plenario no 24 (texto aprovado na Camara)")

    return sorted(datas), refs_diario


# ------------------------------------------------------------------ SENADO
#
# Os antigos /materia/{id}, /materia/movimentacoes/{id}, /materia/textos/{id},
# /materia/relatorias/{id} e /materia/emendas/{id} trazem um bloco
# "Descontinuacao" (DataDepreciacao 2025-03-18, DataDesativacaoCompleta
# 2026-02-01 -- ja vencida) apontando para os substitutos abaixo, que usam
# o novo "idProcesso" em vez do antigo "codigoMateria":
#   /processo?codigoMateria={codigoMateria}  -> acha o idProcesso
#   /processo/{idProcesso}                   -> substitui materia + movimentacoes
#   /processo/documento?idProcesso=...       -> substitui textos
#   /processo/relatoria?idProcesso=...       -> substitui relatorias
#   /processo/emenda?idProcesso=...          -> substitui emendas
# (confirmado contra a API em 2026-10-04: as rotas antigas ainda respondem,
# mas a nova e a que o proprio Senado aponta como definitiva.)
def senado(args):
    titulo("SENADO FEDERAL - PLC 60/1999 (materia %d)" % ID_MATERIA_SENADO)
    d = pasta("senado")
    datas = set()

    j = get_json(f"{SENADO}/processo", params={"codigoMateria": ID_MATERIA_SENADO})
    if not isinstance(j, list) or not j:
        print("  !! /processo nao devolveu nada para codigoMateria="
              f"{ID_MATERIA_SENADO} -- API pode ter mudado de novo")
        return []
    resumo = j[0]
    id_processo = resumo.get("id")
    with open(os.path.join(d, "processo_resumo.json"), "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)
    print(f"  {resumo.get('identificacao')}  (idProcesso={id_processo})")
    print(f"  apelido: {resumo.get('apelido')}")
    print(f"  norma gerada: {resumo.get('normaGerada')}")
    if not id_processo:
        print("  !! registro sem campo 'id' -- nao da pra seguir pros sub-recursos")
        return []

    rotas = {
        "processo": (f"{SENADO}/processo/{id_processo}", None),
        "documento": (f"{SENADO}/processo/documento", {"idProcesso": id_processo}),
        "relatoria": (f"{SENADO}/processo/relatoria", {"idProcesso": id_processo}),
        "emenda": (f"{SENADO}/processo/emenda", {"idProcesso": id_processo}),
    }
    for nome, (url, params) in rotas.items():
        print(f"\n[{nome}]")
        j = get_json(url, params=params)
        if j is None:
            continue
        with open(os.path.join(d, f"{nome}.json"), "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, indent=2)
        bruto = json.dumps(j, ensure_ascii=False)
        print(f"  salvo ({len(bruto):,} chars)")
        # datas no formato AAAA-MM-DD em qualquer lugar da resposta
        for m in re.finditer(r"\b(19|20)\d{2}-\d{2}-\d{2}\b", bruto):
            datas.add(m.group(0))
        # URLs de documento: com extensao de arquivo (pdf/rtf/doc/docx) OU
        # no formato real usado pelo Senado, sdleg-getter/documento?dm=NNN,
        # que nao tem extensao nenhuma (o regex antigo so pegava a primeira
        # forma e por isso nunca baixava nada daqui).
        urls = set(re.findall(r"https?://[^\"'\\ ]+\.(?:pdf|rtf|doc|docx)", bruto, re.I))
        urls |= set(re.findall(r"https?://[^\"'\\ ]*sdleg-getter/documento\?dm=\d+",
                                bruto, re.I))
        if urls:
            print(f"  {len(urls)} arquivos referenciados:")
            sub = pasta("senado", nome)
            for u in sorted(urls):
                print(f"    {u}")
                nomearq = re.sub(r"[^A-Za-z0-9._-]", "_", u.rsplit("/", 1)[-1])[:120]
                if not nomearq.lower().endswith((".pdf", ".rtf", ".doc", ".docx")):
                    nomearq += ".pdf"
                baixar(u, os.path.join(sub, nomearq),
                       f"Senado / {nome}", f"API Senado /{nome}")
        if nome == "emenda" and isinstance(j, list) and not j:
            nota = {
                "achado": ("O parecer MATE_TI_29602.pdf (Comissao de Infraestrutura) "
                           "descreve SEIS emendas de Plenario oferecidas ao PLC 60/1999 "
                           "('Emenda Modificativa n.1', 'Emenda Supressiva n.2', "
                           "'Emenda Aditiva n.3', 'Emenda n.4/5/6'), todas rejeitadas em "
                           "favor do Substitutivo do Senador Roberto Saturnino -- essas "
                           "emendas existiram de verdade."),
                "problema": ("/processo/emenda nao devolve nenhuma delas como registro "
                              "estruturado para esta materia."),
                "tentativas_feitas_e_vazias": [
                    "codigoMateria=42696", "idProcesso=3005683 (PLC 60/1999)",
                    "idProcesso=3005680 (processo original, PL 3808/1997)",
                ],
                "aviso": ("NAO adivinhar outros nomes de parametro aqui: idMateria=... "
                          "e ignorado silenciosamente pela API e devolve a tabela "
                          "INTEIRA de emendas do Senado (>9MB, de qualquer materia), "
                          "nao um filtro vazio -- testado e confirmado."),
                "conclusao": ("Provavel lacuna de digitalizacao da API para emendas de "
                              "Plenario de processos antigos (pre-2000). O conteudo e o "
                              "desfecho das seis emendas estao descritos verbatim dentro "
                              "do proprio parecer (MATE_TI_29602.pdf, paginas 5-6) -- usar "
                              "esse parecer como fonte primaria do teor das emendas."),
            }
            _salvar(d, "emenda_nota.json", nota)
            print("  !! /processo/emenda vazio para esta materia, mas o parecer "
                  "MATE_TI_29602.pdf descreve 6 emendas de Plenario -- lacuna "
                  "provavel da API para processos antigos. Nota gravada em "
                  "senado/emenda_nota.json; nao adivinhar outros parametros (ver nota).")
        time.sleep(0.3)

    # veto parcial (VET 31/2000, MSG 1109/2000-PE): achado a partir do campo
    # "processosRelacionados" dentro de /processo/{idProcesso} (tipoRelacao
    # "VETO", idOutroProcesso=3349182). Confirmado contra a API.
    print("\n[veto]")
    ID_PROCESSO_VETO = 3349182
    sub_veto = pasta("senado", "veto")
    j = get_json(f"{SENADO}/processo/{ID_PROCESSO_VETO}")
    if j:
        _salvar(sub_veto, "processo.json", j)
        print(f"  {j.get('identificacao')}  (idProcesso={ID_PROCESSO_VETO})")
        print(f"  ementa: {str(j.get('conteudo', {}).get('ementa',''))[:160]}")
        for m in re.finditer(r"\b(19|20)\d{2}-\d{2}-\d{2}\b", json.dumps(j, ensure_ascii=False)):
            datas.add(m.group(0))
    j = get_json(f"{SENADO}/processo/documento", params={"idProcesso": ID_PROCESSO_VETO})
    if j is not None:
        _salvar(sub_veto, "documento.json", j)
        print(f"  documentos do veto: {len(j) if isinstance(j, list) else '?'}")
        if isinstance(j, list) and not j:
            print("  (vazio -- mesma lacuna de digitalizacao vista nas emendas; "
                  "o texto do veto e das razoes presidenciais fica no DOFC, ver "
                  "referencias_diario.json da Camara: despacho de 2000-08-17 cita "
                  "'DOFC 18 08 00 PAG 0018 COL 01' para as razoes do veto)")

    return sorted(datas)


# ------------------------------------------------------------------ DIARIOS
def url_diario_camara(data_iso):
    """DCD{DD}{MES}{AAAA}.pdf -- retorna variantes a tentar."""
    y, m, dd = data_iso.split("-")
    nome = f"DCD{dd}{MESES[int(m)-1]}{y}.pdf"
    return [
        f"https://imagem.camara.leg.br/Imagem/d/pdf/{nome}",
        f"https://imagem.camara.leg.br/imagem/d/pdf/{nome}",
    ]


def reocr_diario(caminho_pdf, pasta_ocr):
    """
    Roda `ocrmypdf --redo-ocr -l por` no Diario. A camada de texto original
    desses PDFs (Diarios digitalizados ~1997-2000) existe mas e inutilizavel:
    palavras saem coladas na seguinte (medido: busca por "universalização"
    e "telecomunicações" num Diario de 2000 deu quase zero ocorrencias).
    --redo-ocr aproveita o layout/imagem existente e so troca a camada de
    texto, sem precisar re-rasterizar. Grava num arquivo separado (mantem o
    original intocado como procedencia) e retorna o caminho do resultado,
    ou None se o ocrmypdf nao estiver instalado ou falhar.
    """
    if shutil.which("ocrmypdf") is None:
        print("  !! ocrmypdf nao encontrado no PATH. Instale com:")
        print("       macOS:  brew install ocrmypdf tesseract-lang")
        print("       Debian: apt install ocrmypdf tesseract-ocr-por")
        print("     (pulando reOCR; o PDF original continua no corpus)")
        return None

    nome = os.path.basename(caminho_pdf)
    destino = os.path.join(pasta_ocr, nome)
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        print(f"  (reOCR ja existe) {nome}")
        return destino

    print(f"  reOCR (-l por --redo-ocr) em {nome} ...")
    try:
        resultado = subprocess.run(
            ["ocrmypdf", "--redo-ocr", "-l", "por", "--quiet",
             caminho_pdf, destino],
            capture_output=True, text=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        print(f"  !! ocrmypdf passou de 30min em {nome}, abortado")
        return None
    except Exception as e:
        print(f"  !! ERRO ao rodar ocrmypdf: {e}")
        return None

    if resultado.returncode != 0:
        print(f"  !! ocrmypdf falhou (codigo {resultado.returncode}) em {nome}")
        if resultado.stderr:
            print("     " + resultado.stderr.strip().splitlines()[-1][:200])
        # --redo-ocr exige que ja exista alguma camada de texto; se a pagina
        # for so imagem pura, ocrmypdf recusa. Nesse caso quem quiser texto
        # novo precisa de --force-ocr (reescreve tudo, mais lento e mais
        # arriscado de embaralhar a ordem de colunas do Diario, por isso
        # nao fazemos isso automaticamente aqui).
        if "--force-ocr" in (resultado.stderr or ""):
            print("     (parece precisar de --force-ocr em vez de --redo-ocr "
                  "-- rode manualmente se for o caso)")
        return None

    print(f"    -> reOCR ok: {os.path.basename(destino)}")
    return destino


def diarios(datas, refs_dcd, args):
    """
    refs_dcd: lista de referencias extraidas dos despachos (ver
    extrair_referencias_diario) com serie=="DCD" -- da a pagina exata do
    Diario onde o FUST foi citado naquele dia, em vez de so a data.
    """
    titulo("DIARIOS DA CAMARA - %d datas candidatas" % len(datas))
    datas = [d for d in datas if args.de <= d <= args.ate]

    paginas_por_data = {}
    for r in refs_dcd:
        if r.get("serie") == "DCD":
            paginas_por_data.setdefault(r["data"], set()).add(r["pagina"])

    print(f"  no periodo {args.de} a {args.ate}: {len(datas)} datas")
    print(f"  {len(paginas_por_data)} delas com pagina exata confirmada via despacho "
          f"(DCD ...); as demais datas vieram so do dataHora da tramitacao e podem "
          f"nao ter Diario nenhum nesse dia (despacho so interno, sem publicacao).")
    print(f"  volume estimado: ~{len(datas)*20} MB brutos, "
          f"~{len(datas)*20*2} MB depois do re-OCR")
    print("\n  URLs que seriam baixadas:")
    for dt in datas:
        pags = paginas_por_data.get(dt)
        marca = f"  [pagina confirmada: {sorted(pags)}]" if pags else "  [sem pagina confirmada]"
        print(f"    {dt}  {url_diario_camara(dt)[0]}{marca}")

    if not args.baixar_diarios:
        print("\n  (nada baixado. rode de novo com --baixar-diarios para coletar)")
        return

    d = pasta("diarios_camara")
    d_ocr = pasta("diarios_camara_ocr") if args.ocr_diarios else None
    ok = falhou = 0
    for dt in datas:
        print(f"\n[{dt}]")
        pags = paginas_por_data.get(dt)
        desc = f"Diario da Camara de {dt}"
        if pags:
            desc += f" (pagina(s) relevante(s) ao FUST: {sorted(pags)})"
        caminho = None
        for u in url_diario_camara(dt):
            destino = os.path.join(d, u.rsplit("/", 1)[-1])
            caminho = baixar(u, destino, desc, "imagem.camara.leg.br (padrao de URL)")
            if caminho:
                ok += 1
                break
        else:
            falhou += 1
            print(f"  !! nenhuma variante funcionou para {dt}")
        if caminho and args.ocr_diarios:
            destino_ocr = reocr_diario(caminho, d_ocr)
            if destino_ocr:
                q = qualidade_pdf(destino_ocr)
                h = hashlib.sha256()
                with open(destino_ocr, "rb") as f:
                    for b in iter(lambda: f.read(1 << 20), b""):
                        h.update(b)
                reg = {
                    "arquivo": os.path.relpath(destino_ocr, RAIZ),
                    "descricao": f"Diario da Camara de {dt} (reOCR -l por --redo-ocr)",
                    "origem": f"derivado de {os.path.relpath(caminho, RAIZ)} via ocrmypdf",
                    "url": None,
                    "bytes": os.path.getsize(destino_ocr),
                    "sha256": h.hexdigest(),
                    "baixado_em": datetime.now().isoformat(timespec="seconds"),
                }
                if q:
                    reg["pdf"] = q
                    print(f"    -> {q.get('paginas')} pag | {q.get('veredito')}")
                MANIFESTO.append(reg)
        time.sleep(1.0)
    print(f"\n  {ok} baixados, {falhou} sem Diario nessa data "
          f"(data sem sessao plenaria, ou publicacao no dia seguinte)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baixar-diarios", action="store_true",
                    help="baixa de fato os PDFs dos Diarios (pesado)")
    ap.add_argument("--ocr-diarios", action="store_true",
                    help="roda ocrmypdf --redo-ocr -l por em cada Diario baixado "
                         "(precisa de --baixar-diarios tambem; precisa do "
                         "binario ocrmypdf instalado)")
    ap.add_argument("--so-camara", action="store_true",
                    help="roda so a coleta da Camara")
    ap.add_argument("--so-senado", action="store_true",
                    help="roda so a coleta do Senado (pula Camara e Diarios)")
    ap.add_argument("--de", default="1997-01-01")
    ap.add_argument("--ate", default="2000-12-31")
    args = ap.parse_args()

    if args.ocr_diarios and not args.baixar_diarios:
        print("!! --ocr-diarios sem --baixar-diarios nao faz nada "
              "(nao ha Diario novo pra processar). Ligando --baixar-diarios.")
        args.baixar_diarios = True

    roda_camara = not args.so_senado
    roda_senado = not args.so_camara
    roda_diarios = roda_camara and not args.so_senado

    os.makedirs(RAIZ, exist_ok=True)
    print("COLETA FUST - " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(f"destino: {os.path.abspath(RAIZ)}")

    datas = set()
    refs_diario = []
    if roda_camara:
        try:
            datas_camara, refs_diario = camara(args)
            datas |= set(datas_camara)
        except Exception as e:
            print(f"!! camara falhou: {type(e).__name__}: {e}")
    if roda_senado:
        try:
            datas |= set(senado(args))
        except Exception as e:
            print(f"!! senado falhou: {type(e).__name__}: {e}")
    if roda_diarios:
        try:
            diarios(sorted(datas), refs_diario, args)
        except Exception as e:
            print(f"!! diarios falhou: {type(e).__name__}: {e}")

    cam = os.path.join(RAIZ, "manifesto.json")
    anterior = []
    if os.path.exists(cam):
        try:
            anterior = json.load(open(cam, encoding="utf-8"))
        except Exception:
            pass
    vistos = {r["arquivo"] for r in MANIFESTO}
    final = MANIFESTO + [r for r in anterior if r["arquivo"] not in vistos]
    with open(cam, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    titulo("RESUMO")
    print(f"  {len(final)} arquivos no manifesto")
    from collections import Counter
    c = Counter(r.get("pdf", {}).get("veredito", "nao_pdf") for r in final)
    for k, v in c.most_common():
        print(f"    {v:4d}  {k}")
    print(f"\n  manifesto: {cam}")

    pend = os.path.join(RAIZ, "pendentes_manuais.json")
    if PENDENTES_MANUAIS:
        with open(pend, "w", encoding="utf-8") as f:
            json.dump(PENDENTES_MANUAIS, f, ensure_ascii=False, indent=2)
        print(f"\n  !! {len(PENDENTES_MANUAIS)} arquivo(s) exigem download manual "
              f"(desafio anti-bot ou HTML onde era esperado PDF):")
        for p in PENDENTES_MANUAIS:
            print(f"    [{p['motivo']}] {p['url']}")
        print(f"  lista completa: {pend}")
        print("  baixe num navegador e salve em "
              "corpus_fust/senado/documentos_manuais/")

    print("\n  Me mande o manifesto.json e a saida deste script.")


if __name__ == "__main__":
    main()
