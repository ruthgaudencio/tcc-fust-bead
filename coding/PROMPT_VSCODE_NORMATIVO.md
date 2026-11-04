Codifique o eixo normativo.

**Critério.** Leia `coding/INSTRUMENTO_NORMATIVO.md` e siga apenas o que está
nele. É a única fonte do critério; esta mensagem não o redefine. Em conflito, o
instrumento prevalece.

**Material.** `coding/lotes_normativo/` tem 17 arquivos, indexados em
`_indice_lotes.csv`, com 194 dispositivos no total, 11 do FUST e 183 do BEAD.
Desses, 145 já constam de `coding/dispositivos_eixo_normativo.csv` e devem ser
pulados; faltam 49, concentrados nos lotes 1 a 5, que são os do Digital Equity
Act, incorporado ao escopo depois da primeira rodada.
Cada dispositivo traz o trecho da lei, o diploma de origem, a subcategoria
atribuída e os termos que dispararam a menção.

**Saída.** Uma linha por dispositivo em
`coding/dispositivos_eixo_normativo.csv`, colunas na ordem do item 5 do
instrumento. Crie com cabeçalho se não existir.

**Como processar.** Um lote por vez, na ordem do índice, pulando `disp_id` já
presente no CSV. Grave ao fim de cada lote. Depois de cada um, imprima: lote,
dispositivos codificados, e as contagens de estrutural, superficial, falso
positivo e indeterminado.

**A regra que mais erra.** O mecanismo precisa recair sobre a subcategoria
codificada, não apenas comparecer no mesmo dispositivo. O teste está no item 2.3
do instrumento: se a subcategoria fosse suprimida do dispositivo, o mecanismo
deixaria de operar? Aplique esse teste em todo dispositivo que receber
`vinculante: sim`, e registre o resultado dele na justificativa.

**Não decida o escopo.** Alguns dispositivos vêm de diplomas cuja inclusão no
texto aprovado ainda não foi decidida, conforme
`coding/ESCOPO_TEXTO_APROVADO.md`. Codifique todos, sem ponderar se entram ou
não: a agregação filtra depois. Não sugira qual escopo adotar.

**Ao terminar**, rode `python3 coding/agregar_eixo_normativo.py --comparar` e me
mostre a tabela com os três escopos lado a lado.

**Se o instrumento for ambíguo para um dispositivo concreto**, pare, diga qual e
qual a ambiguidade, e espere.
