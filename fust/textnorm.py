"""
Normalização de texto com preservação de offset + detecção e reparo de
colagem de espaço (palavras grudadas por falha de OCR).

Contrato central: toda transformação devolve um `Normalizado`, que carrega
`src_map` — para cada caractere do texto transformado, o índice do caractere
correspondente no texto ORIGINAL. Isso é o que permite achar um termo no texto
tratado e voltar ao offset exato no documento de origem.

Pipeline de uso:

    n1 = normalizar(bruto, tirar_acentos=True, rebaixar_caixa=False)
    lex = construir_lexico([texto_mate, texto_lei9998])   # só nativos digitais
    cols = detectar_colagens(n1, lex)                     # métrica do item 4
    n2 = reparar_colagens(n1, cols)
    n3 = rebaixar(n2)
    hits = buscar_termos(n3, ["universaliza", "fust"])
    for h in hits:
        bruto[h.inicio_original:h.fim_original]           # volta ao original
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

__all__ = [
    "Normalizado",
    "normalizar",
    "rebaixar",
    "construir_lexico",
    "Colagem",
    "detectar_colagens",
    "contar_colagens",
    "reparar_colagens",
    "Ocorrencia",
    "buscar_termos",
    "contexto",
]


# ---------------------------------------------------------------------------
# Estrutura base
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Normalizado:
    """Texto transformado + mapa de volta para o original."""

    texto: str
    src_map: tuple[int, ...]
    original: str

    def __post_init__(self) -> None:
        if len(self.texto) != len(self.src_map):
            raise ValueError(
                f"src_map dessincronizado: texto={len(self.texto)} "
                f"map={len(self.src_map)}"
            )

    def para_original(self, i: int) -> int:
        """Índice no original correspondente ao caractere `i` do texto tratado."""
        return self.src_map[i]

    def faixa_original(self, inicio: int, fim: int) -> tuple[int, int]:
        """Converte um span [inicio, fim) do texto tratado para o original.

        O span devolvido é conservador: pode ser levemente mais largo que o
        trecho tratado, porque caracteres inseridos no reparo apontam para o
        caractere original seguinte.
        """
        if inicio >= fim:
            return (self.src_map[inicio], self.src_map[inicio])
        return (self.src_map[inicio], self.src_map[fim - 1] + 1)

    def fragmento_original(self, inicio: int, fim: int) -> str:
        a, b = self.faixa_original(inicio, fim)
        return self.original[a:b]


def _identidade(texto: str) -> Normalizado:
    return Normalizado(texto, tuple(range(len(texto))), texto)


def _aplicar_regex(
    chars: list[str],
    idx: list[int],
    padrao: re.Pattern[str],
    repl: Callable[[re.Match[str]], str],
) -> tuple[list[str], list[int]]:
    """Substituição por regex mantendo o mapa de offsets.

    Todo caractere produzido pela substituição herda o índice original do
    primeiro caractere do trecho casado.
    """
    s = "".join(chars)
    out_c: list[str] = []
    out_i: list[int] = []
    pos = 0
    for m in padrao.finditer(s):
        out_c.extend(chars[pos : m.start()])
        out_i.extend(idx[pos : m.start()])
        novo = repl(m)
        if novo:
            base = idx[m.start()]
            out_c.extend(novo)
            out_i.extend([base] * len(novo))
        pos = m.end()
    out_c.extend(chars[pos:])
    out_i.extend(idx[pos:])
    return out_c, out_i


def _por_caractere(
    chars: list[str], idx: list[int], fn: Callable[[str], str]
) -> tuple[list[str], list[int]]:
    out_c: list[str] = []
    out_i: list[int] = []
    for ch, i in zip(chars, idx):
        for c in fn(ch):
            out_c.append(c)
            out_i.append(i)
    return out_c, out_i


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------

_INVISIVEIS = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff]")
# hífen de quebra de linha: "tele-\ncomunicações" -> "telecomunicações"
_HIFEN_QUEBRA = re.compile(r"(?<=\w)[-\u2010\u2011\u2012\u2013]\s*\n\s*(?=\w)")
_ESPACOS = re.compile(r"[^\S\n]+")
_QUEBRAS = re.compile(r"\n{3,}")


def _tirar_acentos_char(ch: str) -> str:
    d = unicodedata.normalize("NFD", ch)
    base = "".join(c for c in d if not unicodedata.combining(c))
    return base if base else ""


def normalizar(
    original: str,
    *,
    tirar_acentos: bool = True,
    rebaixar_caixa: bool = False,
    juntar_hifen_quebra: bool = True,
    colapsar_espaco: bool = True,
) -> Normalizado:
    """Normaliza preservando o mapa de offsets.

    Por padrão a caixa é PRESERVADA, porque o detector `camel` de colagem
    depende da transição minúscula->maiúscula. Rebaixe a caixa depois da
    detecção, com `rebaixar()`.
    """
    chars = list(original)
    idx = list(range(len(original)))

    chars, idx = _aplicar_regex(chars, idx, _INVISIVEIS, lambda m: "")
    if juntar_hifen_quebra:
        chars, idx = _aplicar_regex(chars, idx, _HIFEN_QUEBRA, lambda m: "")
    if tirar_acentos:
        chars, idx = _por_caractere(chars, idx, _tirar_acentos_char)
    if rebaixar_caixa:
        chars, idx = _por_caractere(chars, idx, str.lower)
    if colapsar_espaco:
        chars, idx = _aplicar_regex(chars, idx, _ESPACOS, lambda m: " ")
        chars, idx = _aplicar_regex(chars, idx, _QUEBRAS, lambda m: "\n\n")

    return Normalizado("".join(chars), tuple(idx), original)


def rebaixar(n: Normalizado) -> Normalizado:
    """Rebaixa a caixa. Mantém o mapa (str.lower pode expandir; é tratado)."""
    chars, idx = _por_caractere(list(n.texto), list(n.src_map), str.lower)
    return Normalizado("".join(chars), tuple(idx), n.original)


# ---------------------------------------------------------------------------
# Léxico
# ---------------------------------------------------------------------------

_RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def _chave(tok: str) -> str:
    return "".join(_tirar_acentos_char(c) for c in tok).lower()


#  Palavras funcionais que grudam no início do token seguinte em OCR ruim
#  ("ofust", "detelecomunicacoes", "aolei").
FUNCIONAIS: frozenset[str] = frozenset(
    """
    a o as os um uma uns umas
    de do da dos das dum duma num numa
    em no na nos nas ao aos pelo pela pelos pelas
    por para com sem sob sobre entre ate apos
    e ou que se nao ja so mais muito
    """.split()
)


def construir_lexico(
    textos: Iterable[str], *, min_len: int = 3, min_cont: int = 1
) -> frozenset[str]:
    """Constrói o léxico a partir de textos LIMPOS (nativos digitais).

    Importante: não alimente com o texto OCRizado do Diário. O léxico é o
    gabarito do que é palavra de verdade; se o lixo de OCR entrar nele, a
    contagem de colagens desaba.
    """
    cont: Counter[str] = Counter()
    for t in textos:
        for m in _RE_TOKEN.finditer(t):
            k = _chave(m.group(0))
            if len(k) >= min_len:
                cont[k] += 1
    base = {w for w, c in cont.items() if c >= min_cont}
    return frozenset(base | set(FUNCIONAIS))


# ---------------------------------------------------------------------------
# Colagem de espaço
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Colagem:
    """Um token marcado como colagem. Pode ter mais de um corte.

    "temporfinalidade" -> ("tem", "por", "finalidade"): dois cortes, um
    registro. A contagem de colagens é por TOKEN, não por corte.
    """

    token: str
    inicio: int  # offset no texto normalizado analisado
    fim: int
    cortes: tuple[int, ...]  # posições de corte dentro do token
    partes: tuple[str, ...]
    detector: str  # "camel" | "funcional" | "lexico"

    @property
    def corte(self) -> int:
        """Primeiro corte. Conveniência para os casos de colagem simples."""
        return self.cortes[0]


def _cortes_camel(tok: str) -> tuple[int, ...]:
    return tuple(
        i for i in range(1, len(tok)) if tok[i - 1].islower() and tok[i].isupper()
    )


def _parte_valida(
    parte: str, lexico: frozenset[str], min_parte: int, *, aceita_funcional: bool
) -> bool:
    if aceita_funcional and parte in FUNCIONAIS:
        return True
    return len(parte) >= min_parte and parte in lexico


def _segmentar(
    chave: str,
    lexico: frozenset[str],
    min_parte: int,
    *,
    aceita_funcional: bool,
    max_partes: int = 4,
) -> tuple[int, ...] | None:
    """Segmentação por programação dinâmica: menor número de partes válidas.

    Devolve as posições de corte, ou None se o token não se decompõe em pelo
    menos duas partes reconhecidas.
    """
    n = len(chave)
    # melhor[i] = (numero_de_partes, cortes) para o prefixo chave[:i]
    melhor: list[tuple[int, tuple[int, ...]] | None] = [None] * (n + 1)
    melhor[0] = (0, ())
    for i in range(1, n + 1):
        cand: tuple[int, tuple[int, ...]] | None = None
        for j in range(i):
            anterior = melhor[j]
            if anterior is None:
                continue
            if anterior[0] + 1 > max_partes:
                continue
            if not _parte_valida(
                chave[j:i], lexico, min_parte, aceita_funcional=aceita_funcional
            ):
                continue
            novo = (anterior[0] + 1, anterior[1] + ((j,) if j else ()))
            if cand is None or novo[0] < cand[0]:
                cand = novo
        melhor[i] = cand
    fim = melhor[n]
    if fim is None or fim[0] < 2:
        return None
    return fim[1]


def detectar_colagens(
    n: Normalizado,
    lexico: frozenset[str],
    *,
    detectores: Sequence[str] = ("camel", "funcional", "lexico"),
    min_len: int = 6,
    min_parte: int = 3,
    max_len: int = 40,
) -> list[Colagem]:
    """Detecta tokens que parecem ser palavras grudadas.

    Guarda principal: um token que já existe no léxico não é marcado. É isso
    que evita falso positivo em texto limpo ("dose" = "do" + "se" é ignorado
    porque "dose" está no léxico).

    Estratégia: primeiro os cortes por caixa (`camel`), que são os mais
    confiáveis; depois, dentro de cada segmento que sobrou e continua fora do
    léxico, uma segmentação por programação dinâmica. Isso cobre colagem de
    três ou mais palavras, comum em Diário digitalizado.

    `detectores`:
      camel      — transição minúscula->maiúscula dentro do token
      funcional  — permite partes curtas de FUNCIONAIS ("de", "por", "ao")
      lexico     — exige que toda parte tenha >= min_parte e esteja no léxico
    """
    usa_dp = "funcional" in detectores or "lexico" in detectores
    aceita_funcional = "funcional" in detectores

    achados: list[Colagem] = []
    for m in _RE_TOKEN.finditer(n.texto):
        tok = m.group(0)
        if not (min_len <= len(tok) <= max_len):
            continue
        chave = _chave(tok)
        if chave in lexico:
            continue

        cortes: tuple[int, ...] = ()
        if "camel" in detectores:
            cortes = _cortes_camel(tok)
        det = "camel" if cortes else ""

        # A segmentação trabalha sobre a chave; os índices só se alinham ao
        # token se o dobramento de acento não mudou o comprimento.
        if usa_dp and len(chave) == len(tok):
            extras: list[int] = []
            bordas = (0,) + cortes + (len(tok),)
            for a, b in zip(bordas, bordas[1:]):
                seg = chave[a:b]
                if len(seg) <= min_parte or seg in lexico:
                    continue
                sub = _segmentar(
                    seg, lexico, min_parte, aceita_funcional=aceita_funcional
                )
                if sub:
                    extras.extend(a + k for k in sub)
            if extras:
                cortes = tuple(sorted(set(cortes) | set(extras)))
                if not det:
                    det = "funcional" if aceita_funcional else "lexico"

        if not cortes:
            continue

        bordas = (0,) + cortes + (len(tok),)
        partes = tuple(tok[a:b] for a, b in zip(bordas, bordas[1:]))
        if det == "camel" and any(_chave(p) in FUNCIONAIS for p in partes):
            det = "camel"
        achados.append(
            Colagem(
                token=tok,
                inicio=m.start(),
                fim=m.end(),
                cortes=cortes,
                partes=partes,
                detector=det,
            )
        )
    return achados


def contar_colagens(n: Normalizado, lexico: frozenset[str], **kw) -> int:
    """Atalho para a métrica de validação do tratamento."""
    return len(detectar_colagens(n, lexico, **kw))


def reparar_colagens(n: Normalizado, colagens: Sequence[Colagem]) -> Normalizado:
    """Insere espaço nos pontos de corte, preservando o mapa.

    O espaço inserido recebe o índice original do caractere seguinte, então
    `faixa_original` continua devolvendo um span válido (no máximo 1 caractere
    mais largo) para qualquer trecho que atravesse um reparo.
    """
    cortes = sorted({c.inicio + k for c in colagens for k in c.cortes})
    if not cortes:
        return n

    out_c: list[str] = []
    out_i: list[int] = []
    pos = 0
    for corte in cortes:
        if corte <= pos:
            continue
        out_c.extend(n.texto[pos:corte])
        out_i.extend(n.src_map[pos:corte])
        out_c.append(" ")
        out_i.append(n.src_map[corte])
        pos = corte
    out_c.extend(n.texto[pos:])
    out_i.extend(n.src_map[pos:])
    return Normalizado("".join(out_c), tuple(out_i), n.original)


# ---------------------------------------------------------------------------
# Busca com offset de volta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ocorrencia:
    termo: str
    inicio_norm: int
    fim_norm: int
    inicio_original: int
    fim_original: int
    fragmento: str  # trecho LITERAL do original


def buscar_termos(
    n: Normalizado, termos: Iterable[str], *, limites_de_palavra: bool = False
) -> list[Ocorrencia]:
    """Busca termos no texto tratado e devolve offsets no original.

    `limites_de_palavra=False` por padrão de propósito: em texto com colagem
    residual, "fust" aparece dentro de "ofust" e você quer esse hit.
    """
    achados: list[Ocorrencia] = []
    for termo in termos:
        alvo = _chave(termo)
        if not alvo:
            continue
        padrao = re.escape(alvo)
        if limites_de_palavra:
            padrao = rf"\b{padrao}\b"
        rx = re.compile(padrao, re.IGNORECASE)
        for m in rx.finditer(n.texto):
            a, b = n.faixa_original(m.start(), m.end())
            achados.append(
                Ocorrencia(
                    termo=termo,
                    inicio_norm=m.start(),
                    fim_norm=m.end(),
                    inicio_original=a,
                    fim_original=b,
                    fragmento=n.original[a:b],
                )
            )
    achados.sort(key=lambda o: o.inicio_original)
    return achados


def contexto(n: Normalizado, oc: Ocorrencia, *, janela: int = 240) -> str:
    """Trecho de contexto, retirado do ORIGINAL, em volta da ocorrência."""
    a = max(0, oc.inicio_original - janela)
    b = min(len(n.original), oc.fim_original + janela)
    return n.original[a:b]
