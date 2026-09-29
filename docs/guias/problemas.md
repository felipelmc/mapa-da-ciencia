# Solução de problemas

Comece sempre por:

```bash
mapa diagnostico
```

Cada item com ✗ ou ! vem com uma dica. Os casos mais comuns estão abaixo.

## O terminal não encontra o `mapa`

> zsh: command not found: mapa

Acontece logo depois do `uv tool install`, quando a pasta onde o `uv` põe os comandos (`~/.local/bin`) não está no caminho de busca do terminal. Rode `uv tool update-shell`, feche o terminal e abra outro. Quem instalou pelo código usa `uv run mapa` dentro da pasta `mapa-da-ciencia` e não passa por isso.

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

As etapas que carregam modelos conferem a memória antes e param com uma mensagem clara se o modelo não couber.

## Pouco espaço em disco

Os modelos ocupam de 0,6 GB (`qwen3-embedding:0.6b`) a 17 GB (`gemma4:26b`). Liste o que está instalado com `ollama list` e remova o que não usa com `ollama rm <modelo>`. A coleta do piloto (cerca de 5 mil artigos) ocupa uns 200 MB.

## Erro de certificado (`CERTIFICATE_VERIFY_FAILED`)

Algumas redes (universidades, órgãos públicos, empresas) inspecionam o tráfego HTTPS com um certificado próprio. O `mapa` usa os certificados do sistema operacional justamente para funcionar nesses casos. Se o erro persistir, o certificado da instituição não está instalado no sistema. Peça ao suporte de TI para instalá-lo ou tente de outra rede.

## A porta 8765 já está em uso

> Erro: a porta 8765 já está em uso. Use outra, por exemplo --porta 8766.

Provavelmente outro `mapa painel` já está aberto. Encerre-o com ++ctrl+c++ no terminal dele ou use outra porta.

## "A interface ainda não foi compilada"

Acontece quando o `mapa` é instalado a partir do código-fonte. Compile a interface uma vez, como explica o [tutorial](../tutoriais/explorar-exemplo.md#3-abra-o-painel-com-o-exemplo).

## Pastas "dados 2", "dados 3"… e o painel vazio

Acontecia com projetos numa pasta sincronizada, como a Mesa ou os Documentos no iCloud Drive do macOS, feitos com versões antigas do `mapa-da-ciencia` (anteriores à 1.0): a exportação trocava a pasta `saida/dados` inteira, e o serviço de sincronização guardava a nova com outro nome. Hoje a exportação troca só os arquivos, e a pasta continua a mesma. Se o seu projeto tem essas pastas, apague as `saida/dados N` e rode `mapa publicar` ou qualquer etapa (`mapa geografia` é a mais rápida): a exportação refaz `saida/dados`.

## Erro no `mapa.yaml` ou no `codebook.yaml`

As mensagens apontam o campo e o motivo:

```
Erro: codebook.yaml tem 1 problema(s):
  - variaveis.0: a variável `metodo` (categorica) precisa de pelo menos 2 categorias
```

`variaveis.0` é a primeira variável da lista (a contagem começa do zero). Consulte a [referência da configuração](../referencia/configuracao.md) e a [do codebook](../referencia/codebook.md).
