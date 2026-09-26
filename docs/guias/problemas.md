# Solução de problemas

Comece sempre por:

```bash
mapa diagnostico
```

Cada item com ✗ ou ! vem com uma dica. Os casos mais comuns estão abaixo.

## O Ollama não está respondendo

> O Ollama não está respondendo em http://localhost:11434.

- No macOS e no Windows, abra o aplicativo Ollama (o ícone aparece na barra de menus).
- No Linux, rode `ollama serve` num terminal separado.
- Se o Ollama roda em outra máquina ou porta, defina `OLLAMA_HOST`, por exemplo `export OLLAMA_HOST=http://192.168.0.10:11434`.

## Modelo não instalado

> ✗ qwen3.5:9b (classificação, rótulos): não instalado. Rode: ollama pull qwen3.5:9b (download de ~6,6 GB)

Rode o comando sugerido. Antes, confira o espaço em disco (a linha "Disco livre" do diagnóstico).

## O computador fica lento ao rodar um modelo

O modelo não cabe na memória livre, e o sistema passou a usar o disco como memória (*swap*). O que fazer:

1. Veja "Memória disponível agora" e "Swap" no `mapa diagnostico`.
2. Feche programas pesados: outros modelos, jobs de R ou Python, máquinas virtuais.
3. Descarregue modelos esquecidos na memória: `ollama ps` lista os carregados, e `ollama stop <modelo>` descarrega um deles.
4. Se não bastar, troque para um modelo menor no `mapa.yaml` (veja os [perfis](instalacao.md#3-escolha-um-perfil-de-modelos)).

A partir do marco M3, as etapas que carregam modelos conferem a memória antes e param com uma mensagem clara se o modelo não couber.

## Pouco espaço em disco

Os modelos ocupam de 0,6 GB (`qwen3-embedding:0.6b`) a 17 GB (`gemma4:26b`). Liste o que está instalado com `ollama list` e remova o que não usa com `ollama rm <modelo>`. A coleta do piloto (cerca de 5 mil artigos) ocupa uns 200 MB.

## Erro de certificado (`CERTIFICATE_VERIFY_FAILED`)

Algumas redes (universidades, órgãos públicos, empresas) inspecionam o tráfego HTTPS com um certificado próprio. O `mapa` usa os certificados do sistema operacional justamente para funcionar nesses casos (veja o registro de decisão [0001](../decisoes/0001-certificados-do-sistema-com-truststore.md)). Se o erro persistir, o certificado da instituição não está instalado no sistema. Peça ao suporte de TI para instalá-lo ou tente de outra rede.

## A porta 8765 já está em uso

> Erro: a porta 8765 já está em uso. Use outra, por exemplo --porta 8766.

Provavelmente outro `mapa painel` já está aberto. Encerre-o com ++ctrl+c++ no terminal dele ou use outra porta.

## "A interface ainda não foi compilada"

Acontece quando o `mapa` é instalado a partir do código-fonte. Compile a interface uma vez, como explica o [tutorial](../tutoriais/explorar-exemplo.md#3-abra-o-painel-com-o-exemplo).

## Erro no `mapa.yaml` ou no `codebook.yaml`

As mensagens apontam o campo e o motivo:

```
Erro: codebook.yaml tem 1 problema(s):
  - variaveis.0: a variável `metodo` (categorica) precisa de pelo menos 2 categorias
```

`variaveis.0` é a primeira variável da lista (a contagem começa do zero). Consulte a [referência da configuração](../referencia/configuracao.md) e a [do codebook](../referencia/codebook.md).
