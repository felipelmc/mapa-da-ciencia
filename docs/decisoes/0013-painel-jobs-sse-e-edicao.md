# 0013. Painel: jobs, progresso ao vivo e edição do projeto

- **Status:** aceita (M6)
- **Data:** 2026-09-26
- **Marco:** M6

## Contexto

Até o M5, o painel só mostrava o que a CLI tinha gerado (e, no M5, gravava a codificação da amostra). O plano do projeto pede que quem não usa o terminal consiga rodar o pipeline pela interface: coletar, gerar os tópicos, a geografia e a classificação, ver o progresso, cancelar, e configurar o projeto (revistas, recorte, modelos, codebook). As etapas levam de segundos (geografia) a horas (classificação), e o navegador pode fechar, recarregar ou perder a conexão no meio.

## Decisão

1. **Jobs no servidor, um por vez.** Um `ThreadPoolExecutor(1)` roda as etapas em segundo plano, as mesmas funções da CLI. Cada job fica na tabela `jobs` do `estado.sqlite` (etapa, opções, estado, início, fim, resumo, erro). Pedir outra etapa com uma rodando dá 409: as etapas leem e escrevem os mesmos arquivos, e duas ao mesmo tempo disputariam a memória dos modelos. Um job que ficou "rodando" quando o painel caiu aparece como interrompido ao abrir de novo.
2. **O progresso é uma sequência de eventos guardados.** Um `ProgressoSSE`, implementação do protocolo `Progresso` que as etapas já usam, grava cada evento (`etapa`, `avanco`, `mensagem`, `resumo`, `erro`, `fim`) numa tabela `eventos`, numerado. Os avanços são agrupados (no máximo quatro por segundo), para uma etapa de milhares de documentos não gerar milhares de linhas.
3. **Server-Sent Events com retomada.** `GET /api/jobs/{job}/eventos` manda os eventos com `id:` = número; o `EventSource` do navegador reconecta sozinho e manda `Last-Event-ID`, e o servidor reenvia só o que falta. O estado montado no navegador ignora eventos repetidos. Um reload no meio de uma etapa retoma o acompanhamento do zero, relendo a sequência. SSE e não WebSocket: o fluxo é num sentido só, passa por qualquer proxy e já traz a reconexão.
4. **Cancelar é cooperativo.** `DELETE /api/jobs/{job}` marca um pedido de parada; o `ProgressoSSE` levanta `Cancelado` (uma `BaseException`, como o ++ctrl+c++) na próxima chamada. As etapas já eram retomáveis (cache da coleta, dos embeddings e da classificação), então parar no meio não perde trabalho.
5. **Editar o projeto sem perder os comentários.** O `mapa.yaml` e o `codebook.yaml` são escritos por quem usa o projeto e vêm comentados. A edição pelo painel usa `ruamel.yaml` em modo *round-trip*: só os valores que mudaram são trocados, e os comentários seguem os itens das listas pelo valor (uma revista) ou pelo `id`/`valor` (uma variável, uma categoria). O resultado passa pelos mesmos modelos Pydantic da leitura antes de ir para o disco; inválido, o arquivo não muda. Nada é editado com uma etapa rodando.
6. **Só nesta máquina.** A API só escuta em `127.0.0.1` e só responde a pedidos cujo `Host` seja local (contra um DNS apontado para cá, que deixaria uma página de fora ler as codificações); as rotas de escrita recusam também um `Origin` de fora: uma página aberta em outro site não consegue rodar etapas nem mudar o projeto pelo navegador, nem com um DNS apontado para cá. O site publicado não tem API.
7. **Testes com etapas falsas.** O registro das etapas do painel pode ser trocado; os testes do servidor usam etapas que emitem progresso sob controle, e os e2e da interface usam uma API falsa em Node que espelha as respostas da API Python (e derruba a primeira conexão SSE de cada job, de propósito, para exercitar a retomada).

## Evidência

- **Testes.** Os testes do servidor rodam cada etapa com um registro falso: o job passa por `na_fila`, `rodando` e `concluido`, um segundo pedido dá 409, o cancelamento para no passo seguinte, um job "rodando" de uma sessão anterior aparece como interrompido, e a leitura dos eventos com `Last-Event-ID` devolve só os que faltam. Nos e2e, a primeira conexão SSE de cada job cai de propósito, e o painel retoma o acompanhamento sem perder nem repetir eventos; um reload no meio da etapa também.
- **O pipeline pela interface.** O projeto do tutorial (*Opinião Pública*, 2010–2025) foi criado e rodado inteiro pelo painel, sem o terminal: a coleta refeita do cache (396 artigos, nenhuma requisição), os *embeddings* (37 s), 13 tópicos em 4 macrotemas (293 s), a geografia (859 vínculos, 94,4% ligados a uma de 145 instituições, em menos de 1 s), a amostra de validação sorteada pela estação da linha de metrô e 20 resumos classificados (454 s, sem falhas).
- **Edição do YAML.** Os testes editam o `mapa.yaml` e o `codebook.yaml` de exemplo pelo painel e conferem que os comentários continuam no arquivo, que uma edição inválida não muda nada e que nada muda com uma etapa rodando.

## Consequências

- `ruamel.yaml` entra como dependência (Python puro).
- A linha de metrô da vista Projeto mostra o estado de cada etapa (pendente, em dia, incompleta, desatualizada) calculado pelo mesmo código do `mapa status`.
- Uma etapa rodada pela CLI enquanto o painel está aberto não passa pela fila de jobs; as duas não são impedidas de rodar ao mesmo tempo. O painel mostra o resultado quando a etapa termina.
- O download de um modelo (`ollama pull`) também é um job, com o progresso por camada.
