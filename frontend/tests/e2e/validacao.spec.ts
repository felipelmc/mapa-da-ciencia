// Validação › Concordância (M5), sobre o build com o exemplo sintético (e a API falsa, no painel).
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { h1, ler, TELAS, url, vigiar } from './comum';

const validacao = ler('validacao.json');

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

test('mostra os participantes, as métricas do par e as divergências da variável', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/validacao`);
	await expect(h1(page)).toHaveText('Validação');
	await expect(page.getByTestId('lide-validacao')).toContainText(`Amostra de ${validacao.amostra.n} documentos`);
	// o codificador de referência é identificado como tal
	await expect(page.getByTestId('aviso-referencia')).toBeVisible();
	await expect(page.getByTestId('lide-validacao')).toContainText('referência (não humano)');
	const doPar = validacao.metricas.filter((m: { referencia: string }) => m.referencia === 'referencia-exemplo');
	await expect(page.getByTestId('linha-variavel')).toHaveCount(doPar.length);
	await expect(page.getByTestId('matriz-confusao')).toBeVisible();
	// a segunda variável: as divergências dela, com a evidência do modelo
	const segunda = doPar[1];
	await page.getByTestId('linha-variavel').nth(1).click();
	const esperadas = validacao.divergencias.filter((d: { variavel: string }) => d.variavel === segunda.variavel).length;
	if (esperadas) await expect(page.getByTestId('divergencias').locator('li')).toHaveCount(esperadas);
	await expect(page.getByTestId('link-codificar')).toHaveCount(0); // site estático: sem codificação
	await page.screenshot({ path: join(TELAS, 'validacao-1440x900.png'), fullPage: true });
	expect(problemas).toEqual([]);
});

test('kappa nulo: "não se aplica" na variável de texto livre, "sem variação" só nas outras', async ({ page }) => {
	// o exemplo não tem essas métricas; o pipeline as gera (texto livre: só a concordância)
	const base = validacao.metricas[0];
	const nula = (variavel: string, concordancia: number) => ({
		...base,
		variavel,
		concordancia,
		kappa: null,
		kappa_ic95: null,
		pabak: null,
		alfa: null,
		matriz: { rotulos: [], valores: [] },
		por_classe: []
	});
	await page.route('**/dados/validacao.json', (r) =>
		r.fulfill({
			json: {
				...validacao,
				metricas: [...validacao.metricas, nula('periodo_analisado', 0.84), nula('recorte_geografico:nacional', 1)]
			}
		})
	);
	await page.goto(`${url('RAIZ')}#/validacao`);
	const tabela = page.getByTestId('tabela-metricas');
	const texto = tabela.getByRole('row', { name: /Período analisado/ });
	await expect(texto).toContainText('não se aplica (texto livre)');
	await expect(texto).not.toContainText('sem variação');
	await expect(tabela.getByRole('row', { name: /Recorte geográfico/ }).last()).toContainText('indefinido (sem variação)');
});

test('no painel, as métricas vêm da API e há o link para codificar', async ({ page }) => {
	const problemas = vigiar(page);
	const pedidos: string[] = [];
	page.on('request', (r) => pedidos.push(new URL(r.url()).pathname));
	await page.goto(`${url('PAINEL')}#/validacao`);
	await expect(h1(page)).toHaveText('Validação');
	await expect(page.getByTestId('link-codificar')).toBeVisible();
	expect(pedidos).toContain('/api/validacao/metricas');
	await page.getByTestId('link-codificar').click();
	await expect(page).toHaveURL(/#\/validacao\/codificar/);
	await expect(page.getByRole('link', { name: 'Validação' })).toHaveAttribute('aria-current', 'page');
	expect(problemas).toEqual([]);
});
