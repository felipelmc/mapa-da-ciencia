# Usar o painel

O painel é a interface do `mapa-da-ciencia`: um site que roda **só na sua máquina**, servido pelo próprio comando `mapa`, sem nada publicado na internet.

## Abrir

Dentro da pasta de um projeto:

```bash
mapa painel
```

Sem projeto, com os dados de exemplo:

```bash
mapa painel --exemplo
```

O navegador abre em `http://127.0.0.1:8765/`. Para encerrar, aperte ++ctrl+c++ no terminal.

| Opção | Para quê |
|---|---|
| `--exemplo` | Mostra o exemplo sintético, sem precisar de projeto |
| `--porta 8800` | Usa outra porta (a padrão, 8765, pode estar ocupada) |
| `--nao-abrir` | Não abre o navegador (útil em servidores e no Colab) |
| `--projeto`, `-P` | Indica a pasta do projeto quando você está fora dela |

Cada projeto abre num painel só. Com um painel já aberto no projeto (numa aba esquecida, ou pelo notebook), um segundo `mapa painel` (ou `mapa.painel()`) não abre e diz o endereço do primeiro: dois painéis no mesmo projeto atrapalhariam as etapas um do outro. A trava fica no arquivo `.painel.lock` da pasta do projeto e some quando o painel fecha.

Num notebook (Jupyter ou Colab), `mapa painel` prenderia a célula. Use a API Python, que deixa o servidor rodando numa *thread*:

```python
import mapa_da_ciencia.api as mapa

painel = mapa.painel("op")  # mostra o link; painel.parar() encerra
```

No Colab, o painel abre numa janela nova, pelo *proxy* do Google, e só nesse modo a API aceita pedidos que não vêm de `127.0.0.1`: a máquina do Colab é só de quem a abriu, e o *proxy* exige o login dessa pessoa. O caderno da oficina faz isso no fim (veja [Oficina no Colab](../tutoriais/oficina-colab.md)).

## O que aparece

| Vista | Mostra |
|---|---|
| Início | Números do corpus e macrotemas, com a participação de cada um por ano |
| Mapa | Cada artigo como um ponto; artigos próximos tratam de assuntos próximos. Contornos e rótulos dos tópicos (dos macrotemas, de longe), colorir por tópico, macrotema, revista ou ano, e filtrar pela legenda ou pelos rótulos; busca, laço e linha do tempo com play. Clicar num ponto abre o cartão do documento, com o resumo e os 5 mais parecidos ([Ler o mapa](ler-o-mapa.md)) |
| Tópicos | O fluxo dos macrotemas e dos tópicos no tempo, em três modos; os tópicos em alta e em queda; a gaveta de cada tópico; o perfil de cada revista ([Ler os tópicos no tempo](ler-os-topicos.md)) |
| Classificação | Uma variável do codebook por vez: a distribuição por ano, o cruzamento com macrotemas, tópicos ou revistas, os selos de concordância e os documentos de cada célula com a evidência marcada no resumo ([Ler a classificação](ler-a-classificacao.md)) |
| Geografia | Produção por UF, país e instituição, com contagem fracionária, e a cobertura das afiliações por ano ([Ler a geografia](ler-a-geografia.md)) |
| Validação | A concordância do modelo com quem codificou a amostra, a matriz de confusão e as divergências; no painel local, a codificação da amostra pelo teclado ([Codificar a amostra](codificar-a-amostra.md), [Ler kappa e PABAK](ler-kappa-e-pabak.md)) |
| Projeto | As etapas do pipeline numa linha de metrô (em dia, desatualizadas ou pendentes), rodar e cancelar cada uma com o progresso ao vivo, a estimativa da classificação e os modelos do Ollama (só no painel local) |
| Redes | Coautoria entre pessoas e entre instituições, colaboração entre estados e citações (o cânone e o fluxo entre macrotemas), com o mesmo recorte das outras vistas ([Ler as redes](ler-as-redes.md)) |

Para projetar numa aula ou numa apresentação, aperte ++p++: o **modo apresentação** esconde o trilho e as barras e aumenta a letra; ++esc++ (ou ++p++ de novo) volta.

A interface tem dois temas: **Observatório** (escuro, bom para projetar) e **Prancha** (claro, bom para figuras de artigo). Ela segue o tema do sistema, e o botão na barra superior alterna entre os dois.

## Projeto novo, painel vazio

Logo depois do `mapa novo`, o painel abre, mas sem dados: a página inicial explica quais etapas rodar primeiro. Os números e as vistas aparecem conforme as etapas vão sendo concluídas:

- depois do `mapa coletar`, a página inicial mostra quantos documentos e revistas há e o período coberto;
- depois do `mapa topicos`, a página inicial mostra os tópicos e os macrotemas, a vista Mapa mostra cada documento como um ponto, e a vista Tópicos mostra os temas no tempo;
- depois do `mapa geografia`, a vista Geografia mostra de onde vêm os autores;
- depois do `mapa redes`, a vista Redes mostra quem escreve com quem e o que o corpus cita;
- depois do `mapa classificar`, a vista Classificação mostra as respostas do modelo, e o cartão do Mapa marca as evidências no resumo;
- depois do `mapa validar amostra` e da codificação, a vista Validação mostra a concordância.

Mapa, Tópicos, Classificação, Geografia e Redes dividem o **recorte**, a barra abaixo do título: período, revistas, tópicos, busca, laço, UFs, países e instituições. Ele vai junto quando você troca de vista pelo trilho, e fica no endereço da página, como tudo o que está na tela.

Cada etapa grava seus arquivos em `saida/dados/`. Basta recarregar a página, sem reiniciar o `mapa painel`.

## Rodar as etapas pelo painel

No painel local, a vista **Projeto** mostra as etapas numa linha, na ordem em que rodam: coleta, tópicos, geografia, redes, classificação e validação. Cada estação diz se a etapa nunca rodou, se está em dia ou se ficou para trás (tracejada: o corpus, o codebook ou as correções mudaram depois da última execução; nas redes, a estação diz o que mudou), com a data, a duração e o que ela produziu.

- **Rodar** começa a etapa em segundo plano. O progresso aparece ao vivo, com as mensagens da etapa; você pode trocar de vista, fechar a aba ou recarregar a página, e ao voltar o acompanhamento continua de onde estava. Só uma etapa roda por vez.
- **Cancelar** para a etapa na próxima atualização de progresso. Como as etapas guardam o que já fizeram, rodar de novo continua de onde parou.
- Algumas etapas têm variações: a coleta e a classificação podem rodar como um **piloto com 20 documentos**, e a classificação pode **estimar o tempo** ou classificar **só a amostra** de validação.
- Quando a etapa termina, **Ver os dados novos** recarrega o painel com os arquivos que ela gerou.
- O bloco **Modelos** mostra se o Ollama está no ar e se os modelos do projeto estão instalados; o que faltar pode ser baixado dali, com o tamanho do download antes.

### Configurar o projeto

O botão **Configurar o projeto** abre um assistente em cinco passos, sobre o projeto aberto:

1. **Fontes:** as revistas do SciELO Brasil (procure por nome, sigla, ISSN ou área) e se a coleta completa os registros com o OpenAlex.
2. **Recorte:** o período, os tipos de documento e os idiomas de análise (dos tópicos) e de exibição (do painel e da classificação).
3. **Modelo:** os perfis de modelos, com o sugerido para a memória desta máquina, o que cada um baixa e o que já está instalado.
4. **Codebook:** as variáveis, com a pergunta e as categorias (veja [Escrever um codebook](codebook.md)).
5. **Revisão:** o que muda e o que isso refaz (uma revista nova refaz a coleta e as etapas seguintes; uma definição nova do codebook refaz a classificação).

Nada é gravado antes da revisão. Ao salvar, o `mapa.yaml` e o `codebook.yaml` mudam só no que mudou, e os comentários dos arquivos ficam. **Salvar e rodar um piloto** coleta só 20 documentos, para conferir o recorte antes da coleta inteira. Enquanto uma etapa roda, o projeto não pode ser mudado.

Na CLI, as mesmas etapas são `mapa coletar`, `mapa topicos`, `mapa geografia`, `mapa redes` e `mapa classificar`, e o que uma faz a outra enxerga: uma etapa rodada no terminal aparece em dia no painel.

## Como funciona

O `mapa painel` sobe um servidor local ([FastAPI](https://fastapi.tiangolo.com)) que entrega a interface compilada, os arquivos do [contrato de dados](../referencia/contrato.md) do projeto e uma API para o que só faz sentido localmente: rodar as etapas, editar o projeto e codificar a amostra de validação. As etapas rodam uma de cada vez numa fila do servidor, e o progresso chega ao navegador por *Server-Sent Events*, que se reconectam sozinhos se a conexão cair. O site publicado com [`mapa publicar`](publicar.md) é a mesma interface lendo os mesmos arquivos, só que sem a API: por isso ele é somente leitura.
