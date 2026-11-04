# Decisão em aberto: o que conta como "texto aprovado"

O eixo normativo lê o texto aprovado de cada caso. O que entra nesse texto é
escolha da pesquisadora, e ela muda o resultado principal do trabalho. Este
documento registra a decisão e a sua consequência medida.

## A medida

Varredura da lista de termos sobre os textos disponíveis, pelo mesmo módulo de
casamento da passada principal. Subcategorias nomeadas, de 18:

| escopo | FUST | BEAD |
|---|---|---|
| estreito: Lei 9.998/2000 e IIJA SEC. 60102 | 9 | 8 |
| adotado: acrescenta o Digital Equity Act, seções 60301 a 60307 | 9 | 16 |
| amplo: acrescenta Lei 9.472/1997 e Division F inteira | 9 | 17 |

Medida refeita em 31 de outubro de 2026, depois da substituição do glossário do
Título 47 pelas seções operativas do Digital Equity Act e da correção do texto
da Lei nº 9.998/2000 para a publicação original.

O lado brasileiro não se move: a Lei Geral de Telecomunicações não nomeia
nenhuma subcategoria que a Lei do Fust já não nomeie.

O lado norte-americano dobra. As nove subcategorias que entram apenas pelo
escopo ampliado são idade, gênero, raça e etnia, saúde e deficiência,
escolaridade e letramento, vínculo institucional, macrorregião, territórios de
povos e comunidades tradicionais e educação, e elas entram porque é no Digital
Equity Act que as "covered populations" são definidas.

## Por que a escolha decide o achado

No escopo estreito, os dois sistemas nomeiam cerca de metade das subcategorias,
9 contra 8, e a comparação é de simetria. No escopo com Digital Equity Act, são
9 contra 16, e a comparação passa a ser de assimetria acentuada. A mesma
codificação sustenta as duas leituras: o que muda é o recorte.

## Os argumentos

**A favor do escopo estreito.** O trabalho compara a passagem de uma lei
brasileira com o programa norte-americano que lhe é análogo. A SEC. 60102 cria o
BEAD, e é ela que corresponde funcionalmente à Lei do Fust. O Digital Equity Act
é programa vizinho, com dotação e governança próprias, e incorporá-lo compara a
Lei do Fust com um conjunto de programas, não com um.

**A favor de incluir o Digital Equity Act.** Os dois programas foram criados
pela mesma lei, a IIJA, na mesma divisão, e o corpus de audiências já inclui as
dedicadas ao Digital Equity Act, conforme declarado em 3.1. Excluir da leitura
normativa o diploma cujas audiências entraram no corpus discursivo cria
assimetria entre os dois eixos do mesmo caso.

**Contra o escopo amplo.** A Division F inteira acrescenta uma subcategoria
sobre o escopo com Digital Equity Act e traz matéria sem relação com o programa,
ao custo de tornar o recorte difícil de justificar.

## A decisão, tomada em 31 de outubro de 2026

**Escopo adotado:** a Lei nº 9.998, de 2000, em sua publicação original, do lado
brasileiro; a SEC. 60102 e o Título III da Division F, o Digital Equity Act of
2021, seções 60301 a 60307, do lado norte-americano.

**Razão declarada.** O corpus discursivo deste trabalho acompanha a cadeia de
proposições que antecede o BEAD, e o Digital Equity Act integra essa cadeia
desde 2019, quando foi apresentado como S. 1167 e H.R. 4486 e não avançou de
modo autônomo. As audiências a ele dedicadas estão no corpus, conforme declarado
na seção 3.1. Incorporado à Infrastructure Investment and Jobs Act e aprovado com
ela, o seu destino normativo pertence ao mesmo processo legislativo que o corpus
documenta. Excluí-lo do eixo normativo trataria o mesmo diploma de dois modos:
presente quando se mede o que foi dito, ausente quando se mede o que foi
aprovado.

Registre-se que a inclusão não supre ausência do lado da seção que institui o
BEAD. A SEC. 60102 nomeia por conta própria oito subcategorias em vinte e oito
dispositivos pertinentes, com mecanismos vinculantes, entre os quais a
prioridade a áreas rurais, a prioridade a edifícios residenciais com proporção
elevada de domicílios de baixa renda e a obrigação de informar sobre planos
destinados a domicílios de baixa renda. A inclusão do Digital Equity Act
acrescenta o programa vizinho, e não um conteúdo que faltasse ao principal.

**O que ficou de fora e por quê.** O restante da Division F, que trata de middle
mile, de acessibilidade tarifária e de discriminação digital, não integra o
escopo: são matérias distintas do programa analisado. Também ficou de fora a
seção de definições codificada no Título 47 do United States Code, porque o seu
conteúdo já consta da SEC. 60302, dentro do Título III, e contá-la em separado
duplicaria o mesmo texto.

## Como aplicar

A codificação dos 194 dispositivos é feita uma vez e vale para qualquer escopo,
porque cada dispositivo carrega o diploma de origem. O escopo é aplicado na
agregação:

```
python3 coding/agregar_eixo_normativo.py --comparar          # os três lado a lado
python3 coding/agregar_eixo_normativo.py --escopo com-dea    # grava o escolhido
```

Rodar `--comparar` depois da codificação mostra, célula a célula, o que cada
escopo produz. A decisão pode, portanto, ser tomada com o resultado à vista, e
precisa ser declarada na seção 3.3 com o argumento que a sustenta.

