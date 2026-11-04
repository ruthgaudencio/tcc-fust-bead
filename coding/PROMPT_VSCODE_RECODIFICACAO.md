Complete a codificação do eixo discursivo. A maior parte já está feita; esta
rodada fecha o que falta.

**Por que falta algo.** O léxico do sistema US só tinha as formas plurais de 23
termos (`schools`, `families`, `veterans`), então as ocorrências no singular
não eram encontradas. As formas singulares foram acrescentadas, o léxico US foi
de 87 para 110 termos, a passada léxica do BEAD foi refeita e os lotes foram
reconstruídos. O FUST não foi afetado: os 1.196 pares dele continuam idênticos.

**Critério.** Leia `coding/INSTRUMENTO_CODIFICACAO.md` e siga apenas o que está
nele. Esse documento é a única fonte do critério. Esta mensagem não o
redefine, não o resume e não acrescenta nada a ele. Se algo nesta mensagem
parecer conflitar com o instrumento, o instrumento prevalece.

**Material.** `coding/lotes/` tem 137 arquivos, 77 do BEAD e 60 do FUST,
indexados em `coding/lotes/_indice_lotes.csv`. Cada arquivo traz até 20 pares
(fala, subcategoria), e cada par traz os trechos literais em que os termos da
lista foram encontrados, com o deslocamento no corpo do documento.

**Saída.** Acrescente uma linha por par em `coding/pares_eixo_discursivo.csv`,
com as colunas na ordem do item 6 do instrumento. O arquivo já existe, com
2.321 pares codificados e cabeçalho. Não o reescreva, não reordene as linhas
existentes e não altere nenhuma linha que já esteja lá.

**Como processar.**

1. Leia `coding/pares_eixo_discursivo.csv` e monte o conjunto dos `par_id` já
   codificados. São 2.321.
2. Processe um arquivo de lote por vez, na ordem do índice, pulando os pares já
   presentes. Grave no CSV ao terminar cada lote, nunca só no fim: a execução
   precisa poder ser interrompida e retomada sem perder trabalho.
3. Depois de cada lote, imprima uma linha: nome do lote, pares codificados,
   e as contagens de estrutural, superficial, falso positivo e indeterminado.
4. Não paralelize. Não pule lote. Não reordene.

**Quantos pares esperar.** Ao todo 415, sobre um universo de 2.736. São 238
pares que não existiam antes, 175 cujas janelas de texto mudaram porque
ganharam ocorrência nova, e 2 que ficaram de fora da rodada anterior. Todos são
do BEAD. A conta tem que fechar em 2.736 linhas no final. Se você chegar ao fim
do índice com um número diferente, pare e me diga, em vez de ajustar.

**Regras que não podem ser relaxadas.**

- `trecho_evidencia` é copiado literalmente de uma das janelas do próprio par.
  Não parafraseie, não junte pedaços de janelas diferentes, não complete o
  período com texto que não está ali.
- Quando os trechos não bastarem para decidir, use `indeterminado`. Não escolha
  entre `sim` e `nao` por verossimilhança.
- Quando `n_janelas_omitidas` for maior que zero e as janelas disponíveis não
  bastarem para `estrutural`, use `indeterminado` e escreva `janelas_omitidas`
  em `notas`.
- Codifique com a mesma régua usada na rodada anterior. O instrumento não
  mudou. O que mudou foi só o léxico de busca.
- Não procure confirmar nem refutar nenhuma expectativa sobre o resultado de
  uma subcategoria ou de um caso. Se eu tiver mencionado alguma, ignore.
- Os pares recodificados não trazem o código antigo. Não tente recuperá-lo de
  `coding/pares_eixo_discursivo_backup_20261031_1854.csv` nem de qualquer outro
  backup, e não o use como referência. Codifique do zero, a partir das janelas.

**Ao terminar**, rode `python3 coding/agregar_eixo_discursivo.py` e me mostre a
tabela das 34 células, com o número de pares indeterminados de cada uma.

**Se algo no instrumento estiver ambíguo para um par concreto**, pare, me diga
qual par e qual é a ambiguidade, e espere. Não resolva por conta própria e não
registre a sua interpretação como se fosse o critério.
