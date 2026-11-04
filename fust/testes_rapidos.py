"""Testes com dados sintéticos — validam a mecânica, não substituem o corpus."""

from datetime import date

from diario_refs import agrupar_por_arquivo, extrair_refs, nome_arquivo
from textnorm import (
    buscar_termos,
    construir_lexico,
    detectar_colagens,
    normalizar,
    rebaixar,
    reparar_colagens,
)

falhas = 0


def checar(nome, cond, extra=""):
    global falhas
    print(("  ok   " if cond else "  FALHA") + f" {nome}" + (f"  {extra}" if extra else ""))
    if not cond:
        falhas += 1


print("\n[1] parser de referências de Diário")

VARIANTES = [
    ("DCD 01 09 00 PAG 44321", date(2000, 9, 1), 44321),
    ("DCD 01/09/2000 PÁG 44321", date(2000, 9, 1), 44321),
    ("DCD 01 SET 2000 pág. 44321", date(2000, 9, 1), 44321),
    ("DCD 12-11-97, PAGS. 36012", date(1997, 11, 12), 36012),
    ("DSF 23.06.1999 P. 15880", date(1999, 6, 23), 15880),
    ("DCD 09 DEZ 99", date(1999, 12, 9), None),
]
for bruto, d_esp, p_esp in VARIANTES:
    r = extrair_refs(bruto)
    ok = len(r) == 1 and r[0].data == d_esp and r[0].pagina_inicial == p_esp
    checar(repr(bruto), ok, str(r[0]) if r else "nada casou")

duplo = "Publicado DCD 01 09 00 PAG 44321 e retificado DCD 05/09/2000 PÁG 44500."
checar("duas citações no mesmo despacho", len(extrair_refs(duplo)) == 2)

faixa = extrair_refs("DCD 01 SET 2000 PAGS. 44321 A 44340")
checar(
    "faixa de páginas",
    len(faixa) == 1 and faixa[0].pagina_final == 44340,
    str(faixa[0]) if faixa else "",
)

checar(
    "composição do nome do arquivo",
    nome_arquivo("DCD", date(2000, 9, 1)) == "DCD01SET2000.pdf",
    nome_arquivo("DCD", date(2000, 9, 1)),
)

checar("texto sem referência não gera falso positivo",
       extrair_refs("Aprovado o Substitutivo do Senado, art. 60 de 1999.") == [])

grupos = agrupar_por_arquivo(extrair_refs(duplo))
checar("agrupamento por arquivo", len(grupos) == 2, list(grupos))


print("\n[2] colagem de espaço")

LIMPO = """
O Fundo de Universalização dos Serviços de Telecomunicações tem por finalidade
proporcionar recursos destinados a cobrir a parcela de custo exclusivamente
atribuível ao cumprimento das obrigações de universalização de serviços de
telecomunicações que não possa ser recuperada com a exploração eficiente do
serviço, conforme o disposto no inciso II do art. 81 da Lei Geral.
"""
SUJO = (
    "oFundo deUniversalizacao dos Servicos deTelecomunicacoes temporfinalidade "
    "proporcionar recursosdestinados acobrir aparcela decusto exclusivamente "
    "atribuivel aocumprimento dasobrigacoes deuniversalizacao deservicos"
)

lex = construir_lexico([LIMPO])

n_limpo = normalizar(LIMPO)
n_sujo = normalizar(SUJO)
c_limpo = detectar_colagens(n_limpo, lex)
c_sujo = detectar_colagens(n_sujo, lex)

checar("texto limpo = 0 colagens", len(c_limpo) == 0, f"achou {len(c_limpo)}")
checar("texto sujo > 0 colagens", len(c_sujo) >= 6, f"achou {len(c_sujo)}")
for c in c_sujo[:6]:
    print(f"         {c.token!r} -> {' + '.join(c.partes)}  [{c.detector}]")

camel = detectar_colagens(normalizar("palavra deTelecomunicacoes aqui"), lex)
checar("detector camel", any(c.detector == "camel" for c in camel))

tripla = detectar_colagens(normalizar("temporfinalidade"), lex)
checar("colagem de tres palavras", len(tripla) == 1 and len(tripla[0].partes) == 3,
       " + ".join(tripla[0].partes) if tripla else "nao detectou")

for falso in ["Universalizacao", "telecomunicacoes", "exclusivamente"]:
    checar(f"sem falso positivo em {falso!r}",
           detectar_colagens(normalizar(falso), lex) == [])


print("\n[3] busca com volta ao offset original (o teste do item 5)")

TERMO = "universalizacao"  # palavra inteira, para o teste de limite
antes = buscar_termos(rebaixar(n_sujo), [TERMO], limites_de_palavra=True)
reparado = rebaixar(reparar_colagens(n_sujo, c_sujo))
depois = buscar_termos(reparado, [TERMO], limites_de_palavra=True)

checar("com limite de palavra, texto colado esconde o termo", len(antes) == 0,
       f"{len(antes)} hits")
checar("depois do reparo o termo aparece", len(depois) >= 2, f"{len(depois)} hits")

# o critério do TCC usa radicais ("universaliza", "fust"), que são prefixos:
# aí a busca é por substring e acha mesmo sem reparo
radical = buscar_termos(reparado, ["universaliza"])
checar("busca por radical, sem limite de palavra", len(radical) >= 2,
       f"{len(radical)} hits")

ok_roundtrip = True
for oc in depois:
    trecho = SUJO[oc.inicio_original : oc.fim_original]
    if "niversaliza" not in trecho.lower():
        ok_roundtrip = False
    print(f"         norm[{oc.inicio_norm}:{oc.fim_norm}] -> "
          f"original[{oc.inicio_original}:{oc.fim_original}] = {trecho!r}")
checar("offset volta ao trecho certo do original", ok_roundtrip)

acento = normalizar("a universalização dos serviços")
hit = buscar_termos(rebaixar(acento), ["universalização"])
checar("acento normalizado dos dois lados", len(hit) == 1 and
       hit[0].fragmento.lower() == "universalização", hit[0].fragmento if hit else "")

quebra = normalizar("das tele-\ncomunicacoes brasileiras")
h2 = buscar_termos(rebaixar(quebra), ["telecomunicacoes"])
checar("hífen de quebra de linha é religado", len(h2) == 1,
       repr(h2[0].fragmento) if h2 else "")

print(f"\n{'TUDO OK' if not falhas else str(falhas) + ' FALHA(S)'}\n")
raise SystemExit(1 if falhas else 0)
