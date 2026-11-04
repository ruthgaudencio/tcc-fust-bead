# Equidade digital no processo legislativo: FUST e BEAD

Código, instrumento de codificação e dados do trabalho de conclusão de curso
*A institucionalização da equidade digital: uma análise comparada dos processos
legislativos do FUST e do BEAD*, apresentado ao curso de Direito do Insper.

Este repositório é o anexo do trabalho. Reúne o que é preciso para conferir e
repetir a análise.

## O que a pesquisa faz

Compara como a equidade digital foi enunciada no debate legislativo e como foi
incorporada ao texto normativo aprovado, em dois casos: a tramitação do Projeto
de Lei nº 3.808, de 1997, até a Lei nº 9.998, de 2000, que institui o FUST, e a
cadeia de proposições incorporada à *Infrastructure Investment and Jobs Act*,
de 2021, que institui o BEAD.

A comparação percorre dezoito subcategorias de desigualdade e dois eixos: o
discursivo, sobre o que foi dito na tramitação, e o normativo, sobre o que o
texto aprovado vincula.

## Organização

    recorte.py                  delimitação temporal dos dois corpora
    analise_lexical.py          cobertura lexical, frequência e linha do tempo
    analise_validada.py         níveis e densidade por subcategoria
    analise_etapas.py           distribuição por etapa do processo legislativo
    diagramas_processo.py       figuras 1 e 2
    diagrama_metodologia.py     figura 3
    coleta_brasil.py            coleta das fontes brasileiras
    COLETA.md                   rotas de acesso e obstáculos da coleta

    coding/INSTRUMENTO_CODIFICACAO.md   o livro de códigos
    coding/PROMPT_VSCODE_*.md           as instruções dadas ao codificador
    coding/pares_eixo_discursivo.csv    a base codificada do eixo discursivo
    coding/eixo_normativo_*.csv         o eixo normativo, por escopo
    coding/lotes/                       o material exibido ao codificador
    coding/medir_confiabilidade.py      kappa de Cohen
    coding/medir_alfa_krippendorff.py   alfa de Krippendorff
    coding/verificar_trechos.py         auditoria da trilha de evidência

    fust/matriz/                lista de termos de busca, por subcategoria
    corpus_fust/, corpus_bead/  texto extraído das fontes e índices do corpus
    resultados/                 tabelas e figuras do trabalho

## Ordem de execução

Há uma dependência entre dois passos: `analise_validada.py` lê um arquivo que
`analise_lexical.py` produz. A ordem correta é:

    python3 coding/agregar_eixo_discursivo.py --base .
    python3 analise_lexical.py
    python3 analise_validada.py
    python3 analise_etapas.py
    python3 coding/verificar_trechos.py
    python3 coding/medir_confiabilidade.py
    python3 coding/medir_alfa_krippendorff.py

## O recorte

`recorte.py` fixa num lugar só a delimitação dos corpora e é importado por todos
os scripts de análise. A análise de cada caso termina no texto aprovado. No caso
norte-americano isso significa a promulgação da IIJA, em 15 de novembro de 2021.

## O que não está aqui

Os PDF originais do corpus, que somam mais de um gigabyte. São documentos
públicos, obtidos nos repositórios oficiais da Câmara dos Deputados, do Senado
Federal e do congress.gov, e as rotas de acesso estão documentadas no código de
coleta. O texto extraído deles está neste repositório, e é sobre esse texto que
a análise opera.

Também não estão aqui os artigos acadêmicos consultados, por serem de terceiros.

## Termos de uso

Este repositório é publicado como anexo de trabalho de conclusão de curso, para
consulta, conferência e verificação dos resultados apresentados no trabalho.

Todos os direitos sobre o código, a lista de termos, o livro de códigos e as
bases de dados derivadas estão reservados à autora. O uso, a adaptação, a
redistribuição e a incorporação em outro trabalho dependem de autorização
prévia, que pode ser solicitada pelo endereço ruthgs@al.insper.edu.br.

A citação acadêmica do trabalho e deste repositório, com a devida atribuição,
dispensa autorização.

Os documentos legislativos que compõem o corpus são documentos públicos,
produzidos pela Câmara dos Deputados, pelo Senado Federal e pelo Congresso dos
Estados Unidos, e não são abrangidos por esta reserva.
