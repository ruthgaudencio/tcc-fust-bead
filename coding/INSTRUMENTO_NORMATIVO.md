# Instrumento de codificação do eixo normativo

Instrução de codificação do eixo normativo, reproduzida como apêndice. É a única
fonte do critério.

## 1. O que é codificado

A unidade é o **dispositivo**: o trecho do texto aprovado em que uma
subcategoria de desigualdade é nomeada. São 161 dispositivos, 14 do caso
brasileiro e 147 do norte-americano, cada um com o diploma de origem registrado.

O nível de cada subcategoria por caso é agregado depois, pela regra do item 4.

## 2. As decisões, nesta ordem

### 2.1 Pertinência

O termo encontrado nomeia, naquele dispositivo, a subcategoria a que foi
atribuído? `sim`, `nao` ou `indeterminado`. Pertinência `nao` encerra o
dispositivo.

### 2.2 Mecanismo

Que mecanismo o dispositivo institui, entre estes quatro, ou nenhum?

- `percentual destinado` — fixa parcela dos recursos para o grupo ou lugar.
- `critério de elegibilidade` — condiciona acesso ao recurso à pertença ao grupo
  ou à situação descrita.
- `meta diferenciada` — fixa para o grupo alvo, prazo ou padrão distinto do
  geral.
- `obrigação de monitoramento` — impõe medir, informar ou prestar contas sobre o
  grupo.
- `nenhum` — o dispositivo nomeia sem instituir nenhum dos quatro.

### 2.3 Vinculação

**A regra decisiva, e a principal fonte de erro.** O mecanismo precisa recair
sobre a subcategoria codificada, e não apenas comparecer no mesmo dispositivo.

Um percentual destinado a área rural é mecanismo vinculante para urbano e rural.
O mesmo percentual, num dispositivo que menciona escolas de passagem ao definir
o beneficiário, não é mecanismo vinculante para educação. A pergunta é: se esta
subcategoria fosse suprimida do dispositivo, o mecanismo deixaria de operar? Se
sim, ele é vinculante para ela; se o mecanismo seguiria operando igual, não é.

Responder `sim`, `nao` ou `indeterminado`.

Dispositivo que figura em princípio, objetivo, finalidade, definição ou
exposição de motivos, sem consequência para a aplicação de recursos, recebe
`nao`, mesmo quando contém vocabulário de mecanismo.

### 2.4 Nível do dispositivo

| pertinência | mecanismo | vinculante | nível |
|---|---|---|---|
| nao | — | — | `falso_positivo` |
| sim | um dos quatro | sim | `estrutural` |
| sim | qualquer | nao | `superficial` |
| sim | nenhum | — | `superficial` |
| indeterminado | — | — | `indeterminado` |

## 3. Regras de conduta

Citar sempre: todo dispositivo pertinente recebe trecho literal de até 300
caracteres, copiado do campo `trecho`, que sustenta a decisão. Trecho
parafraseado invalida o registro.

`indeterminado` existe para ser usado. Não escolher entre `sim` e `nao` por
verossimilhança.

Codificar os dois casos com a mesma régua. A língua e a técnica legislativa
mudam, o critério não.

Não receber nem procurar expectativa sobre o resultado de uma subcategoria ou de
um caso.

## 4. Agregação

Pela regra do **nível mais alto alcançado**, a mesma do eixo discursivo:

- `estrutural` — algum dispositivo da célula é estrutural;
- `superficial` — nenhum é estrutural e algum é superficial;
- `ausente` — a subcategoria não é nomeada em nenhum dispositivo do escopo.

**O escopo é parâmetro, não constante.** A agregação recebe a lista de diplomas
que contam como texto aprovado e ignora os dispositivos de fora. A codificação
vale para qualquer escopo; só o resultado agregado muda. A escolha do escopo é
da pesquisadora e está registrada em `coding/ESCOPO_TEXTO_APROVADO.md`.

## 5. Formato de saída

Um registro por dispositivo, em `coding/dispositivos_eixo_normativo.csv`:

```
disp_id, caso, diploma, codigo, subcategoria, pertinencia, mecanismo_tipo,
vinculante, nivel_do_dispositivo, trecho_evidencia, justificativa, notas
```
