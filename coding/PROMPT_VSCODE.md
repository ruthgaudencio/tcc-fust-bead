Codifique o eixo discursivo dos dois corpora.

**Critério.** Leia `coding/INSTRUMENTO_CODIFICACAO.md` e siga apenas o que está
nele. Esse documento é a única fonte do critério. Esta mensagem não o
redefine, não o resume e não acrescenta nada a ele. Se algo nesta mensagem
parecer conflitar com o instrumento, o instrumento prevalece.

**Material.** `coding/lotes/` tem 126 arquivos, 66 do BEAD e 60 do FUST,
indexados em `coding/lotes/_indice_lotes.csv`. Cada arquivo traz até 20 pares
(fala, subcategoria), e cada par traz os trechos literais em que os termos da
lista foram encontrados, com o deslocamento no corpo do documento.

**Saída.** Acrescente uma linha por par em `coding/pares_eixo_discursivo.csv`,
com as colunas na ordem do item 6 do instrumento. Crie o arquivo com cabeçalho
se ele não existir.

**Como processar.**

1. Leia `coding/pares_eixo_discursivo.csv`, se existir, e monte o conjunto dos
   `par_id` já codificados.
2. Processe um arquivo de lote por vez, na ordem do índice, pulando os pares já
   presentes. Grave no CSV ao terminar cada lote, nunca só no fim: a execução
   precisa poder ser interrompida e retomada sem perder trabalho.
3. Depois de cada lote, imprima uma linha: nome do lote, pares codificados,
   e as contagens de estrutural, superficial, falso positivo e indeterminado.
4. Não paralelize. Não pule lote. Não reordene.

**Regras que não podem ser relaxadas.**

- `trecho_evidencia` é copiado literalmente de uma das janelas do próprio par.
  Não parafraseie, não junte pedaços de janelas diferentes, não complete o
  período com texto que não está ali.
- Quando os trechos não bastarem para decidir, use `indeterminado`. Não escolha
  entre `sim` e `nao` por verossimilhança.
- Quando `n_janelas_omitidas` for maior que zero e as janelas disponíveis não
  bastarem para `estrutural`, use `indeterminado` e escreva `janelas_omitidas`
  em `notas`.
- Codifique o FUST e o BEAD com a mesma régua. A língua e o gênero documental
  mudam, o critério não.
- Não procure confirmar nem refutar nenhuma expectativa sobre o resultado de
  uma subcategoria ou de um caso. Se eu tiver mencionado alguma, ignore.

**Ao terminar**, rode `python3 coding/agregar_eixo_discursivo.py` e me mostre a
tabela das 34 células, com o número de pares indeterminados de cada uma.

**Se algo no instrumento estiver ambíguo para um par concreto**, pare, me diga
qual par e qual é a ambiguidade, e espere. Não resolva por conta própria e não
registre a sua interpretação como se fosse o critério.
