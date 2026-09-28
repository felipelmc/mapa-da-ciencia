# Explorar o exemplo em 5 minutos

Neste tutorial você instala o `mapa-da-ciencia` e abre o painel com um **exemplo sintético**: 1.500 artigos fictícios de ciência política, em 28 tópicos, publicados entre 2010 e 2025. Não é preciso Ollama, modelos nem internet (além da instalação).

!!! note "Dados fictícios"
    Títulos, autores, resumos e afiliações do exemplo são **inventados**. Só os nomes das revistas e das instituições são reais, para o exemplo parecer familiar. Não use esses dados em análises.

## 1. Instale o `uv`

O [uv](https://docs.astral.sh/uv/) gerencia o Python e as dependências do projeto.

=== "macOS"

    ```bash
    brew install uv
    ```

=== "Linux e macOS sem Homebrew"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

## 2. Instale o `mapa-da-ciencia`

Há dois caminhos. Para usar, o primeiro basta; o segundo é para quem vai mexer no código.

=== "Pelo *wheel* (mais simples)"

    Cada [*release*](https://github.com/felipelmc/mapa-da-ciencia/releases) tem um arquivo `.whl` com tudo pronto, inclusive a interface do painel. Instale o da mais recente (troque a versão, se houver uma mais nova):

    ```bash
    uv tool install "https://github.com/felipelmc/mapa-da-ciencia/releases/download/v2.0.0/mapa_da_ciencia-2.0.0-py3-none-any.whl"
    mapa --versao
    ```

    A última linha mostra a versão instalada, por exemplo `mapa-da-ciencia 2.0.0`. Se o terminal responder `command not found: mapa`, o `uv` pôs o comando numa pasta que o terminal ainda não procura (ele avisa isso no fim da instalação). Rode `uv tool update-shell`, feche o terminal e abra outro.

=== "Pelo código"

    Além do `uv`, é preciso o [Node.js](https://nodejs.org) 22.18 ou mais recente, para compilar a interface do painel uma vez:

    ```bash
    git clone https://github.com/felipelmc/mapa-da-ciencia.git
    cd mapa-da-ciencia
    uv sync
    cd frontend
    npm ci
    npm run empacotar
    cd ..
    uv run mapa --versao
    ```

    O `npm` pode sugerir `npm audit fix --force` ou `npm run preview` no fim: não é preciso, pode ignorar. Neste caminho, os comandos do `mapa` começam com `uv run` (`uv run mapa painel`), e as dicas que o próprio `mapa` imprime (`mapa status`) também.

## 3. Abra o painel com o exemplo

```bash
mapa painel --exemplo
```

(Pelo código: `uv run mapa painel --exemplo`.) O navegador abre em `http://127.0.0.1:8765/`. A página inicial mostra os números do corpus e os sete macrotemas, cada um com sua cor. Use o trilho à esquerda para passear pelas vistas. O **Mapa** mostra os 1.500 documentos fictícios como pontos: arraste para mover, use a roda do mouse para aproximar, clique num ponto para ver o documento, e experimente a busca (<kbd>/</kbd>), o laço (<kbd>L</kbd>) e o botão Tocar da linha do tempo ([Ler o mapa](../guias/ler-o-mapa.md)). **Tópicos** mostra os assuntos no tempo, **Geografia** as UFs, os países e as instituições dos autores, e **Classificação** e **Validação**, a leitura dos resumos por um codebook e a concordância numa amostra.

Para encerrar, volte ao terminal e aperte ++ctrl+c++.

!!! tip "A página diz que a interface não foi compilada?"
    Você instalou pelo código e a interface ainda não foi compilada. Encerre o painel (++ctrl+c++), rode os comandos do `npm` do passo 2 e abra o painel de novo: o painel só enxerga a interface nova quando é aberto de novo.

## O que aconteceu

`mapa painel --exemplo` gerou os dados de exemplo numa pasta temporária, subiu um servidor local só na sua máquina e abriu o navegador. Os dados seguem o mesmo [contrato](../referencia/contrato.md) que o pipeline produz para um projeto real. Por isso o exemplo é uma prévia fiel do que você vai ver com os seus próprios dados.

## Próximos passos

- [Seu primeiro mapa, parte 1](primeiro-mapa.md), para coletar artigos de verdade, e a [parte 2](primeiro-mapa-topicos.md), para descobrir os tópicos deles.
- [Instalar e escolher os modelos](../guias/instalacao.md), para preparar o Ollama.
- [Criar um projeto](../guias/criar-projeto.md), para definir o seu recorte.
