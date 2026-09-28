# Instalar e escolher os modelos

O `mapa-da-ciencia` tem duas partes: o pacote Python (a linha de comando `mapa` e o painel) e o **Ollama**, o programa que roda os modelos de linguagem na sua máquina.

## 1. Pacote Python

Com o [uv](https://docs.astral.sh/uv/) instalado (veja o [tutorial](../tutoriais/explorar-exemplo.md#1-instale-o-uv)):

```bash
git clone https://github.com/felipelmc/mapa-da-ciencia.git
cd mapa-da-ciencia
uv sync
uv run mapa --versao
```

É necessário o Python 3.11, 3.12, 3.13 ou 3.14; o `uv` baixa um sozinho, se preciso. O pacote e suas dependências ocupam cerca de 400 MB, a maior parte das bibliotecas numéricas usadas nos tópicos (UMAP, HDBSCAN). Nos exemplos a seguir, `mapa` significa `uv run mapa` quando você estiver dentro da pasta do código.

### Sem compilar a interface: o *wheel* da *release*

O código do repositório não traz a interface do painel compilada (ela precisa do Node.js). Cada [*release*](https://github.com/felipelmc/mapa-da-ciencia/releases) tem um *wheel* com ela pronta, que instala sem clonar nada. Por exemplo, com o `uv`:

```bash
uv tool install "https://github.com/felipelmc/mapa-da-ciencia/releases/download/v1.0.1/mapa_da_ciencia-1.0.1-py3-none-any.whl"
mapa --versao
```

Troque `1.0.1` (nos dois lugares do endereço) pela versão da *release* mais recente. Com o `pip`, num ambiente virtual, é o mesmo endereço em `pip install`. Se o terminal responder `command not found: mapa`, o `uv` pôs o comando numa pasta que o terminal ainda não procura (ele avisa isso no fim da instalação). Rode `uv tool update-shell`, feche o terminal e abra outro.

## 2. Ollama

Baixe e instale o Ollama em [ollama.com/download](https://ollama.com/download) (macOS, Windows e Linux). No macOS e no Windows ele fica rodando como aplicativo. No Linux, o servidor sobe com `ollama serve`.

## 3. Escolha um perfil de modelos

Os modelos precisam caber na memória. O `mapa` sugere um perfil a partir da memória total da máquina:

| Perfil | Memória | Embeddings | Classificação | Rótulos dos tópicos | Download |
|---|---|---|---|---|---|
| `leve` | 8 a 16 GB | `qwen3-embedding:0.6b` | `qwen3.5:4b` | `qwen3.5:4b` | ~4 GB |
| `padrao` | 16 a 32 GB (e a T4 do Colab) | `qwen3-embedding:0.6b` | `qwen3.5:9b` | `qwen3.5:9b` | ~7 GB |
| `forte` | 32 GB ou mais | `qwen3-embedding:0.6b` | `qwen3.5:9b` | `gemma4:26b` | ~24 GB |

As métricas publicadas do piloto são do `qwen3.5:9b`. O `qwen3.5:4b` do perfil `leve` ainda não passou pela validação ([adendo ao ADR 0005](../decisoes/0005-modelo-de-classificacao.md#adendo-2026-09-28-versao-101-o-perfil-leve)): a validação do seu projeto mede a concordância do modelo que você usar.

Baixe os modelos do seu perfil. No perfil `padrao`:

```bash
ollama pull qwen3-embedding:0.6b
ollama pull qwen3.5:9b
```

!!! warning "Memória total não é memória livre"
    Um modelo de 6,6 GB precisa de uns 8 GB **livres** na hora de rodar, contando o contexto. Com outros programas pesados abertos (outros modelos, jobs de R ou Python, dezenas de abas), o computador pode começar a usar o disco como memória e ficar muito lento. O `mapa diagnostico` mostra se cada modelo cabe na memória livre agora, e as etapas que carregam modelos fazem essa conferência antes de começar.

Por que esses modelos, e não outros? Veja [Modelos locais](../explicacoes/modelos-locais.md) e os registros de decisão [0004](../decisoes/0004-embeddings-e-idioma-de-analise.md) (embeddings) e [0005](../decisoes/0005-modelo-de-classificacao.md) (classificação).

## 4. Confira tudo com `mapa diagnostico`

```bash
mapa diagnostico
```

O comando confere:

- a memória total, a memória livre agora, o swap e o disco livre;
- se o Ollama está respondendo, e quais modelos estão instalados e carregados;
- se os modelos do perfil (ou do projeto, se você estiver na pasta de um) estão instalados e cabem na memória. Quando um falta, ele mostra o `ollama pull` e o tamanho do download;
- a conexão HTTPS com a ArticleMeta (SciELO) e com o OpenAlex.

A saída termina com "Tudo pronto." ou com a lista do que impede rodar o pipeline. Se algo der errado, veja [Solução de problemas](problemas.md).
