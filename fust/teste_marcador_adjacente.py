#!/usr/bin/env python3
"""
Teste sintético: o segmentador de `segmentar_oradores.py` perde marcador
quando dois aparecem muito próximos?

Não usa nenhum Diário real -- texto construído à mão, limpo (sem ruído de
OCR), pra isolar se o problema é do REGEX em si ou de ruído de
reconhecimento. Cada caso diz quantos marcadores UMA LEITURA HUMANA
contaria (`esperado`) e compara com o que `_RE_MARCADOR_CORPO` acha.

Resultado (2026-10-15, achado lendo o Diário de verdade antes de escrever
este teste, depois confirmado aqui com texto sintético limpo): a causa da
fala perdida na ATA 240ª NÃO é "dois marcadores próximos" em si -- os
casos de adjacência pura, incluindo o mesmo orador duas vezes seguidas,
sempre passaram. A causa real é `O SR. WALTER PINHEIRO` aparecendo sem
parênteses nenhum ("O SR. WALTER PINHEIRO - Sr. Presidente, peço a
palavra pela ordem."), um pedido breve de palavra, formato diferente da
fala completa que vem depois ("O SR. WALTER PINHEIRO (PT - BA. Sem
revisão do orador.) - ..."). O regex original EXIGIA parênteses logo após
o nome, então esse formato nunca batia. CORRIGIDO em segmentar_oradores.py
(parênteses agora opcionais, âncora passou a ser o traço que sempre vem
depois, com ou sem parêntese). Este arquivo fica como teste de regressão:
se a correção quebrar de novo, os casos abaixo acusam.

    python teste_marcador_adjacente.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import segmentar_oradores as so  # noqa: E402

CASOS = [
    {
        "nome": "dois marcadores adjacentes, ambos com parênteses (controle)",
        "texto": (
            "O SR. FULANO (PT - BA. Sem revisão do orador.) - Peço a palavra.\n"
            "O SR. PRESIDENTE (Michel Temer) - Concedida.\n"
        ),
        "esperado": 2,
    },
    {
        "nome": "mesmo orador duas vezes seguidas, ambos com parênteses",
        "texto": (
            "O SR. WALTER PINHEIRO (PT - BA. Pela ordem.) - Peço a palavra.\n"
            "O SR. WALTER PINHEIRO (PT - BA. Sem revisão do orador.) - Falo agora.\n"
        ),
        "esperado": 2,
    },
    {
        "nome": "marcador SEM parênteses (pedido breve), seguido de marcador normal "
                "-- reproduz o padrão real achado no DCD08DEZ1999 p60567",
        "texto": (
            "O SR. WALTER PINHEIRO - Sr. Presidente,\n"
            "peço a palavra pela ordem.\n"
            "\n"
            "O SR. PRESIDENTE (Michel Temer) - Tem V. Exª\n"
            "a palavra.\n"
            "\n"
            "O SR. WALTER PINHEIRO (PT - BA. Sem revi-\n"
            "são do orador.) - Sr. Presidente, só para facilitar...\n"
        ),
        "esperado": 3,  # 2x Walter Pinheiro + 1x Presidente
    },
    {
        "nome": "dois marcadores na MESMA linha, sem quebra entre eles",
        "texto": (
            "O SR. FULANO (PT - BA.) - Sim. O SR. PRESIDENTE (Michel Temer) - Próximo.\n"
        ),
        "esperado": 2,
    },
    {
        "nome": "marcador sem parênteses no MEIO (não no início) de uma sequência",
        "texto": (
            "O SR. PRESIDENTE (Michel Temer) - Em votação.\n"
            "O SR. BISPO RODRIGUES - Sr. Presidente, peço a palavra.\n"
            "O SR. PRESIDENTE (Michel Temer) - Concedida.\n"
            "O SR. BISPO RODRIGUES (Bloco/PL - RJ. Sem revisão do orador.) - Obrigado.\n"
        ),
        "esperado": 4,
    },
]


def main() -> None:
    print("=" * 78)
    print("TESTE -- marcador perdido quando próximo de outro?")
    print("=" * 78)

    falhas = []
    for caso in CASOS:
        achados = list(so._RE_MARCADOR_CORPO.finditer(caso["texto"]))
        ok = len(achados) == caso["esperado"]
        print(f"\n[{'OK' if ok else 'FALHOU'}] {caso['nome']}")
        print(f"  esperado: {caso['esperado']}, achado: {len(achados)}")
        for m in achados:
            print(f"    -> {m.group(1).strip()!r}  parênteses={m.group(2)!r}")
        if not ok:
            falhas.append(caso["nome"])

    print("\n" + "-" * 78)
    if falhas:
        print(f"{len(falhas)} de {len(CASOS)} caso(s) falharam:")
        for f in falhas:
            print(f"  - {f}")
        print("\nCONCLUSÃO: a causa NÃO é proximidade entre marcadores -- os casos "
              "de adjacência pura (incluindo mesmo orador duas vezes seguidas) "
              "passam. A causa é a AUSÊNCIA DE PARÊNTESES no pedido breve de "
              "palavra ('O SR. NOME - Sr. Presidente, peço a palavra.'), formato "
              "legítimo e recorrente nos Diários, não um erro de OCR isolado. "
              "Vai se repetir nos outros 7 DCDs, sempre que alguém pedir a palavra "
              "e só depois a falar de verdade (2 marcadores, 1 sem parênteses).")
    else:
        print("todos os casos passaram -- nenhuma evidência de perda por proximidade")


if __name__ == "__main__":
    main()
