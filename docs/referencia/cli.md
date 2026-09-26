<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->

# Linha de comando

Todos os comandos têm ajuda embutida: `mapa --help` ou `mapa <comando> --help`.

Opção global: `mapa --versao` (`-V`) mostra a versão instalada.

## `mapa novo`

Cria um projeto novo, com mapa.yaml e codebook.yaml prontos para editar.

```
mapa novo [OPÇÕES] pasta
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `pasta` | Pasta onde o projeto será criado. | **obrigatório** |
| `--modelo`, `-m` | Modelo de projeto: ciencia-politica, vazio. | `ciencia-politica` |
| `--perfil`, `-p` | Perfil de modelos locais: leve, padrao, forte. Padrão: sugerido pela memória da máquina. |  |

## `mapa status`

Mostra o recorte do projeto e em que ponto está cada etapa do pipeline.

```
mapa status [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |

## `mapa diagnostico`

Confere memória, disco, o Ollama, os modelos do projeto e a conexão com as fontes.

```
mapa diagnostico [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--sem-rede` | Não testa a conexão com ArticleMeta e OpenAlex. |  |

## `mapa painel`

Abre o painel no navegador: a interface do projeto, servida só nesta máquina.

```
mapa painel [OPÇÕES]
```

| Argumento ou opção | Descrição | Padrão |
|---|---|---|
| `--projeto`, `-P` | Pasta do projeto (padrão: a pasta atual ou uma acima dela). | pasta atual |
| `--exemplo` | Mostra o exemplo sintético, sem precisar de um projeto. |  |
| `--porta` | Porta local do servidor. | `8765` |
| `--abrir`, `--nao-abrir` | Abre o navegador automaticamente. | `True` |
