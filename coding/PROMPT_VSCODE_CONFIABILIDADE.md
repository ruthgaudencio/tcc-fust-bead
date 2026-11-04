Codifique o eixo discursivo dos pares em `coding/lotes_confiabilidade/`.

**Critério.** Leia `coding/INSTRUMENTO_CODIFICACAO.md` e siga apenas o que está
nele. Esse documento é a única fonte do critério. Esta mensagem não o redefine,
não o resume e não acrescenta nada a ele. Se algo nesta mensagem parecer
conflitar com o instrumento, o instrumento prevalece.

**Material.** `coding/lotes_confiabilidade/` tem 6 arquivos, indexados em
`_indice_lotes.csv`, com 120 pares (fala, subcategoria), 66 do FUST e 54 do
BEAD. Cada par traz os trechos literais em que os termos da lista foram
encontrados, com o deslocamento no corpo do documento.

**Saída.** Uma linha por par em `coding/pares_confiabilidade.csv`, com as
colunas na ordem do item 6 do instrumento. Crie o arquivo com cabeçalho. Grave
somente nesse arquivo.

**Arquivos que não devem ser abertos.** Não leia, não consulte e não use como
referência nenhum destes: `coding/pares_eixo_discursivo.csv`, qualquer arquivo
começado por `pares_eixo_discursivo_backup`, `coding/eixo_discursivo.csv`,
`coding/delta_singulares.csv`, `coding/amostra_confiabilidade.csv`,
`coding/verificacao_trechos.csv` e a pasta `coding/_antes_singulares_normativo/`.
Decida cada par apenas a partir do instrumento e das janelas do próprio par.

**Como processar.**

1. Processe um arquivo de lote por vez, na ordem do índice. Grave no CSV ao
   terminar cada lote, nunca só no fim.
2. Depois de cada lote, imprima uma linha: nome do lote, pares codificados, e as
   contagens de estrutural, superficial, falso positivo e indeterminado.
3. Não paralelize. Não pule lote. Não reordene.

**Regras que não podem ser relaxadas.**

- `trecho_evidencia` é copiado literalmente de uma das janelas do próprio par.
  Não parafraseie, não junte pedaços de janelas diferentes com reticências, não
  complete o período com texto que não está ali e não cite trecho que esteja
  fora das janelas apresentadas.
- Quando os trechos não bastarem para decidir, use `indeterminado`. Não escolha
  entre `sim` e `nao` por verossimilhança.
- Quando `n_janelas_omitidas` for maior que zero e as janelas disponíveis não
  bastarem para `estrutural`, use `indeterminado` e escreva `janelas_omitidas`
  em `notas`.
- Codifique o FUST e o BEAD com a mesma régua. A língua e o gênero documental
  mudam, o critério não.
- Não procure confirmar nem refutar nenhuma expectativa sobre o resultado de
  uma subcategoria ou de um caso. Se eu tiver mencionado alguma, ignore.

**Ao terminar**, informe apenas quantos pares foram codificados e a contagem de
cada nível. O arquivo tem que ficar com 120 linhas de dados mais o cabeçalho.

**Se algo no instrumento estiver ambíguo para um par concreto**, pare, me diga
qual par e qual é a ambiguidade, e espere. Não resolva por conta própria e não
registre a sua interpretação como se fosse o critério.
