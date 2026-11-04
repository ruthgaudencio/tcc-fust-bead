"""
Extração de referências a Diário a partir dos despachos de tramitação.

Lê os textos de tramitacoes.json (Câmara, API v2) e devolve referências
estruturadas no formato DCD/DSF + data + página, cobrindo as variantes que
aparecem nos despachos:

    DCD 01 09 00 PAG 44321
    DCD 01/09/2000 PÁG 44321
    DCD 01 SET 2000 pág. 44321
    DCD 01-09-2000, PAGS. 44321 A 44340
    duas citações no mesmo despacho

Nome de arquivo do Diário é composto, não descoberto: DCD{DD}{MES}{AAAA}.pdf
(armadilha 7 — imagem.camara.leg.br não responde a fetch nem a headless).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator

__all__ = [
    "DiarioRef",
    "extrair_refs",
    "extrair_de_tramitacoes",
    "agrupar_por_arquivo",
    "nome_arquivo",
]


MESES_NUM_PARA_SIGLA = {
    1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ",
}

MESES_TEXTO_PARA_NUM = {
    "JAN": 1, "JANEIRO": 1,
    "FEV": 2, "FEVEREIRO": 2,
    "MAR": 3, "MARCO": 3, "MARÇO": 3,
    "ABR": 4, "ABRIL": 4,
    "MAI": 5, "MAIO": 5,
    "JUN": 6, "JUNHO": 6,
    "JUL": 7, "JULHO": 7,
    "AGO": 8, "AGOSTO": 8,
    "SET": 9, "SETEMBRO": 9, "SETE": 9,
    "OUT": 10, "OUTUBRO": 10,
    "NOV": 11, "NOVEMBRO": 11,
    "DEZ": 12, "DEZEMBRO": 12,
}

SIGLAS = ("DCD", "DSF", "DCN", "DOU")

_SEP = r"[\s./\-]{1,3}"

_RE_REF = re.compile(
    r"\b(?P<sigla>" + "|".join(SIGLAS) + r")\b"
    r"[\s:,]*"
    r"(?P<dia>\d{1,2})" + _SEP +
    r"(?P<mes>\d{1,2}|[A-Za-zÇç]{3,9})\.?" + _SEP +
    r"(?P<ano>\d{4}|\d{2})"
    r"(?:"
    r"[\s.,;:\-]{0,4}"
    r"(?:P[ÁA]GS?|P[ÁA]GINAS?|P)\.?\s*[:.]?\s*"
    r"(?P<pag>\d{1,6})"
    r"(?:\s*(?:A|AT[ÉE]|[\-–])\s*(?P<pag2>\d{1,6}))?"
    r")?",
    re.IGNORECASE | re.UNICODE,
)

# campos dos itens de tramitacoes.json que podem conter a citação
CAMPOS_TEXTO = ("despacho", "descricaoTramitacao", "descricaoSituacao", "texto")


@dataclass(frozen=True)
class DiarioRef:
    sigla: str
    data: date
    pagina_inicial: int | None
    pagina_final: int | None
    bruto: str
    origem: str = ""

    @property
    def arquivo(self) -> str:
        return nome_arquivo(self.sigla, self.data)

    @property
    def tem_pagina(self) -> bool:
        return self.pagina_inicial is not None

    @property
    def chave(self) -> tuple[str, date, int | None, int | None]:
        return (self.sigla, self.data, self.pagina_inicial, self.pagina_final)

    def __str__(self) -> str:
        faixa = ""
        if self.pagina_inicial is not None:
            faixa = f" p.{self.pagina_inicial}"
            if self.pagina_final:
                faixa += f"-{self.pagina_final}"
        return f"{self.arquivo}{faixa}"


def nome_arquivo(sigla: str, data: date) -> str:
    """DCD + 01 + SET + 2000 + .pdf"""
    return (
        f"{sigla.upper()}{data.day:02d}"
        f"{MESES_NUM_PARA_SIGLA[data.month]}{data.year}.pdf"
    )


def _resolver_mes(bruto: str) -> int | None:
    bruto = bruto.strip(". ")
    if bruto.isdigit():
        n = int(bruto)
        return n if 1 <= n <= 12 else None
    return MESES_TEXTO_PARA_NUM.get(bruto.upper())


def _resolver_ano(bruto: str) -> int:
    n = int(bruto)
    if len(bruto) == 4:
        return n
    # corpus 1997-2000: 97..99 -> 19xx, 00..xx -> 20xx
    return 1900 + n if n >= 90 else 2000 + n


def extrair_refs(texto: str, origem: str = "") -> list[DiarioRef]:
    """Extrai todas as referências de Diário presentes em um texto."""
    if not texto:
        return []
    refs: list[DiarioRef] = []
    for m in _RE_REF.finditer(texto):
        mes = _resolver_mes(m.group("mes"))
        dia = int(m.group("dia"))
        if mes is None or not (1 <= dia <= 31):
            continue
        try:
            d = date(_resolver_ano(m.group("ano")), mes, dia)
        except ValueError:
            continue
        pag = m.group("pag")
        pag2 = m.group("pag2")
        refs.append(
            DiarioRef(
                sigla=m.group("sigla").upper(),
                data=d,
                pagina_inicial=int(pag) if pag else None,
                pagina_final=int(pag2) if pag2 else None,
                bruto=m.group(0).strip(),
                origem=origem,
            )
        )
    return refs


def _itens_tramitacao(dados) -> Iterator[dict]:
    if isinstance(dados, dict):
        dados = dados.get("dados", dados)
    if isinstance(dados, dict):
        dados = [dados]
    for item in dados or []:
        if isinstance(item, dict):
            yield item


def extrair_de_tramitacoes(
    caminho: str | Path, *, deduplicar: bool = True
) -> list[DiarioRef]:
    """Varre tramitacoes.json e devolve as referências encontradas.

    Dedupe por (sigla, data, página inicial, página final). A origem guardada
    é a do primeiro despacho em que a referência apareceu.
    """
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))

    refs: list[DiarioRef] = []
    for i, item in enumerate(_itens_tramitacao(dados)):
        rotulo = str(
            item.get("sequencia")
            or item.get("dataHora")
            or item.get("codTipoTramitacao")
            or i
        )
        for campo in CAMPOS_TEXTO:
            valor = item.get(campo)
            if isinstance(valor, str) and valor.strip():
                refs.extend(extrair_refs(valor, origem=f"{campo}#{rotulo}"))

    if not deduplicar:
        return refs

    vistos: dict[tuple, DiarioRef] = {}
    for r in refs:
        vistos.setdefault(r.chave, r)
    return sorted(vistos.values(), key=lambda r: (r.data, r.pagina_inicial or 0))


def agrupar_por_arquivo(refs: Iterable[DiarioRef]) -> dict[str, list[DiarioRef]]:
    """Agrupa por nome de arquivo de Diário, para baixar cada PDF uma vez só."""
    out: dict[str, list[DiarioRef]] = {}
    for r in refs:
        out.setdefault(r.arquivo, []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r.pagina_inicial or 0)
    return out


if __name__ == "__main__":  # diagnóstico rápido
    import sys

    alvo = sys.argv[1] if len(sys.argv) > 1 else "corpus_fust/camara/tramitacoes.json"
    achadas = extrair_de_tramitacoes(alvo)
    com_pagina = [r for r in achadas if r.tem_pagina]
    print(f"{len(achadas)} referências, {len(com_pagina)} com página exata")
    for arq, grupo in agrupar_por_arquivo(achadas).items():
        paginas = [r.pagina_inicial for r in grupo if r.tem_pagina]
        print(f"  {arq:<22} {len(grupo)} ref(s)  páginas={paginas or '—'}")
