# Coleta do corpus brasileiro: rotas de acesso e obstáculos

Este documento registra como as fontes primárias brasileiras foram obtidas e que
obstáculos a coleta encontrou. Serve a quem queira repetir ou estender o
levantamento, e explica por que certas decisões de tratamento foram tomadas.

O corpus norte-americano foi recolhido do congress.gov pelo procedimento
descrito em `corpus_bead/` e no capítulo 3 do trabalho, e não apresentou
obstáculos comparáveis.

## 1. Identificadores das matérias

Câmara dos Deputados, API de dados abertos v2:

    PL 3.808/1997, principal                 idProposicao 38109
    PL 3.938/1997, do Executivo, apensado    idProposicao 41154
    Emenda Substitutiva de Plenário nº 24    idProposicao 68783

Trinta e uma emendas figuram na interface como proposições próprias, com
identificadores sequenciais: as emendas de comissão 1 a 6, de 1998, nos
identificadores 68753 a 68758; a emenda 7, de 1999, no 68759; e as emendas de
Plenário 1 a 24, todas de 7 de dezembro de 1999, nos identificadores 68760 a
68783. O inteiro teor de cada uma exige consulta individual a `/proposicoes/{id}`.

Senado Federal, API de dados abertos:

    PLC 60/1999      codigoMateria 42696, idProcesso 3005683
    processo inicial idProcesso 3005680
    VET 31/2000      idProcesso 3349182

A norma gerada é a Lei nº 9.998, de 17 de agosto de 2000, publicada no Diário
Oficial da União de 18 de agosto de 2000, página 1; as razões do veto parcial
foram publicadas na página 18 da mesma edição.

## 2. Rotas utilizadas

No Senado, a coleta usou as rotas de processo, e não as de matéria: estas
anunciam desativação completa nas próprias respostas, em campo específico, o que
as torna inadequadas para trabalho que precise ser repetido. Os pronunciamentos
vieram de `/plenario/lista/discursos/{dataInicio}/{dataFim}`, com as datas em
formato AAAAMMDD, e o texto corrido de
`/discurso/texto-integral/{CodigoPronunciamento}`.

A especificação legível da interface está em `/dadosabertos/v3/api-docs`. A
documentação navegável é renderizada por JavaScript e não serve a leitura
automatizada.

## 3. Obstáculos encontrados

### Cobertura das interfaces

A cobertura histórica da interface do Senado vale para a base de pronunciamentos,
e não para as demais. As notas taquigráficas de sessão respondem com erro para o
período, e o resultado de plenário devolve estrutura vazia para o ano 2000. A
consequência analítica é que a deliberação da matéria em Ordem do Dia não está
disponível por interface programática, apenas no Diário do Senado Federal.

Não há rota reversa que permita descobrir o identificador de uma reunião de
comissão a partir da data ou da sigla, o que torna as notas taquigráficas de
comissão inalcançáveis quando o identificador não vem de outra fonte.

Na Câmara, a rota de discursos por deputado existe e cobre o período, mas o campo
de transcrição vem vazio em todos os registros verificados, e o endereço de texto
remete ao visualizador do Diário digitalizado. Não há rota que devolva o conjunto
de oradores de uma data: a consulta de discursos como recurso de topo não é
servida, e só existe a consulta por deputado, um por vez. Qualquer coleta por
essa via é limite inferior do que foi dito na sessão, nunca o conjunto. Daí a
necessidade de segmentar o Diário por orador.

A busca de parlamentar por nome falha para parte dos deputados da 51ª
legislatura. O identificador foi obtido pela rota de autores da proposição
correspondente.

### Recuperação de documentos

Código de resposta bem-sucedido não garante documento: a interface da Câmara
devolve página de erro em HTML com código 200. A coleta verifica os bytes
iniciais do arquivo antes de gravar.

Os endereços de documento do Senado não trazem extensão e seguem mais de um
padrão, o mais comum sendo o do serviço `sdleg-getter`. Esse serviço opera
verificação automatizada de origem. A coleta não tentou contorná-la: os
documentos barrados foram registrados em `corpus_fust/pendentes_manuais.json`
com o motivo, e permanecem como lacuna declarada.

A rota de emendas do processo devolve lista vazia para a matéria, embora as seis
emendas de Plenário existam e estejam descritas no Parecer nº 712, de 2000, às
folhas 251 a 266 do processo. Variações do nome do parâmetro devolvem a tabela
integral de emendas do Senado, sem filtro, e não resolvem o problema.

### Diários

Os Diários da Câmara estão em domínio próprio, distinto do domínio institucional
principal, e o endereço se compõe pelo padrão `DCD{DD}{MES}{AAAA}.pdf`, com o mês
em três letras maiúsculas.

A paginação impressa dos Diários reinicia a cada ano ou sessão legislativa, de
modo que o deslocamento calibrado para uma edição não se transfere a outra. Cada
localização foi calibrada no próprio volume.

O Diário é datado pela sessão e publicado no dia seguinte, e o parâmetro de data
do endereço é o da publicação. Antes de registrar uma data de sessão como lacuna,
é preciso conferir a edição publicada no dia seguinte.

A consulta de discursos do Senado por intervalo mensal trunca o resultado: um
pedido de mês inteiro devolveu menos registros do que pedidos de dias isolados
dentro do mesmo mês. A varredura foi feita data a data.

### Camada de texto e reconhecimento óptico

A camada de texto embutida nos Diários da Câmara intercala as duas colunas da
página, de modo que a linha da coluna esquerda sai unida à da direita. Qualquer
segmentação por orador feita sobre essa camada vem contaminada. O reprocessamento
por reconhecimento óptico resolve, por fazer análise de layout, e por isso foi
condição da segmentação, não refinamento dela.

O problema não se repete no Senado, cujos marcadores de orador saem íntegros. A
decisão de reprocessar foi tomada por arquivo, em três testes sucessivos:

1. Há camada de texto? Amostradas oito páginas e contados os caracteres. Nenhum
   em todas indica digitalização sem texto, e o reprocessamento é obrigatório.
2. Há intercalação de coluna? Extraídos os marcadores de orador, verifica-se se a
   linha invade o assunto da coluna vizinha.
3. Passando os dois testes, a camada nativa foi usada e o reprocessamento
   dispensado, que foi o caso de sete das oito edições do Senado.

O volume do Diário também foi conferido antes de rasterizar. Uma das edições tem
880 KB por página contra 38 a 59 KB nas demais, e nenhuma camada de texto; outra
apresenta número de páginas uma ordem de grandeza acima do conjunto, com
indicação de estrutura danificada na leitura.

### Classificação da modalidade de fala

O campo de tipo de uso da palavra da interface do Senado não é confiável para o
período: todos os registros verificados de duas sessões voltam classificados como
discurso, embora o texto de ao menos um deles se identifique como fala pela
ordem. A taxonomia fina existe, mas seus códigos foram criados depois e não
retroagiram aos registros.

Por isso a modalidade registrada no corpus foi extraída do parêntese do marcador
de orador no próprio texto, no padrão `(PARTIDO - UF. modalidade. revisão)`, e o
valor devolvido pela interface foi guardado em campo paralelo, para comparação,
sem ser usado na análise.

### Triagem das datas

A varredura identificou pronunciamentos com termo de busca em 105 datas. Baixar o
Diário de todas seria desproporcional, e a triagem separou termo específico, como
o nome do fundo, o número do projeto e o nome da agência reguladora, de termo
genérico isolado, que produz ruído. Só as datas com ao menos um termo específico
foram recolhidas.

## 4. O que não foi obtido

Três itens permaneceram sem rota de acesso e estão declarados na seção 3.1 do
trabalho: o Aviso nº 15, de 2000, do Ministério das Comunicações; um parecer
barrado pela verificação automatizada de origem; e as razões do veto parcial,
cuja série no Diário Oficial não segue o padrão de nomes da Câmara e cuja busca
no portal da Imprensa Nacional não retorna resultado para a data.

Permaneceu igualmente em aberto o Diário do Senado Federal da sessão de 27 de
junho de 2000, em que foi lido o Parecer nº 712, de 2000.

As notas taquigráficas da audiência pública de 14 de dezembro de 1999 na Comissão
de Assuntos Econômicos existem às folhas 114 a 145 do processo físico, fora do
acervo digitalizado consultável. A realização do evento está atestada pelo
relatório anual de atividades da comissão, e não presumida.
