#!/usr/bin/env python3
"""
Segmentação por marcador de orador (seção 4.6) + validação contra o
sumário do próprio Diário (gabarito).

Dois lados:
  1. GABARITO: parseia o texto OCRizado do SUMÁRIO (lista de oradores por
     sessão, formato "NOME (PARTIDO - UF) - tópico ... página" ou "Usou/
     Usaram da palavra ... o(s) Sr(s). Deputado(s) NOME[, NOME2, ...]").
  2. RECUPERADO: varre o texto OCRizado do CORPO (as falas de verdade) com
     o marcador `O SR. NOME (...)` / `A SRª NOME (...)`.

Compara as contagens por faixa de página. Divergência é esperada e não é
erro automático: o sumário às vezes agrupa (ex. "Usaram da palavra ... os
Srs. Deputados X, Y" conta como 2 falas no corpo mas 1 linha no sumário --
já expandido aqui) e o corpo pode ter interrupções/apartes que o sumário
não lista à parte.

    python segmentar_oradores.py \\
        --sumario-dir corpus_fust/diarios_camara/DCD08DEZ1999_sumario_p60352-60361_paginas \\
        --sumario-dir corpus_fust/diarios_camara/DCD08DEZ1999_sumario_p60359-60361_paginas \\
        --corpo-dir corpus_fust/camara/emendas/_compartilhados/DCD08DEZ1999_p60552-60574_paginas \\
        --pagina-inicial 60552 --pagina-final 60574
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Gabarito (sumário)
# --------------------------------------------------------------------------

_RE_NUM_LINHA = re.compile(r"^\s*(\d{4,6})\s*\.?\s*$")
_RE_NOME_CAPS = re.compile(
    r"\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ'\.]+(?:\s+(?:DE|DA|DO|DOS|DAS|E)?\s*"
    r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ'\.]+){0,3})\b"
)
_RE_INTRO_DIRETA = re.compile(
    r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ'\. ]{2,40}?)\s*\((?:PARTIDO|[A-Z]{2,6}\s*[-–/]|"
    r"Pela ordem|Como Líder|Bloco)"
)
_RE_USOU = re.compile(
    r"Usou|Usaram.{0,80}?(?:o|os)\s+Sr\.?s?\.?\s+Deputad[oa]s?\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^.]*?)\.{0,3}\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _nomes_de_lista(trecho: str) -> list[str]:
    """'FERNANDO GABEIRA, ROBERTO ARGENTA E BISPO RODRIGUES' -> 3 nomes."""
    trecho = re.sub(r"\s+E\s+", ", ", trecho)
    partes = [p.strip(" .") for p in trecho.split(",")]
    return [p for p in partes if len(p) > 2]


def parsear_sumario(diretorios: list[Path], pagina_inicial: int, pagina_final: int) -> list[dict]:
    """Lê todos os .txt de página dos diretórios de sumário, concatena em
    ordem, separa por marcador de página e extrai nome(s) de cada bloco.
    Devolve uma entrada por ORADOR (lista expandida), só para blocos cuja
    página cai em [pagina_inicial, pagina_final].

    Não assume que o número de página sai sozinho na própria linha --
    testado e falso: boa parte vem colado ao fim dos pontos de preenchimento
    ("..........60553") na mesma linha do texto anterior. Busca o token de
    número em QUALQUER posição do texto corrido (limitado à faixa plausível
    de página deste Diário) e corta ali, não por linha.
    """
    arquivos = []
    for d in diretorios:
        arquivos.extend(sorted(d.glob("p*.txt"), key=lambda p: int(re.search(r"\d+", p.stem).group())))

    texto = " ".join(a.read_text(encoding="utf-8").replace("\n", " ") for a in arquivos)
    # faixa plausível: 2 ordens de grandeza em volta do que foi pedido, pra
    # não confundir com "1999", "24" (nº da emenda) etc.
    piso = max(10000, pagina_inicial - 5000)
    teto = pagina_final + 5000
    re_num = re.compile(rf"\b({piso // 1000}\d{{3,4}}|\d{{5,6}})\b")

    blocos: list[tuple[str, int | None]] = []
    pos = 0
    for m in re_num.finditer(texto):
        pag = int(m.group(1))
        if piso <= pag <= teto:
            blocos.append((texto[pos:m.start()].strip(), pag))
            pos = m.end()
    if texto[pos:].strip():
        blocos.append((texto[pos:].strip(), None))

    falas = []
    for texto_bloco, pagina in blocos:
        if pagina is None or not (pagina_inicial <= pagina <= pagina_final):
            continue
        if not texto_bloco:
            continue

        m_usou = re.search(r"(?:Usou|Usaram)\b.*?Deputad[oa]s?\s+(.+)", texto_bloco, re.IGNORECASE)
        if m_usou:
            for nome in _nomes_de_lista(m_usou.group(1)):
                falas.append({"nome": nome, "pagina": pagina, "origem": "usou_da_palavra"})
            continue

        m_direto = _RE_INTRO_DIRETA.match(texto_bloco)
        if m_direto:
            falas.append({"nome": m_direto.group(1).strip(), "pagina": pagina, "origem": "intro_direta"})
            continue

        if texto_bloco.upper().startswith("PRESIDENTE"):
            falas.append({"nome": "PRESIDENTE", "pagina": pagina, "origem": "presidente"})

    return falas


# --------------------------------------------------------------------------
# Recuperado (corpo, marcador O SR./A SRª)
# --------------------------------------------------------------------------

#   Parênteses OPCIONAIS -- achado testando (teste_marcador_adjacente.py):
#   um pedido breve de palavra sai sem parênteses nenhum ("O SR. WALTER
#   PINHEIRO - Sr. Presidente, peço a palavra pela ordem."), diferente da
#   fala completa que vem depois ("O SR. WALTER PINHEIRO (PT - BA. Sem
#   revisão do orador.) - ..."). Exigir "(" logo após o nome (versão
#   anterior) derrubava esse pedido silenciosamente -- não por ele estar
#   perto de outro marcador, mas por não ter parênteses. O traço (-/–/—)
#   depois do nome [e do parêntese, se houver] é o que sobra como âncora
#   confiável nos dois formatos.
_RE_MARCADOR_CORPO = re.compile(
    r"\b[OoAa]\s+SRA?[Aa\xaa]?\.?\s*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^\n(]{0,60}?)"
    r"\s*(?:\(([^)]*)\))?\s*[-–—−]",
    re.UNICODE,
)


def segmentar_corpo(
    diretorio: Path,
    pagina_inicial: int,
    pagina_final: int,
    *,
    ancora_inicio: str | None = None,
    ancora_fim: str | None = None,
) -> list[dict]:
    """`ancora_inicio`/`ancora_fim` recortam matéria vizinha que vaza para a
    borda da faixa pedida (achado nas 3 sessões de
    metodologia_validacao_segmentacao.md): texto antes de `ancora_inicio` na
    PRIMEIRA página, ou depois de `ancora_fim` na ÚLTIMA página, é
    descartado antes de rodar o regex -- mas o `offset` devolvido continua
    relativo ao texto ORIGINAL da página (não ao texto recortado), porque é
    isso que permite voltar ao arquivo fonte."""
    arquivos = sorted(diretorio.glob("p*.txt"), key=lambda p: int(re.search(r"\d+", p.stem).group()))
    falas = []
    for a in arquivos:
        pagina = int(re.search(r"\d+", a.stem).group())
        if not (pagina_inicial <= pagina <= pagina_final):
            continue
        texto = a.read_text(encoding="utf-8")
        deslocamento = 0
        if pagina == pagina_inicial and ancora_inicio is not None:
            pos = texto.find(ancora_inicio)
            if pos == -1:
                raise ValueError(f"ancora_inicio {ancora_inicio!r} não achada em {a}")
            deslocamento = pos
            texto = texto[pos:]
        if pagina == pagina_final and ancora_fim is not None:
            pos = texto.find(ancora_fim)
            if pos == -1:
                raise ValueError(f"ancora_fim {ancora_fim!r} não achada em {a}")
            texto = texto[:pos]
        for m in _RE_MARCADOR_CORPO.finditer(texto):
            nome = m.group(1).strip()
            parenteses = (m.group(2) or "").strip()
            falas.append({"nome": nome, "pagina": pagina, "parenteses": parenteses,
                         "sem_parenteses": m.group(2) is None,
                         "offset": m.start() + deslocamento, "arquivo": str(a)})
    return falas


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumario-dir", action="append", required=True,
                    help="diretório com p<pagina>.txt do sumário (repetível)")
    ap.add_argument("--corpo-dir", required=True,
                    help="diretório com p<pagina>.txt do corpo (as falas de verdade)")
    ap.add_argument("--pagina-inicial", type=int, required=True)
    ap.add_argument("--pagina-final", type=int, required=True)
    args = ap.parse_args()

    sumario_dirs = [Path(d) if Path(d).is_absolute() else RAIZ / d for d in args.sumario_dir]
    corpo_dir = Path(args.corpo_dir) if Path(args.corpo_dir).is_absolute() else RAIZ / args.corpo_dir

    gabarito = parsear_sumario(sumario_dirs, args.pagina_inicial, args.pagina_final)
    recuperado = segmentar_corpo(corpo_dir, args.pagina_inicial, args.pagina_final)

    print("=" * 78)
    print(f"SESSÃO -- páginas {args.pagina_inicial} a {args.pagina_final}")
    print("=" * 78)

    print(f"\nGABARITO (sumário): {len(gabarito)} fala(s) listada(s)")
    for f in gabarito:
        print(f"  pág {f['pagina']}  {f['nome']}  [{f['origem']}]")

    presidente = [f for f in recuperado if f["nome"].strip().upper().startswith("PRESIDENTE")]
    nomeados = [f for f in recuperado if not f["nome"].strip().upper().startswith("PRESIDENTE")]
    sem_parenteses = [f for f in nomeados if f.get("sem_parenteses")]

    print(f"\nRECUPERADO (marcador no corpo): {len(recuperado)} marcador(es) no total")
    print(f"  Presidência: {len(presidente)}")
    print(f"  orador nomeado: {len(nomeados)}"
          + (f"  ({len(sem_parenteses)} sem parênteses -- pedido breve de palavra)"
             if sem_parenteses else ""))
    for f in recuperado:
        tag = " [sem parênteses]" if f.get("sem_parenteses") else ""
        print(f"  pág {f['pagina']}  {f['nome']}  ({f['parenteses'][:40]}){tag}")

    print("\n" + "-" * 78)
    print("RESUMO -- as duas contagens NÃO se somam, são naturezas diferentes:")
    print(f"  Presidência: sumário cita {sum(1 for f in gabarito if f['nome']=='PRESIDENTE')}, "
          f"corpo recuperou {len(presidente)}")
    print(f"  orador nomeado: sumário cita {sum(1 for f in gabarito if f['nome']!='PRESIDENTE')}, "
          f"corpo recuperou {len(nomeados)}")
    nomes_gabarito = {re.sub(r'[^A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]', '', f['nome'].upper()) for f in gabarito
                      if f['nome'] != 'PRESIDENTE'}
    nomes_recuperado = {re.sub(r'[^A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]', '', f['nome'].upper()) for f in nomeados}
    so_no_gabarito = {n for n in nomes_gabarito if not any(n in r or r in n for r in nomes_recuperado)}
    so_no_corpo = {n for n in nomes_recuperado if not any(n in g or g in n for g in nomes_gabarito)}
    if so_no_gabarito:
        print(f"nomes no sumário sem marcador correspondente achado no corpo: {sorted(so_no_gabarito)}")
    if so_no_corpo:
        print(f"nomes achados no corpo sem entrada correspondente no sumário: {sorted(so_no_corpo)}")


if __name__ == "__main__":
    main()
