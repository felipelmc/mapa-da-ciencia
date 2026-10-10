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
- Uma etapa rodada pela CLI enquanto o painel está aberto não passa pela fila de jobs; as duas não são impedidas de rodar ao mesmo tempo. O painel mostra o resultado quando a etapa termina. (Desde a 2.3.0, as duas se impedem: veja o adendo.)
- O download de um modelo (`ollama pull`) também é um job, com o progresso por camada.

## Adendo (2.3.0): uma etapa por vez, também fora do painel

A consequência acima (uma etapa pela CLI passa por cima da fila) foi registrada como risco e se confirmou na revisão: uma coleta no terminal regravava o corpus enquanto o painel calculava os tópicos, e as duas exportavam `saida/dados/` por cima uma da outra. **Decisão:** toda função que escreve em `dados/` ou `saida/`, ou que carrega um modelo, trava o projeto enquanto roda (`trava_etapas.py`: `flock` num `.etapa.lock` na pasta do projeto, com o PID, a etapa, a origem e a hora; o decorador `@etapa`). A trava é a mesma para a CLI, o notebook e os jobs do painel, e é reentrante na mesma thread (a votação do júri chama a classificação).

- **Na CLI e no notebook**, uma etapa com outra rodando sai com `EtapaEmAndamento` (um `ErroConfig`, que a CLI mostra sem traceback), dizendo qual etapa roda, onde (pelo painel, com o endereço lido do `.painel.lock`, ou em outro terminal ou notebook) e desde quando.
- **No painel**, `POST /api/etapas/{etapa}` e as rotas que mudam o projeto respondem 409 com `em_andamento`, e `GET /api/projeto/etapas` traz `em_andamento` enquanto a etapa de fora roda; a vista Projeto desativa os botões e consulta de novo a cada 5 s. Baixar um modelo não escreve no projeto e continua liberado.
- **Sem travar para ler:** `quem_roda` lê o dono do arquivo, e um PID que já não existe quer dizer livre; o sistema solta o `flock` quando o processo morre. Entre a consulta e a trava, uma etapa pode ganhar a corrida: o job do painel falha com a mesma mensagem.
- Sem `fcntl` (Windows), não há trava, como no `.painel.lock`.

Alternativas descartadas: travar só nos comandos da CLI (o notebook e o painel ficariam de fora, e um comando novo poderia esquecer a trava) e uma fila comum em SQLite (precisaria de um processo dono da fila; o painel nem sempre está aberto).

