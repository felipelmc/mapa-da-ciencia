// A vista Projeto (M6) contra a API falsa do painel (api-falsa-painel.ts): a linha de metrô, o job ao vivo (que
// sobrevive à queda da primeira conexão SSE), cancelar, retomar depois de um reload e baixar um modelo.
import { expect, test } from '@playwright/test';
import { join } from 'node:path';
import { h1, ler, TELAS, url, vigiar } from './comum';

/** Os problemas, menos os da queda proposital da primeira conexão SSE (ver api-falsa-painel.ts). */
const semAQueda = (problemas: string[]) =>
	problemas.filter((p) => !p.includes('/eventos') && !p.includes('ERR_INCOMPLETE_CHUNKED_ENCODING'));

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

test('no site estático, a seção vira a Metodologia, tirada do manifesto', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/projeto`);
	await expect(h1(page)).toHaveText('Metodologia');
	await expect(page.getByTestId('modelos-metodologia')).toContainText('Classificação');
	// a versão exata dos modelos, o hash e a versão do contrato ficam no bloco recolhido "Para reproduzir"
	const reproduzir = page.getByTestId('para-reproduzir');
	const versao = `versão ${ler('manifesto.json').versao_contrato}`;
	await expect(reproduzir.getByText(versao)).toBeHidden();
	await reproduzir.locator('summary').click();
	await expect(reproduzir.getByText(versao)).toBeVisible();
	await expect(page.getByRole('link', { name: 'Desenho da validação' })).toBeVisible();
	expect(problemas).toEqual([]);
});

test('a linha de metrô, a estimativa e os modelos', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('PAINEL')}#/projeto`);
	await expect(h1(page)).toHaveText('Projeto');
	await expect(page.getByTestId('linha-metro').getByRole('listitem')).toHaveCount(7);
	// o júri (o projeto tem `juri.membros`): o estado e o próximo comando, sem botão de rodar
	const juri = page.getByTestId('estacao-juri');
	await expect(page.getByTestId('estado-juri')).toHaveText('Incompleta');
	await expect(page.getByTestId('proximo-juri')).toContainText('mapa juri exportar-pedidos');
	await expect(juri.getByRole('link', { name: 'Como usar o júri' })).toBeVisible();
	await expect(juri.getByRole('button')).toHaveCount(0);
	// o comando longo quebra dentro da estação: a página não rola de lado
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
	// as redes, depois da geografia: desatualizadas, com o que mudou, e o botão diz "Atualizar"
	await expect(page.getByTestId('estado-redes')).toHaveText('Desatualizada');
	await expect(page.getByTestId('mudou-redes')).toHaveText('Mudou o pessoas.yaml');
	await expect(page.getByTestId('rodar-redes')).toHaveText('Atualizar');
	await expect(page.getByTestId('estado-classificacao')).toHaveText('Desatualizada');
	await expect(page.getByTestId('estacao-classificacao')).toHaveAttribute('data-estado', 'desatualizada');
	await expect(page.getByTestId('estimativa')).toContainText('Faltam 1.280, cerca de 3 h 55 min');
	await expect(page.getByTestId('baixar-classificacao')).toHaveText('Baixar (6,6 GB)');
	expect(problemas).toEqual([]);
});

test('sortear a amostra de validação pela estação', async ({ page }) => {
	await page.goto(`${url('PAINEL')}#/projeto`);
	const estacao = page.getByTestId('estacao-validacao');
	await estacao.getByTestId('tamanho-amostra').fill('40');
	await estacao.getByTestId('sortear-amostra').click();
	await expect(estacao).toContainText('0 documentos de 40 codificados');
	await expect(estacao.getByRole('link', { name: 'Codificar a amostra' })).toBeVisible();
});

test('rodar uma etapa: progresso ao vivo, mesmo com a conexão caindo, e a estação fica em dia', async ({ page }) => {
	const problemas = vigiar(page);
	const conexoes: string[] = [];
	page.on('request', (r) => r.url().includes('/eventos') && conexoes.push(r.url()));
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('rodar-topicos').click();
	const job = page.getByTestId('job-ao-vivo');
	await expect(job).toBeVisible();
	await expect(page.getByTestId('rodar-coleta')).toBeDisabled(); // uma etapa por vez
	await expect(page.getByTestId('estacao-topicos')).toHaveAttribute('data-estado', 'rodando');
	await expect(page.getByTestId('estado-job')).toHaveText('Concluído', { timeout: 15_000 });
	await expect(page.getByTestId('passo-job')).toContainText('20 de 20');
	await page.screenshot({ path: join(TELAS, 'projeto-1440x900.png'), fullPage: true });
	// a primeira conexão caiu depois de 5 eventos: o navegador reconectou e nada se repetiu
	expect(conexoes.length).toBeGreaterThanOrEqual(2);
	await expect(page.getByTestId('mensagens-job').getByRole('listitem')).toHaveText([
		'passo 5 de 20',
		'passo 10 de 20',
		'passo 15 de 20',
		'passo 20 de 20'
	]);
	await expect(page.getByTestId('resumo-job')).toHaveText('topicos: 20 passos feitos.');
	await expect(page.getByTestId('estado-topicos')).toHaveText('Em dia');
	await expect(page.getByTestId('historico')).toContainText('Tópicos');
	await expect(page.getByTestId('recarregar')).toBeVisible();
	expect(semAQueda(problemas)).toEqual([]);
});

test('cancelar um job', async ({ page }) => {
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('estacao-classificacao').getByRole('button', { name: 'Só a amostra' }).click();
	await expect(page.getByTestId('estado-job')).toHaveText('Rodando');
	// o histórico acompanha o job ao vivo (não fica "na fila", o estado que o POST devolveu)
	const ultima = page.getByTestId('historico').getByRole('listitem').first();
	await expect(ultima.getByTestId('estado-historico')).toHaveText('rodando');
	await page.getByTestId('cancelar-job').click();
	await expect(page.getByTestId('estado-job')).toHaveText('Cancelado');
	await expect(ultima.getByTestId('estado-historico')).toHaveText('cancelado');
	await expect(page.getByTestId('rodar-coleta')).toBeEnabled();
});

test('um reload no meio retoma o acompanhamento do job', async ({ page }) => {
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('rodar-geografia').click();
	await expect(page.getByTestId('estado-job')).toHaveText('Rodando');
	await page.reload();
	await expect(page.getByTestId('job-ao-vivo')).toBeVisible();
	await expect(page.getByTestId('estado-job')).toHaveText('Concluído', { timeout: 15_000 });
	await expect(page.getByTestId('mensagens-job').getByRole('listitem')).toHaveCount(4);
});

test('baixar um modelo que falta', async ({ page }) => {
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('baixar-classificacao').click();
	await expect(page.getByRole('heading', { name: 'Download do modelo' })).toBeVisible();
	await expect(page.getByTestId('estado-job')).toHaveText('Concluído', { timeout: 15_000 });
	await expect(page.getByTestId('modelos')).not.toContainText('Baixar');
});

// Por último: o assistente muda a configuração da API falsa (os modelos), e os testes acima contam com a original.
test('o assistente em 5 passos salva o projeto e roda um piloto', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('configurar').click();
	const assistente = page.getByTestId('assistente');
	await expect(assistente.getByTestId('revistas-escolhidas')).toContainText('Opinião Pública');
	// 1. fontes: sem revistas, o assistente avisa que o corpus vem dos arquivos importados (um projeto só de
	// importação configura sem revista nenhuma); procurar e incluir outra
	await assistente.getByRole('button', { name: 'Tirar Opinião Pública' }).click();
	await expect(assistente.getByTestId('sem-revistas')).toBeVisible();
	await assistente.getByTestId('busca-revista').fill('ciencia politica');
	await assistente.getByTestId('incluir-revista').first().click();
	await expect(assistente.getByTestId('revistas-escolhidas')).toContainText('Revista Brasileira de Ciência Política');
	await assistente.getByTestId('avancar').click();
	// 2. recorte
	await expect(assistente.getByTestId('passo-2')).toBeVisible();
	await assistente.getByTestId('ano-inicio').fill('2015');
	await assistente.getByTestId('avancar').click();
	// 3. modelos: o perfil leve troca a classificação por um modelo já instalado
	await assistente.getByTestId('perfil-leve').click();
	await expect(assistente.getByTestId('perfil-leve')).toHaveAttribute('aria-pressed', 'true');
	await assistente.screenshot({ path: join(TELAS, 'assistente-modelos.png') });
	await assistente.getByTestId('avancar').click();
	// 4. codebook: uma variável nova, e outra que vira booleana (as categorias dela saem)
	await assistente.getByTestId('nova-variavel').click();
	await assistente.getByTestId('nova-variavel').click();
	const virouBooleana = assistente.locator('details.variavel').last();
	await virouBooleana.getByLabel('Tipo').selectOption('booleana');
	await expect(virouBooleana.locator('table.categorias')).toHaveCount(0);
	await assistente.getByTestId('avancar').click();
	// 5. revisão: o que muda e o que isso refaz
	const mudancas = assistente.getByTestId('mudancas');
	await expect(mudancas).toContainText('Revistas incluídas: Revista Brasileira de Ciência Política');
	await expect(mudancas).toContainText('Revistas retiradas: Opinião Pública');
	await expect(mudancas).toContainText('Período: 2010–2025 → 2015–2025');
	await expect(mudancas).toContainText('Classificação: qwen3.5:9b → qwen3.5:4b');
	await expect(mudancas).toContainText('O codebook mudou no que o modelo lê.');
	await expect(mudancas).toContainText('a classificação inteira');
	await assistente.getByTestId('salvar-piloto').click();
	await expect(page.getByTestId('projeto-salvo')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Etapa: Coleta' })).toBeVisible();
	await expect(page.getByTestId('estado-job')).toHaveText('Concluído', { timeout: 15_000 });
	const config = await (await page.request.get(`${url('PAINEL')}api/configuracao`)).json();
	expect(config.recorte.anos).toEqual([2015, 2025]);
	expect(config.fontes.scielo.revistas).toEqual(['0103-3352']);
	expect(config.modelos.classificacao.modelo).toBe('qwen3.5:4b');
	const codebook = await (await page.request.get(`${url('PAINEL')}api/codebook`)).json();
	expect(codebook.variaveis.at(-2).rotulo).toMatch(/^Variável \d+$/);
	expect(codebook.variaveis.at(-1)).toMatchObject({ tipo: 'booleana' });
	expect(codebook.variaveis.at(-1).categorias ?? []).toEqual([]);
	expect(semAQueda(problemas)).toEqual([]);
});

test('rodar as redes pela estação: a vista Redes não depende da CLI', async ({ page }) => {
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('rodar-redes').click();
	await expect(page.getByTestId('estado-job')).toHaveText('Concluído', { timeout: 15_000 });
	await expect(page.getByTestId('estado-redes')).toHaveText('Em dia');
	await expect(page.getByTestId('mudou-redes')).toHaveCount(0);
});

test('no celular, as etapas ficam uma embaixo da outra', async ({ browser }) => {
	const contexto = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
	const page = await contexto.newPage();
	await page.goto(`${url('PAINEL')}#/projeto`);
	const estacoes = page.getByTestId('linha-metro').locator(':scope > li');
	await expect(estacoes.first()).toBeVisible();
	const caixas = await estacoes.evaluateAll((els) => els.map((e) => e.getBoundingClientRect()).map((c) => [c.left, c.top, c.width]));
	expect(new Set(caixas.map(([x]) => Math.round(x))).size).toBe(1); // a mesma coluna
	expect(caixas.every(([, , w]) => w > 250)).toBe(true);
	for (let i = 1; i < caixas.length; i += 1) expect(caixas[i][1]).toBeGreaterThan(caixas[i - 1][1]);
	await contexto.close();
});

test('com uma etapa rodando no terminal, o painel não começa outra e avisa até ela terminar', async ({ page }) => {
	const terminal = `${url('PAINEL')}api/__teste/terminal`;
	await page.request.post(terminal, { data: { etapa: 'coleta' } });
	try {
		await page.goto(`${url('PAINEL')}#/projeto`);
		await expect(page.getByTestId('etapa-fora')).toContainText('A etapa coleta está rodando em outro terminal ou notebook');
		await expect(page.getByTestId('estado-coleta')).toHaveText('Rodando…');
		await expect(page.getByTestId('rodar-topicos')).toBeDisabled();
		await expect(page.getByTestId('configurar')).toBeDisabled();
		// terminou no terminal: a linha confere a cada 5 s e volta a liberar
		await page.request.delete(terminal);
		await expect(page.getByTestId('etapa-fora')).toHaveCount(0, { timeout: 8000 });
		await expect(page.getByTestId('rodar-topicos')).toBeEnabled();
	} finally {
		await page.request.delete(terminal);
	}
});

test('o painel já aberto nota a etapa que começa no terminal', async ({ page }) => {
	const terminal = `${url('PAINEL')}api/__teste/terminal`;
	await page.goto(`${url('PAINEL')}#/projeto`);
	await expect(page.getByTestId('rodar-topicos')).toBeEnabled();
	await page.request.post(terminal, { data: { etapa: 'geografia' } });
	try {
		await expect(page.getByTestId('etapa-fora')).toContainText('A etapa geografia está rodando', { timeout: 8000 });
		await expect(page.getByTestId('rodar-topicos')).toBeDisabled();
	} finally {
		await page.request.delete(terminal);
	}
});

test('o editor dos rótulos grava só o que mudou e aplica sem refazer os tópicos', async ({ page }) => {
	const topicos = ler('topicos.json');
	const t0 = topicos.topicos.find((t: { id: number }) => t.id === 0);
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('editar-rotulos').click();
	const editor = page.getByTestId('editor-rotulos');
	await expect(editor.locator('#rotulo-t-0')).toHaveValue(t0.rotulo);
	await expect(editor.getByTestId('salvar-rotulos')).toBeDisabled(); // nada mudou
	// um acento perdido ("coalizao", e a palavra-chave é "coalizão") não impede de salvar, mas segura o editor antes de aplicar
	await editor.locator('#rotulo-t-0').fill('Coalizao no congresso');
	await expect(editor.getByTestId('salvar-rotulos')).toHaveText('Salvar e aplicar 1 rótulo');
	const pedido = page.waitForRequest((r) => r.url().endsWith('/api/rotulos') && r.method() === 'PATCH');
	await editor.getByTestId('salvar-rotulos').click();
	expect((await pedido).postDataJSON()).toEqual({
		topicos: { '0': { rotulo: 'Coalizao no congresso', descricao: t0.descricao } },
		macrotemas: {}
	});
	await expect(editor.getByTestId('avisos-rotulos')).toContainText('“coalizao”');
	await expect(editor.getByTestId('pe-rotulos')).toBeInViewport(); // o aviso fica no pé da tela, à vista
	// o arquivo já tem o texto do aviso: voltar ao texto de antes conta como mudança (e não fica preso no arquivo)
	await editor.locator('#rotulo-t-0').fill(t0.rotulo);
	await expect(editor.getByTestId('salvar-rotulos')).toHaveText('Salvar e aplicar 1 rótulo');
	await editor.locator('#rotulo-t-0').fill('Coalizao no congresso');
	await expect(editor.getByTestId('salvar-rotulos')).toHaveText('Aplicar');
	const job = page.waitForRequest((r) => r.url().endsWith('/api/etapas/topicos') && r.method() === 'POST');
	await editor.getByTestId('aplicar-assim').click();
	expect((await job).postDataJSON()).toEqual({ aplicar_rotulos: true });
	await expect(editor).toHaveCount(0);
	// de volta ao do modelo: a entrada sai do arquivo
	await expect(page.getByTestId('editar-rotulos')).toBeEnabled({ timeout: 10_000 });
	await page.getByTestId('editar-rotulos').click();
	await expect(page.getByTestId('fonte-t:0')).toHaveText('à mão');
	await page.getByTestId('voltar-t:0').check();
	const volta = page.waitForRequest((r) => r.url().endsWith('/api/rotulos') && r.method() === 'PATCH');
	await page.getByTestId('salvar-rotulos').click();
	expect((await volta).postDataJSON()).toEqual({ topicos: { '0': null }, macrotemas: {} });
});

test('no celular, o botão de salvar os rótulos fica acima da barra de navegação', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 740 });
	await page.goto(`${url('PAINEL')}#/projeto`);
	await page.getByTestId('editar-rotulos').click();
	await page.locator('#rotulo-t-0').fill('Um rótulo novo');
	const salvar = page.getByTestId('salvar-rotulos');
	await expect(salvar).toBeInViewport();
	const botao = (await salvar.boundingBox())!;
	const barra = (await page.getByRole('navigation', { name: 'Seções' }).boundingBox())!;
	expect(botao.y + botao.height).toBeLessThanOrEqual(barra.y);
	page.once('dialog', (d) => d.accept()); // sair com a mudança pergunta antes
	await page.getByRole('button', { name: 'Fechar sem salvar' }).click();
	await expect(page.getByTestId('editor-rotulos')).toHaveCount(0);
});

test('a gaveta do tópico leva ao editor do rótulo, só no painel', async ({ page }) => {
	const t = ler('topicos.json').topicos[3];
	await page.goto(`${url('PAINEL')}#/topicos?topico=${t.id}`);
	await page.getByTestId('gaveta-topico').getByTestId('editar-rotulo').click();
	await expect(page).toHaveURL(new RegExp(`#/projeto\\?topico=${t.id}`));
	await expect(page.locator(`#rotulo-t-${t.id}`)).toBeFocused();
	await page.getByTestId('editor-rotulos').screenshot({ path: join(TELAS, 'projeto-rotulos.png') });
	await page.getByRole('button', { name: 'Fechar sem salvar' }).click();
	await expect(page).not.toHaveURL(/topico=/);
	await page.goto(`${url('PUBLICADO')}#/topicos?topico=${t.id}`);
	await expect(page.getByTestId('gaveta-topico')).toBeVisible();
	await expect(page.getByTestId('editar-rotulo')).toHaveCount(0);
});
