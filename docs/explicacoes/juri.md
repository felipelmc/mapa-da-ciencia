# Júri de modelos locais e supervisor

Um modelo pequeno, rodando num notebook, classifica bem as variáveis claras do codebook e mal as ambíguas. O júri
põe **vários modelos locais para classificar o mesmo texto e conversar sobre as discordâncias**, e deixa para um
**supervisor**, que pode ser uma pessoa ou um modelo maior, só os casos em que eles não chegam a acordo. A pergunta
que ele responde é metodológica: quanto se ganha juntando modelos abertos, e quanto trabalho sobra para quem
supervisiona?

## O protocolo

**1. Votação.** Cada membro de `juri.membros` classifica os documentos da amostra de validação, pelo mesmo caminho
de `mapa classificar --modelo`: o mesmo prompt, a mesma evidência obrigatória e o mesmo cache. A decisão de cada
variável é a **maioria estrita** dos membros. Uma maioria que não é unânime só vale se ao menos um voto dela trouxer
evidência que esteja no texto (um valor sem trecho que o sustente não desempata nada); a unanimidade decide mesmo
sem evidência, porque não há o que deliberar, e a auditoria pode sorteá-la. Variáveis de múltipla escolha são decididas categoria
a categoria; as de texto livre, pela forma normalizada.

**2. Deliberação.** Nas variáveis sem unanimidade, cada membro recebe, na mesma conversa em que classificou, a
própria resposta e as dos outros, **anônimas** ("Modelo A", "Modelo B", na ordem dos valores, sem dizer quem é quem),
cada uma com a evidência e a marca de quando o trecho não está no texto. A instrução é manter a resposta se o texto a
sustenta e mudar só se a evidência de outro mostrar que a definição de outra categoria se cumpre melhor, nunca só
para concordar. Uma rodada só. A nova resposta só vale com evidência no texto.

**3. Supervisor.** O que continua sem maioria vai para o supervisor, que **escolhe entre os candidatos** (as
respostas distintas dos membros, numeradas, sem os nomes dos modelos), com uma evidência do texto e uma
justificativa. Ele não inventa uma resposta nova: se nenhum candidato serve, escolhe o menos ruim e marca
`nenhum_adequado`.

**4. Auditoria.** Unanimidade não é garantia de acerto: modelos parecidos erram parecido. O supervisor confere uma
amostra sorteada das decisões unânimes (`juri.auditoria`, 40 por padrão), e a taxa de erro sai com o intervalo de
Wilson de 95%.

Cada decisão fica com um **estágio**: `unanime`, `maioria` (sem deliberação), `deliberacao` (a maioria saiu da
conversa; `virou` diz se ela mudou) ou `sem_maioria` (com a escolha do supervisor, se houver).

## Três fontes, e por que o supervisor não entra no número principal

O júri produz três classificações que a validação compara como se fossem modelos:

| Fonte | O que é |
|---|---|
| `juri-r1` | a maioria da votação (sem maioria: o voto do primeiro membro, o "presidente") |
| `juri` | a maioria depois da deliberação (sem maioria: o presidente) |
| `juri-supervisor` | o `juri`, com a escolha do supervisor onde não houve maioria |

No piloto, o **codificador de referência** também é um modelo da família Claude, e o supervisor também. Comparar os
dois mede, em parte, quanto uma instância do Claude concorda com outra: é **circular**. Por isso:

- o **resultado principal** é a referência contra o `juri`, que não passa pelo supervisor, ao lado de cada membro
  sozinho e do teste de McNemar entre o `juri` e o modelo principal;
- a referência contra o `juri-supervisor` aparece como **limite superior**, marcada "circular" no relatório e no
  painel (`validacao.familias` declara a família de cada codificador);
- a escolha restrita aos candidatos **limita** a circularidade (o supervisor não pode dar uma resposta que nenhum
  modelo local deu), mas não a elimina;
- o teste sem circularidade é a codificação por uma pessoa: quando há um codificador humano com pelo menos 50
  documentos, ele passa a ser a referência do relatório.

## Custo e privacidade

A votação custa uma classificação da amostra por membro; a deliberação, uma chamada por membro e documento em
disputa. Tudo local. O supervisor, por padrão, trabalha **por arquivos**: o `mapa juri exportar-pedidos` grava os
pedidos em JSONL, e quem supervisiona devolve as respostas no mesmo formato. Com `juri.supervisor.modo: api`, o
supervisor é um modelo da Anthropic chamado pela API: aí os títulos e resumos saem da máquina, o que exige
`enviar_textos: true`, uma confirmação a cada execução e um limite de gasto (ver [Usar o júri](../guias/juri.md)).

## Limitações

- Três modelos locais de famílias diferentes discordam menos do que se esperaria de três pessoas: **concordar não é
  acertar**. A auditoria estima o erro entre os unânimes.
- A deliberação pode levar à conformidade (um modelo muda só porque os outros dois concordam). O relatório conta as
  mudanças na direção da referência e contra ela.
- O júri roda na amostra de validação (200 documentos, no piloto), que é onde há referência para medir o ganho.
  Levá-lo ao corpus inteiro (uma classificação completa por membro, a deliberação e o supervisor em milhares de
  documentos) fica para uma versão futura.
- Os números do piloto e a comparação entre os membros estão no [ADR 0015](../decisoes/0015-juri-de-modelos-e-supervisor.md).
