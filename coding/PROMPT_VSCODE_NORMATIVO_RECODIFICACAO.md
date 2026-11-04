Complete a codificação do eixo normativo. A maior parte já está feita; esta
rodada fecha o que falta.

**Por que falta algo.** O léxico do sistema US só tinha as formas plurais de 23
termos (`schools`, `families`, `veterans`), então as ocorrências no singular não
eram encontradas. As formas singulares foram acrescentadas, o léxico US foi de
87 para 110 termos, e a varredura dos textos aprovados foi refeita. O universo
passou de 194 para 221 dispositivos. O FUST não foi afetado: continua com 11.

**Critério.** Leia `coding/INSTRUMENTO_NORMATIVO.md` e siga apenas o que está
nele. É a única fonte do critério; esta mensagem não o redefine. Em conflito, o
instrumento prevalece.

**Material.** `coding/lotes_normativo/` tem 19 arquivos, indexados em
`_indice_lotes.csv`, com 221 dispositivos, 11 do FUST e 210 do BEAD. Cada
dispositivo traz o trecho da lei, o diploma de origem, a subcategoria atribuída
e os termos que dispararam a menção.

**Saída.** Uma linha por dispositivo em
`coding/dispositivos_eixo_normativo.csv`, colunas na ordem do item 5 do
instrumento. O arquivo já existe, com 154 dispositivos codificados e cabeçalho.
Não o reescreva e não altere nenhuma linha que já esteja lá.

**Como processar.** Um lote por vez, na ordem do índice, pulando `disp_id` já
presente no CSV. Grave ao fim de cada lote. Depois de cada um, imprima: lote,
dispositivos codificados, e as contagens de estrutural, superficial, falso
positivo e indeterminado.

**Quantos esperar.** 67 dispositivos: 27 que não existiam antes e 40 cujo trecho
de lei mudou de extensão porque ganharam menção nova. A conta tem que fechar em
221 linhas no final. Se chegar ao fim do índice com número diferente, pare e me
diga, em vez de ajustar.

**A regra que mais erra.** O mecanismo precisa recair sobre a subcategoria
codificada, não apenas comparecer no mesmo dispositivo. O teste está no item 2.3
do instrumento: se a subcategoria fosse suprimida do dispositivo, o mecanismo
deixaria de operar? Aplique esse teste em todo dispositivo que receber
`vinculante: sim`, e registre o resultado dele na justificativa.

**Os recodificados não trazem o código antigo.** Não tente recuperá-lo de
`coding/_antes_singulares_normativo/` nem de qualquer outro backup, e não o use
como referência. Codifique do zero, a partir do trecho.

**Escopo.** Os dispositivos do `47 U.S.C. 1721` foram retirados do universo, por
duplicarem o texto da SEC. 60302, e as 13 linhas correspondentes já saíram do
CSV. Os lotes atuais trazem apenas o que está em escopo: codifique tudo o que
estiver neles, sem ponderar inclusão, e não sugira alteração de escopo.

**Ao terminar**, rode `python3 coding/agregar_eixo_normativo.py --comparar` e me
mostre a tabela com os escopos lado a lado.

**Se o instrumento for ambíguo para um dispositivo concreto**, pare, diga qual e
qual a ambiguidade, e espere.
