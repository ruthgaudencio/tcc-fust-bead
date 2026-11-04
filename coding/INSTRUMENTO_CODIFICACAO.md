# Instrumento de codificação do eixo discursivo

Este documento é a instrução de codificação. Ele é reproduzido como apêndice da
monografia e é a única fonte do critério: nenhuma instrução enviada ao modelo
redefine o que está aqui.

## 1. O que é codificado

A unidade de codificação é o **par (fala, subcategoria)**: cada fala em que uma
subcategoria de desigualdade foi invocada por pelo menos um termo da lista. São
2.498 pares, 1.196 no corpus brasileiro e 1.302 no norte-americano.

O nível de cada subcategoria em cada caso não é julgado diretamente. Ele é
**agregado** a partir dos pares, pela regra do item 5.

## 2. As três decisões, nesta ordem

Para cada par, decidir três coisas, olhando apenas os trechos fornecidos.

### 2.1 Pertinência

O termo encontrado invoca, naquele trecho, a subcategoria a que foi atribuído?

- `sim` — o termo se refere ao grupo ou à posição que a subcategoria nomeia.
- `nao` — o termo aparece em outro sentido. Exemplos: "família" numa homenagem
  fúnebre não invoca arranjo familiar; "campo" no sentido de área de
  conhecimento não invoca o rural; um nome próprio que contém a palavra.
- `indeterminado` — o trecho não permite decidir.

Pertinência `nao` encerra o par: as duas decisões seguintes ficam vazias.

### 2.2 Razão declarada

O trecho declara uma razão que vincule aquele grupo ao tratamento proposto?

Razão declarada é uma afirmação de **por que** aquele grupo deve receber
atenção, recurso ou tratamento distinto. Não basta nomear o grupo, nem afirmar
que ele é numeroso, nem lamentar sua situação.

- `sim` — há uma proposição do tipo "porque", explícita ou imediatamente
  reconstituível do período: o grupo está em desvantagem X, por isso a medida Y
  deve alcançá-lo; sem a medida, o grupo permanece excluído de Z.
- `nao` — o grupo é nomeado em lista, em saudação, em enumeração de
  beneficiários, em exposição de motivos genérica, ou mencionado sem ligação com
  a medida discutida.
- `indeterminado` — há indício de razão cortado pelo limite do trecho.

### 2.3 Dado ou diagnóstico

O trecho traz dado ou diagnóstico que sustente a razão?

- `sim` — número, proporção, série, resultado de levantamento, censo, pesquisa,
  mapeamento, ou diagnóstico atribuído a fonte identificável, ainda que sem
  número exato ("o mapeamento da agência mostra que").
- `nao` — afirmação de magnitude sem fonte nem quantificação ("é sabido que a
  maioria", "todos conhecem a situação"), ou nenhum elemento factual.
- `indeterminado` — há referência a dado cuja substância ficou fora do trecho.

## 3. Nível do par

Derivado das três decisões, sem julgamento adicional:

| pertinência | razão | dado | nível do par |
|---|---|---|---|
| nao | — | — | `falso_positivo` |
| sim | sim | sim | `estrutural` |
| sim | qualquer outro | qualquer outro | `superficial` |
| indeterminado | — | — | `indeterminado` |

## 4. Regras de conduta da codificação

**Não preencher por inferência.** `indeterminado` existe para ser usado. Um par
marcado `indeterminado` é tratado como nível não alcançado na agregação, e o
número de indeterminados é reportado. Escolher entre `sim` e `nao` sem base no
trecho produz resultado que não se sustenta em conferência.

**Citar sempre.** Todo par com pertinência `sim` recebe um trecho literal de até
300 caracteres, copiado dos trechos fornecidos, que é a evidência da decisão.
Trecho inventado ou parafraseado invalida o par.

**Não consultar o nível esperado.** A codificação não recebe, em nenhum momento,
expectativa sobre o resultado de uma subcategoria ou de um caso. Previsão na
instrução ancora o resultado.

**Mesma instrução nos dois casos.** O corpus brasileiro e o norte-americano são
codificados com este mesmo documento, sem ajuste de critério por língua ou por
gênero documental. O que varia é o material, não a régua.

**Pares com janela omitida.** Quando `n_janelas_omitidas` é maior que zero, o par
tem mais ocorrências do que as mostradas. Se as janelas disponíveis bastarem
para `estrutural`, o par está decidido. Se não bastarem, o par recebe
`indeterminado` e o campo `notas` registra `janelas_omitidas`, para que a
varredura complementar o reexamine.

## 5. Agregação ao nível da subcategoria

Executada por `agregar_eixo_discursivo.py`, pela regra do **nível mais alto
alcançado**, decidida pela pesquisadora:

- `estrutural` — algum par da célula é `estrutural`;
- `superficial` — nenhum par é `estrutural` e algum é `superficial`;
- `ausente` — a célula não tem par pertinente, isto é, não há ocorrência válida.

A regra responde à hipótese, que pergunta se a equidade foi nomeada com razão e
dado em algum ponto do processo legislativo, e não com que frequência. A
contrapartida é que o nível não mede densidade do discurso: uma menção
estrutural entre trezentas superficiais produz célula estrutural. As contagens de
cada nível ficam registradas ao lado do nível agregado, de modo que a densidade
permaneça legível.

## 6. Formato de saída

Um registro por par, em `coding/pares_eixo_discursivo.csv`:

```
par_id, caso, unit_id, subcategoria, codigo, pertinencia, razao_declarada,
dado_ou_diagnostico, nivel_do_par, trecho_evidencia, justificativa, notas
```

`justificativa` tem uma linha, diz em que o trecho sustenta a decisão e não
repete a definição do critério.
