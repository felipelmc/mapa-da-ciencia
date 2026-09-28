// A vista Tópicos (M4), sobre o build servido com o exemplo sintético.
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { h1, inteiro, ler, TELAS, url, vigiar } from './comum';

const topicos = ler('topicos.json');
const documentos = ler('documentos.json');
const macros: { id: number; rotulo: string; topicos: number[] }[] = topicos.macrotemas;

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`desenha o fluxo dos macrotemas (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/topicos`);
		await expect(h1(page)).toHaveText('Tópicos');
		await expect(page.getByTestId('figura-fluxo')).toHaveAttribute('data-pronto', 'sim');
		await expect(page.getByTestId('faixa')).toHaveCount(macros.length + 1); // + "sem tópico"
		await expect(page.getByTestId('resumo-fluxo')).toContainText(`${inteiro(documentos.n)} documentos`);
		if (site === 'RAIZ') await page.screenshot({ path: join(TELAS, 'topicos-1440x900.png'), fullPage: true });
		expect(problemas).toEqual([]);
	});
}

test('os modos mudam a URL, e a tabela bate com o topicos.json', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	await page.getByTestId('modo-proporcao').click();
	await expect(page).toHaveURL(/modo=proporcao/);
	await expect(page.getByTestId('modo-proporcao')).toHaveAttribute('aria-pressed', 'true');
	await expect(page.getByTestId('figura-fluxo').getByText('100%').first()).toBeVisible();
	await page.getByTestId('figura-fluxo').getByRole('button', { name: 'Ver como tabela' }).click();
	const tabela = page.getByTestId('tabela-fluxo');
	await expect(tabela.locator('tbody tr')).toHaveCount(macros.length + 1);
	const doTopico = new Map(topicos.topicos.map((t: { id: number; n: number }) => [t.id, t.n]));
	const primeiro = macros[0];
	const total = primeiro.topicos.reduce((s, t) => s + (doTopico.get(t) as number), 0);
	await expect(tabela.locator('tbody tr', { hasText: primeiro.rotulo }).locator('td').last()).toHaveText(inteiro(total));
});

test('clicar num macrotema abre os tópicos dele, e a trilha volta', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const alvo = macros[2];
	await page.locator(`[data-testid="faixa"][data-id="${alvo.id}"]`).click({ force: true });
	await expect(page).toHaveURL(new RegExp(`macro=${alvo.id}`));
	await expect(page.getByTestId('macro-aberto')).toHaveText(alvo.rotulo);
	await expect(page.getByTestId('faixa')).toHaveCount(alvo.topicos.length);
	await page.getByRole('button', { name: 'Todos os macrotemas' }).click();
	await expect(page).not.toHaveURL(/macro=/);
	await expect(page.getByTestId('faixa')).toHaveCount(macros.length + 1);
});

test('o teclado escolhe a faixa', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	await page.getByTestId('faixa').first().focus();
	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(/macro=\d+/);
});

test('o recorte da barra filtra os documentos do fluxo', async ({ page }) => {
	const revista = documentos.dicionarios.revista[1];
	const i = documentos.dicionarios.revista.indexOf(revista);
	const n = documentos.colunas.revista.filter((r: number) => r === i).length;
	await page.goto(`${url('RAIZ')}#/topicos?revistas=${revista}`);
	await expect(page.getByTestId('resumo-fluxo')).toContainText(`${inteiro(n)} documentos`);
	await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(n));
});

test('em alta e em queda: sem recorte, a lista é a do gabarito do Python', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const esperado = (direcao: string) =>
		topicos.topicos
			.filter((t: { tendencia: { direcao: string } }) => t.tendencia.direcao === direcao)
			.map((t: { id: number }) => String(t.id))
			.sort();
	for (const direcao of ['alta', 'queda']) {
		const itens = page.getByTestId(`lista-${direcao}`).locator('li');
		await expect(itens).toHaveCount(esperado(direcao).length);
		const ids = await itens.evaluateAll((els) => els.map((e) => e.getAttribute('data-id')!));
		expect(ids.sort()).toEqual(esperado(direcao));
	}
	await page.screenshot({ path: join(TELAS, 'topicos-tendencias-1440x900.png'), fullPage: true });
});

test('a ajuda das tendências avisa do pico na borda do período e das marcações marginais', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	await expect(page.getByTestId('cautela-tendencias')).toContainText('primeiro ou no último ano do período');
	await expect(page.getByTestId('cautela-tendencias')).toContainText('marginais');
	await page.goto(`${url('RAIZ')}#/ajuda`);
	await expect(page.getByText(/pico no primeiro ou no último ano/)).toBeVisible();
});

test('com menos de 5 anos no recorte, a lista pede um período maior', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos?anos=2020-2022`);
	await expect(page.getByTestId('tendencias-poucos-anos')).toBeVisible();
});

test('a gaveta abre pelo link topico=, leva ao mapa com o tópico e fecha com Esc', async ({ page }) => {
	const t = topicos.topicos[3];
	await page.goto(`${url('RAIZ')}#/topicos?anos=2012-2024&topico=${t.id}`);
	const gaveta = page.getByTestId('gaveta-topico');
	await expect(gaveta.getByRole('heading', { level: 2 })).toHaveText(t.rotulo);
	await expect(gaveta.getByRole('heading', { level: 2 })).toBeFocused();
	await expect(gaveta.getByTestId('tendencia-gaveta')).toBeVisible();
	await page.screenshot({ path: join(TELAS, 'topicos-gaveta-1440x900.png') });
	await expect(gaveta.getByTestId('ver-no-mapa')).toHaveAttribute('href', `#/mapa?anos=2012-2024&topicos=${t.id}`);
	await page.keyboard.press('Escape');
	await expect(gaveta).toHaveCount(0);
	await expect(page).not.toHaveURL(/topico=/);
	// da lista de tendências também se abre a gaveta
	await page.getByTestId('lista-alta').getByRole('button').first().click();
	await expect(page).toHaveURL(/topico=\d+/);
	await expect(page.getByTestId('gaveta-topico')).toBeVisible();
});

test('fechar a gaveta com Esc devolve o foco a quem a abriu', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const item = page.getByTestId('lista-alta').getByRole('button').first();
	await item.focus();
	await page.keyboard.press('Enter');
	const gaveta = page.getByTestId('gaveta-topico');
	await expect(gaveta.getByRole('heading', { level: 2 })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(gaveta).toHaveCount(0);
	await expect(item).toBeFocused();
});

test('um link com um tópico ou macrotema que não existe avisa e o tira da URL', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos?topico=9999`);
	await expect(page.getByRole('status').filter({ hasText: 'Este tópico não está nesta publicação' })).toBeVisible();
	await expect(page).toHaveURL(/#\/topicos$/);
	await expect(page.getByTestId('gaveta-topico')).toHaveCount(0);
	await page.goto(`${url('RAIZ')}#/topicos?macro=999`);
	await expect(page.getByRole('status').filter({ hasText: 'Este macrotema não está nesta publicação' })).toBeVisible();
	await expect(page).toHaveURL(/#\/topicos$/);
});

test('os pequenos múltiplos por revista filtram o recorte', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const figura = page.getByTestId('figura-por-revista');
	await expect(figura.locator('.multiplo')).toHaveCount(documentos.dicionarios.revista.length);
	const primeira = figura.locator('.titulo-multiplo').first();
	const id = (await primeira.textContent())!.trim().split(/\s/)[0];
	await primeira.click();
	await expect(page).toHaveURL(new RegExp(`revistas=${id}`));
	await expect(primeira).toHaveAttribute('aria-pressed', 'true');
});

test('nos pequenos múltiplos, o último ano de um painel não encosta no primeiro do vizinho', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/topicos`);
	const anos = page.getByTestId('figura-por-revista').locator('.multiplo svg .eixo text');
	await expect(anos.first()).toBeVisible();
	const caixas = (await anos.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON()))) as DOMRect[];
	caixas.sort((a, b) => a.y - b.y || a.x - b.x);
	for (let k = 1; k < caixas.length; k += 1) {
		const [a, b] = [caixas[k - 1], caixas[k]];
		if (Math.abs(a.y - b.y) < 2) expect(a.x + a.width, 'textos do eixo encostados').toBeLessThanOrEqual(b.x - 4);
	}
});

test('projeto vazio: estado vazio, sem pedir arquivos ausentes', async ({ page }) => {
	const pedidos: string[] = [];
	page.on('request', (r) => pedidos.push(new URL(r.url()).pathname));
	await page.goto(`${url('VAZIO')}#/topicos`);
	await expect(page.getByText('Este projeto ainda não tem tópicos.')).toBeVisible();
	await expect(page.getByText('ainda não gerado').first()).toBeVisible();
	expect(pedidos.filter((p) => p.endsWith('.json') && !p.endsWith('manifesto.json'))).toEqual([]);
});
