#!/usr/bin/env python3
"""
Download incremental dos Diários referenciados nos despachos de tramitação.

Roda um alvo por vez por padrão, para dar para conferir o que voltou antes de
seguir. Nada é sobrescrito: arquivo que já existe ganha versão nova.

    python baixar_diarios.py --listar          # plano, sem baixar nada
    python baixar_diarios.py                   # baixa 1 alvo pendente
    python baixar_diarios.py --n 3             # baixa 3
    python baixar_diarios.py --so DCD14NOV1997 # baixa um específico
    python baixar_diarios.py --forcar          # repete alvo já concluído

Convenções mantidas do resto da coleta:
  - metadado do alvo é gravado no manifesto ANTES da tentativa de download
  - um arquivo por resposta, nome = o nome composto do Diário
  - não sobrescreve, versiona (_v2, _v3)
  - registra qual tentativa funcionou quando há mais de uma
  - o que falhar vai para pendentes_manuais.json com motivo legível

Só stdlib. Rode da raiz do projeto (a pasta que contém corpus_fust/).
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "corpus_fust"
REFS = CORPUS / "camara" / "referencias_diario.json"
DESTINO = CORPUS / "diarios_camara"
MANIFESTO = CORPUS / "manifesto.json"
PENDENTES = CORPUS / "pendentes_manuais.json"

# O domínio correto está no inteiro_teor_resolucao.json do próprio corpus:
# imagem.camara.gov.br, não .leg.br.
BASES = [
    "http://imagem.camara.gov.br/Imagem/d/pdf/{arquivo}",
    "https://imagem.camara.gov.br/Imagem/d/pdf/{arquivo}",
]

MESES = {
    1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ",
}

# Séries cujo nome de arquivo segue o padrão de composição da Câmara.
SERIES_COMPONIVEIS = {"DCD", "DCN"}

# Assinaturas de arquivo real. Status 200 não garante PDF: a Câmara devolve
# página de erro do Tomcat com 200.
ASSINATURAS = {
    b"%PDF": "pdf",
    b"{\\rt": "rtf",
    b"PK\x03\x04": "zip/ooxml",
    b"\xd0\xcf\x11\xe0": "ole/doc",
}

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
}


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Alvo:
    serie: str
    data: str  # ISO
    paginas: tuple[int, ...]
    arquivo: str | None  # nome composto, ou None se a série não compõe
    motivo_sem_url: str = ""

    @property
    def chave(self) -> str:
        return self.arquivo or f"{self.serie}_{self.data}"


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
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def nome_composto(serie: str, iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{serie}{d.day:02d}{MESES[d.month]}{d.year}.pdf"


def montar_alvos() -> list[Alvo]:
    """Agrupa as referências por (série, data). Um Diário, um download."""
    refs = _ler_json(REFS, [])
    if not refs:
        raise SystemExit(f"não achei referências em {REFS}")

    por_diario: dict[tuple[str, str], set[int]] = {}
    for r in refs:
        serie = (r.get("serie") or "").upper()
        data = r.get("data")
        if not serie or not data:
            continue
        pag = r.get("pagina")
        por_diario.setdefault((serie, data), set())
        if isinstance(pag, int):
            por_diario[(serie, data)].add(pag)

    alvos = []
    for (serie, data), pags in sorted(por_diario.items(), key=lambda x: x[0][1]):
        if serie in SERIES_COMPONIVEIS:
            alvos.append(Alvo(serie, data, tuple(sorted(pags)), nome_composto(serie, data)))
        else:
            # DOFC é Diário Oficial da União, outro sistema (Imprensa
            # Nacional). O nome não se compõe pelo padrão da Câmara, então
            # não chuto: vai para pendentes com o motivo.
            alvos.append(
                Alvo(
                    serie,
                    data,
                    tuple(sorted(pags)),
                    None,
                    f"série {serie} não segue o padrão de nome da Câmara; "
                    "baixar à mão pela Imprensa Nacional",
                )
            )
    return alvos


# --------------------------------------------------------------------------
# Estado
# --------------------------------------------------------------------------


def manifesto_por_chave() -> dict[str, dict]:
    return {e["chave"]: e for e in _ler_json(MANIFESTO, []) if "chave" in e}


def registrar_manifesto(entrada: dict) -> None:
    """Grava o metadado do alvo. Chamado ANTES da tentativa de download."""
    atual = _ler_json(MANIFESTO, [])
    atual = [e for e in atual if e.get("chave") != entrada["chave"]]
    atual.append(entrada)
    _gravar_json(MANIFESTO, atual)


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


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def _tentar(url: str, timeout: int) -> tuple[bytes | None, str]:
    """Devolve (corpo, diagnóstico). corpo=None quando não deu."""
    req = Request(url, headers=CABECALHOS)
    try:
        with urlopen(req, timeout=timeout) as resp:
            corpo = resp.read()
            ct = resp.headers.get("Content-Type", "?")
            return corpo, f"http={resp.status} tipo={ct} bytes={len(corpo)}"
    except HTTPError as e:
        return None, f"http={e.code} {e.reason}"
    except URLError as e:
        return None, f"rede: {e.reason}"
    except TimeoutError:
        return None, "timeout"


def identificar(corpo: bytes) -> str | None:
    for assinatura, nome in ASSINATURAS.items():
        if corpo.startswith(assinatura):
            return nome
    return None


def baixar(alvo: Alvo, *, tentativas: int = 3, timeout: int = 60) -> dict:
    """Tenta cada base, com backoff. Registra qual estratégia funcionou."""
    log: list[str] = []
    for base in BASES:
        url = base.format(arquivo=alvo.arquivo)
        for i in range(1, tentativas + 1):
            corpo, diag = _tentar(url, timeout)
            log.append(f"{url} [tentativa {i}] {diag}")

            if corpo is None:
                time.sleep(min(2 ** i, 15))
                continue

            tipo = identificar(corpo)
            if tipo is None:
                # 200 com corpo que não é arquivo: página de erro ou desafio.
                amostra = corpo[:200].decode("utf-8", "replace").replace("\n", " ")
                log.append(f"  corpo não é arquivo conhecido: {amostra[:120]}")
                suspeito = caminho_versionado(
                    DESTINO / f"{alvo.arquivo}.suspeito.html"
                )
                suspeito.parent.mkdir(parents=True, exist_ok=True)
                suspeito.write_bytes(corpo)
                break  # trocar de base; repetir a mesma não muda nada

            destino = caminho_versionado(DESTINO / alvo.arquivo)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(corpo)
            return {
                "ok": True,
                "arquivo": str(destino.relative_to(RAIZ)),
                "bytes": len(corpo),
                "tipo": tipo,
                "url_que_funcionou": url,
                "log": log,
            }

    return {"ok": False, "log": log}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def descrever(alvo: Alvo, estado: dict | None) -> str:
    pags = ", ".join(str(p) for p in alvo.paginas) or "sem página"
    marca = "ok " if estado and estado.get("baixado") else "-- "
    nome = alvo.arquivo or f"({alvo.serie} {alvo.data}, sem nome componível)"
    return f"  {marca}{nome:<22} {alvo.data}  pág. {pags}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--listar", action="store_true", help="mostra o plano e sai")
    ap.add_argument("--n", type=int, default=1, help="quantos alvos baixar (padrão 1)")
    ap.add_argument("--so", help="baixa só este arquivo, ex. DCD14NOV1997")
    ap.add_argument("--forcar", action="store_true", help="repete alvo já concluído")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    alvos = montar_alvos()
    estado = manifesto_por_chave()

    if args.listar:
        feitos = sum(1 for a in alvos if estado.get(a.chave, {}).get("baixado"))
        print(f"\n{len(alvos)} Diários referenciados, {feitos} já baixados\n")
        for a in alvos:
            print(descrever(a, estado.get(a.chave)))
        print(f"\ndestino: {DESTINO.relative_to(RAIZ)}")
        return

    fila = [a for a in alvos if a.arquivo]
    if args.so:
        alvo_nome = args.so if args.so.endswith(".pdf") else args.so + ".pdf"
        fila = [a for a in fila if a.arquivo == alvo_nome]
        if not fila:
            raise SystemExit(f"não achei alvo {alvo_nome}. Use --listar.")
    elif not args.forcar:
        fila = [a for a in fila if not estado.get(a.chave, {}).get("baixado")]

    # Séries que não compõem nome vão para pendentes já na primeira passada.
    for a in alvos:
        if not a.arquivo:
            registrar_pendente(
                f"<sem URL componível> {a.serie} {a.data} pág. {list(a.paginas)}",
                f"Diário {a.serie} de {a.data}",
                a.motivo_sem_url,
            )

    if not fila:
        print("nada pendente. --listar para ver o estado, --forcar para repetir.")
        return

    for alvo in fila[: args.n]:
        print(f"\n→ {alvo.arquivo}  (pág. {list(alvo.paginas)})")

        # metadado primeiro: se o download falhar, isto fica
        registrar_manifesto(
            {
                "chave": alvo.chave,
                "serie": alvo.serie,
                "data": alvo.data,
                "paginas": list(alvo.paginas),
                "arquivo_esperado": alvo.arquivo,
                "tentado_em": _agora(),
                "baixado": False,
            }
        )

        r = baixar(alvo, timeout=args.timeout)
        for linha in r["log"]:
            print("   ", linha)

        if r["ok"]:
            registrar_manifesto(
                {
                    "chave": alvo.chave,
                    "serie": alvo.serie,
                    "data": alvo.data,
                    "paginas": list(alvo.paginas),
                    "arquivo_esperado": alvo.arquivo,
                    "tentado_em": _agora(),
                    "baixado": True,
                    "arquivo": r["arquivo"],
                    "bytes": r["bytes"],
                    "tipo": r["tipo"],
                    "url_que_funcionou": r["url_que_funcionou"],
                }
            )
            print(f"   OK  {r['arquivo']}  ({r['bytes']:,} bytes, {r['tipo']})")
        else:
            motivo = r["log"][-1] if r["log"] else "sem diagnóstico"
            registrar_pendente(
                BASES[0].format(arquivo=alvo.arquivo),
                f"Diário {alvo.serie} de {alvo.data}, pág. {list(alvo.paginas)}",
                f"download falhou: {motivo}",
            )
            print(f"   FALHOU → pendentes_manuais.json ({motivo})")


if __name__ == "__main__":
    main()
