// A vista Projeto (M6) contra a API falsa do painel (api-falsa-painel.ts): a linha de metrô, o job ao vivo (que
// sobrevive à queda da primeira conexão SSE), cancelar, retomar depois de um reload e baixar um modelo.
import { expect, test } from '@playwright/test';
import { join } from 'node:path';
import { h1, TELAS, url, vigiar } from './comum';

/** Os problemas, menos os da queda proposital da primeira conexão SSE (ver api-falsa-painel.ts). */
const semAQueda = (problemas: string[]) =>
	problemas.filter((p) => !p.includes('/eventos') && !p.includes('ERR_INCOMPLETE_CHUNKED_ENCODING'));

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

test('no site estático, a vista explica que é do painel', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/projeto`);
	await expect(page.getByText('só existe no painel local')).toBeVisible();
});

test('a linha de metrô, a estimativa e os modelos', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('PAINEL')}#/projeto`);
	await expect(h1(page)).toHaveText('Projeto');
	await expect(page.getByTestId('linha-metro').getByRole('listitem')).toHaveCount(5);
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
	await page.getByTestId('cancelar-job').click();
	await expect(page.getByTestId('estado-job')).toHaveText('Cancelado');
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
	// 1. fontes: tirar a única revista não deixa avançar; procurar e incluir outra
	await assistente.getByRole('button', { name: 'Tirar Opinião Pública' }).click();
	await assistente.getByTestId('avancar').click();
	await expect(assistente.getByRole('alert')).toHaveText('Escolha pelo menos uma revista.');
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
	// 4. codebook: uma variável nova
	await assistente.getByTestId('nova-variavel').click();
	await assistente.getByTestId('avancar').click();
	// 5. revisão: o que muda e o que isso refaz
	const mudancas = assistente.getByTestId('mudancas');
	await expect(mudancas).toContainText('Revistas incluídas: Revista Brasileira de Ciência Política');
	await expect(mudancas).toContainText('Revistas retiradas: Opinião Pública');
	await expect(mudancas).toContainText('Período: 2010–2025 → 2015–2025');
	await expect(mudancas).toContainText('Classificação: qwen3.5:9b → qwen3.5:4b');
	await expect(mudancas).toContainText('O codebook mudou.');
	await assistente.getByTestId('salvar-piloto').click();
	await expect(page.getByTestId('projeto-salvo')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Etapa: Coleta' })).toBeVisible();
	await expect(page.getByTestId('estado-job')).toHaveText('Concluído', { timeout: 15_000 });
	const config = await (await page.request.get(`${url('PAINEL')}api/configuracao`)).json();
	expect(config.recorte.anos).toEqual([2015, 2025]);
	expect(config.fontes.scielo.revistas).toEqual(['0103-3352']);
	expect(config.modelos.classificacao.modelo).toBe('qwen3.5:4b');
	const codebook = await (await page.request.get(`${url('PAINEL')}api/codebook`)).json();
	expect(codebook.variaveis.at(-1).rotulo).toMatch(/^Variável \d+$/);
	expect(semAQueda(problemas)).toEqual([]);
});
