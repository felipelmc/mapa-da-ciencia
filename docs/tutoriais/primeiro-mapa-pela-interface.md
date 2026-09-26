# Seu primeiro mapa pela interface

Este tutorial faz o percurso das partes 1 a 4 de "Seu primeiro mapa" quase todo pelo painel, sem digitar os comandos de cada etapa: você cria um projeto, abre o painel, confere a configuração no assistente e roda a coleta, os tópicos, a geografia e a classificação pela vista **Projeto**, acompanhando cada etapa ao vivo. No fim, codifica uma parte da amostra de validação e vê a concordância. Leva uns 30 minutos, a maior parte esperando os modelos.

!!! info "Antes de começar"
    - Instale o `mapa-da-ciencia` e o Ollama (veja [Instalar e escolher os modelos](../guias/instalacao.md)). O terminal só é usado para criar o projeto e abrir o painel.
    - A classificação usa o modelo do perfil sugerido para a sua máquina (`qwen3.5:9b` com 16 GB de memória ou mais). Se ele ainda não estiver instalado, o painel oferece o download, com o tamanho antes.

## 1. Crie o projeto e abra o painel

```bash
uv run mapa novo projetos/pela-interface --revista op --anos 2010-2025
uv run mapa painel -P projetos/pela-interface  # fora do CI
```

O primeiro comando cria a pasta do projeto com a *Opinião Pública* de 2010 a 2025, o recorte das partes 2 a 4. O segundo abre o painel no navegador, em `http://127.0.0.1:8765/`. Deixe o terminal aberto: o painel roda enquanto ele estiver ali.

## 2. Confira o projeto no assistente

Vá à vista **Projeto**, no trilho da esquerda, e clique em **Configurar o projeto**. O assistente tem cinco passos:

1. **Fontes:** a *Opinião Pública* já está lá. Para incluir outra revista, procure pelo nome, pela sigla ou pelo ISSN.
2. **Recorte:** de 2010 a 2025, artigos e artigos de revisão, tópicos a partir do inglês e o painel em português.
3. **Modelo:** o perfil sugerido para a memória da sua máquina aparece marcado, com o que cada modelo baixa e o que já está instalado.
4. **Codebook:** as seis variáveis do codebook de exemplo (abordagem, técnica, recorte geográfico, Brasil como caso, subárea e período). Abra uma para ver a pergunta e as categorias.
5. **Revisão:** o que mudou e o que isso refaz.

Se não mudou nada, clique em **Cancelar**. (Com alguma mudança, **Salvar** grava o `mapa.yaml` e o `codebook.yaml` sem perder os comentários.)

## 3. Rode as etapas pela linha de metrô

A linha mostra as etapas na ordem: coleta, tópicos, geografia, classificação e validação. Cada estação diz se a etapa nunca rodou, se está em dia ou se ficou desatualizada.

1. Na estação **Coleta**, clique em **Rodar**. O quadro da etapa mostra o progresso ao vivo e, no fim, o resumo: cerca de 400 documentos. Leva menos de um minuto.
2. Na estação **Tópicos**, clique em **Rodar**. O quadro mostra os embeddings, o agrupamento e os rótulos, um por um. Leva alguns minutos.
3. Na estação **Geografia**, clique em **Rodar**. Leva segundos.

Enquanto uma etapa roda, as outras esperam, e você pode trocar de vista ou fechar a aba: ao voltar à vista Projeto, o acompanhamento continua. Para parar uma etapa, **Cancelar**; rodar de novo continua de onde parou.

Quando uma etapa termina, **Ver os dados novos** recarrega o painel: o Mapa, os Tópicos e a Geografia passam a mostrar o corpus (veja [Ler o mapa](../guias/ler-o-mapa.md)).

## 4. Classifique a amostra

A classificação de todo o corpus leva cerca de uma hora e meia neste recorte. Para começar, classifique só a amostra de validação:

1. Na estação **Validação**, escolha **40** documentos e clique em **Sortear a amostra**. A amostra é sorteada entre os documentos com resumo, espalhada pelos tópicos.
2. Na estação **Classificação**, clique em **Estimar o tempo**: o modelo classifica 5 documentos e o painel mostra quanto falta, neste computador.
3. Clique em **Só a amostra**. São uns 10 minutos.

A vista **Classificação** mostra o resultado: a distribuição de cada variável por ano e por macrotema e, numa célula, os documentos com o trecho do resumo que justifica cada resposta (veja [Ler a classificação](../guias/ler-a-classificacao.md)).

## 5. Codifique e veja a concordância

Na estação **Validação**, clique em **Codificar a amostra**, escreva o seu nome (sem acentos nem espaços) e comece. A ficha mostra o título e o resumo, e as variáveis uma de cada vez. Use o teclado: ++1++ a ++9++ escolhem a opção e passam para a próxima variável, a variável de texto é digitada, e ++enter++ confirma a ficha. A ficha nunca mostra o que o modelo respondeu. Codifique pelo menos 20 fichas; tudo é gravado sozinho.

Depois, a vista **Validação** mostra a concordância do modelo com você, variável por variável: kappa, intervalo de 95% e, para a variável escolhida, a matriz de confusão e as divergências, com o trecho que o modelo citou (veja [Ler kappa e PABAK](../guias/ler-kappa-e-pabak.md)).

## O que você fez

- Criou um projeto e o conferiu no assistente, sem editar YAML.
- Rodou a coleta, os tópicos e a geografia pela vista Projeto, acompanhando o progresso ao vivo.
- Sorteou a amostra de validação, classificou-a com o modelo local e a codificou pelo teclado.
- Viu a concordância entre você e o modelo.

## Próximos passos

- Classifique o corpus inteiro: **Rodar** na estação Classificação. A etapa pode ser cancelada e retomada.
- Revise o codebook no assistente, olhando as divergências, e classifique de novo (veja [Escrever um codebook](../guias/codebook.md)).
- As mesmas etapas pela linha de comando estão nas partes [1](primeiro-mapa.md), [2](primeiro-mapa-topicos.md) e [3](primeiro-mapa-tempo-e-geografia.md) de "Seu primeiro mapa".
