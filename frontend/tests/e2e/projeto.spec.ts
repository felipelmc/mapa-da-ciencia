// A vista Projeto (M6) contra a API falsa do painel (api-falsa-painel.ts): a linha de metrô, o job ao vivo (que
// sobrevive à queda da primeira conexão SSE), cancelar, retomar depois de um reload e baixar um modelo.
import { expect, test } from '@playwright/test';
import { join } from 'node:path';
import { h1, TELAS, url, vigiar } from './comum';

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

test('rodar uma etapa: progresso ao vivo, mesmo com a conexão caindo, e a estação fica em dia', async ({ page }) => {
	const problemas = vigiar(page).filter(() => true);
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
	expect(problemas.filter((p) => !p.includes('/eventos'))).toEqual([]);
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
	await expect(page.getByTestId('passo-job')).toContainText(/[3-9] de 20|1\d de 20/);
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
