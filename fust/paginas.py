"""
Mapeamento entre a página IMPRESSA do Diário e o índice da página no PDF,
e extração da faixa relevante.

O despacho de tramitação cita a página impressa ("PAG 44321"), que não é o
índice da página no PDF. No DCD01SET2000 a página impressa 44858 é a 4ª do
PDF: deslocamento 44854. O deslocamento é constante dentro de um Diário e sai
do próprio cabeçalho ("44904 Sexta-feira 1  DIÁRIO DA CÂMARA..."), então é
calibrado, não perguntado.

    cal = calibrar("DCD01SET2000.pdf")
    cal.para_pdf(44904)        # -> 50
    extrair_faixa("DCD01SET2000.pdf", cal, 44904, 44906, "saida.pdf")

Depende de pdftotext, pdfinfo e qpdf no PATH (poppler + qpdf).
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Calibracao", "calibrar", "extrair_faixa", "numero_impresso"]

_RE_NUM = re.compile(r"\b(\d{3,6})\b")


def _texto_pagina(pdf: str | Path, pagina: int) -> str:
    r = subprocess.run(
        ["pdftotext", "-f", str(pagina), "-l", str(pagina), "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
    )
    return r.stdout


def _n_paginas(pdf: str | Path) -> int:
    r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    for linha in r.stdout.splitlines():
        if linha.startswith("Pages:"):
            return int(linha.split()[1])
    raise RuntimeError(f"pdfinfo não devolveu contagem de páginas para {pdf}")


def numero_impresso(texto_pagina: str) -> int | None:
    """Número impresso no cabeçalho, ou None se a página não tiver cabeçalho.

    O número fica na primeira linha não vazia, no começo (página par) ou no
    fim (página ímpar). O ano é descartado para não ser confundido com ele.
    """
    for linha in texto_pagina.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        nums = [int(x) for x in _RE_NUM.findall(linha)]
        nums = [x for x in nums if not 1900 <= x <= 2100]
        return nums[0] if nums else None
    return None


@dataclass(frozen=True)
class Calibracao:
    pdf: str
    deslocamento: int  # pagina_impressa - indice_pdf
    paginas_pdf: int
    amostras_validas: int
    concordancia: float  # fração das amostras legíveis que concordaram

    @property
    def primeira_impressa(self) -> int:
        return self.deslocamento + 1

    @property
    def ultima_impressa(self) -> int:
        return self.deslocamento + self.paginas_pdf

    def para_pdf(self, pagina_impressa: int) -> int | None:
        i = pagina_impressa - self.deslocamento
        return i if 1 <= i <= self.paginas_pdf else None

    def para_impressa(self, indice_pdf: int) -> int:
        return indice_pdf + self.deslocamento

    def contem(self, pagina_impressa: int) -> bool:
        return self.para_pdf(pagina_impressa) is not None


def calibrar(
    pdf: str | Path, *, amostras: int = 12, minimo_concordancia: float = 0.6
) -> Calibracao:
    """Deduz o deslocamento amostrando cabeçalhos ao longo do PDF.

    Vale o deslocamento mais frequente. Páginas sem cabeçalho legível (capa,
    anúncio, página só de imagem) não votam. Se a concordância ficar baixa,
    levanta erro em vez de devolver um mapeamento errado em silêncio: pode ser
    Diário com numeração reiniciada no meio, que precisa de tratamento à mão.
    """
    pdf = Path(pdf)
    total = _n_paginas(pdf)
    passo = max(1, total // (amostras + 1))
    indices = list(range(1, total + 1, passo))[: amostras + 2]

    votos: Counter[int] = Counter()
    validas = 0
    for i in indices:
        n = numero_impresso(_texto_pagina(pdf, i))
        if n is None:
            continue
        validas += 1
        votos[n - i] += 1

    if not votos:
        raise RuntimeError(
            f"{pdf.name}: nenhum cabeçalho legível nas {len(indices)} amostras. "
            "Esse Diário precisa de mapeamento manual."
        )
    deslocamento, n_votos = votos.most_common(1)[0]
    concordancia = n_votos / validas
    if concordancia < minimo_concordancia:
        raise RuntimeError(
            f"{pdf.name}: cabeçalhos inconsistentes (concordância "
            f"{concordancia:.0%} em {validas} amostras legíveis; "
            f"votos={dict(votos)}). Confira à mão antes de recortar."
        )
    return Calibracao(str(pdf), deslocamento, total, validas, concordancia)


def extrair_faixa(
    pdf: str | Path,
    cal: Calibracao,
    impressa_inicial: int,
    impressa_final: int | None = None,
    saida: str | Path | None = None,
    *,
    margem: int = 1,
) -> Path:
    """Recorta a faixa de páginas impressas para um PDF novo, via qpdf.

    `margem` acrescenta páginas antes e depois, porque matéria de Diário
    costuma atravessar a virada de página.
    """
    impressa_final = impressa_final or impressa_inicial
    a = cal.para_pdf(impressa_inicial)
    b = cal.para_pdf(impressa_final)
    if a is None or b is None:
        raise ValueError(
            f"página impressa fora do PDF: pedido "
            f"{impressa_inicial}-{impressa_final}, disponível "
            f"{cal.primeira_impressa}-{cal.ultima_impressa}"
        )
    a = max(1, a - margem)
    b = min(cal.paginas_pdf, b + margem)

    pdf = Path(pdf)
    saida = (
        Path(saida)
        if saida
        else pdf.with_name(f"{pdf.stem}_p{impressa_inicial}-{impressa_final}.pdf")
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["qpdf", str(pdf), "--pages", str(pdf), f"{a}-{b}", "--", str(saida)],
        check=True,
        capture_output=True,
    )
    return saida
