// A vista do mapa (M3), sobre o build servido com o exemplo sintético.
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { esperarMapa, h1, inteiro, ler, RAIZ, trilho, url, vigiar } from './comum';

const documentos = ler('documentos.json');
const topicos = ler('topicos.json');
const n: number = documentos.n;

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`desenha os documentos do exemplo (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/mapa`);
		await expect(h1(page)).toHaveText('Mapa');
		const d = await esperarMapa(page);
		expect(d.erro).toBeNull();
		expect(d.pontos).toBe(n);
		expect(d.visiveis).toBe(n);
		await expect(page.getByTestId('contador-mapa')).toContainText(inteiro(n));
		console.log(`primeiro desenho: ${Math.round(d.msAtePrimeiroDesenho!)} ms`, d.etapasMs, d.renderer);
		// No Mac do desenvolvimento, o critério do M3; no CI (WebGL por software), só o registro acima.
		if (!process.env.CI) expect(d.msAtePrimeiroDesenho!).toBeLessThan(1500);
		expect(page.url()).not.toContain('vista='); // a câmera inicial não vai para o link
		expect(problemas).toEqual([]);
	});
}

test('contornos e rótulos: macrotemas de longe, tópicos de perto', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.anotacoes ?? 0)).toBeGreaterThanOrEqual(topicos.topicos.length);
	const rotulos = page.getByTestId('rotulo-mapa');
	await expect(rotulos.first()).toBeVisible();
	const macros: string[] = topicos.macrotemas.map((m: { rotulo: string }) => m.rotulo);
	expect(macros).toContain(await rotulos.first().textContent().then((t) => t?.trim()));

	// aproxima com a roda do mouse: os rótulos passam a ser dos tópicos
	const canvas = page.getByTestId('canvas-mapa');
	const caixa = (await canvas.boundingBox())!;
	await page.mouse.move(caixa.x + caixa.width * 0.7, caixa.y + caixa.height * 0.5);
	for (let i = 0; i < 2; i += 1) await page.mouse.wheel(0, -300); // ~2× (os rótulos dos tópicos entram a 1,8×)
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.zoom ?? 1)).toBeGreaterThan(1.8);
	const nomesTopicos: string[] = topicos.topicos.map((t: { rotulo: string }) => t.rotulo);
	await expect.poll(async () => {
		const textos = await rotulos.allTextContents();
		return textos.some((t) => nomesTopicos.includes(t.trim()));
	}).toBe(true);
	await expect(page).toHaveURL(/vista=/); // a câmera foi para o link

	// clicar num rótulo filtra o tópico
	const alvo = rotulos.filter({ hasText: new RegExp(nomesTopicos.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')) }).first();
	await alvo.click();
	await expect(page).toHaveURL(/topicos=/);
	expect(problemas).toEqual([]);
});

test('a legenda filtra por tópico, e "Limpar filtros" volta ao todo', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const primeiro = topicos.topicos[0];
	await page.getByTestId('legenda-mapa').getByRole('button', { name: primeiro.rotulo }).click();
	await expect(page).toHaveURL(new RegExp(`topicos=${primeiro.id}(&|$)`));
	const doTopico = documentos.colunas.topico.filter((t: number) => t === primeiro.id).length;
	await expect(page.getByTestId('contador-mapa')).toContainText(inteiro(doTopico));
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(doTopico);

	await page.getByRole('button', { name: 'Limpar filtros' }).click();
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(n);
	await expect(page).toHaveURL(/#\/mapa$/);
	expect(problemas).toEqual([]);
});

test('colorir por revista muda a URL e a legenda', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.getByTestId('cor-por').selectOption('revista');
	await expect(page).toHaveURL(/cor=revista/);
	await expect(page.getByTestId('legenda-mapa').getByRole('listitem')).toHaveCount(documentos.dicionarios.revista.length);
	// a cor por ano não tem legenda por categoria: um degradê do primeiro ao último ano
	await page.getByTestId('cor-por').selectOption('ano');
	await expect(page.getByTestId('legenda-mapa')).toHaveCount(0);
});

test('projeto sem tópicos: o mapa explica o que fazer e não pede arquivos ausentes', async ({ page }) => {
	const problemas = vigiar(page);
	const dados: string[] = [];
	page.on('request', (r) => {
		const caminho = new URL(r.url()).pathname;
		if (caminho.startsWith('/dados/')) dados.push(caminho);
	});
	await page.goto(url('VAZIO'));
	await trilho(page).getByRole('link', { name: 'Mapa', exact: true }).click();
	await expect(h1(page)).toHaveText('Mapa');
	await expect(page.getByRole('heading', { name: 'Este projeto ainda não tem mapa.' })).toBeVisible();
	expect(dados).toEqual(['/dados/manifesto.json']);
	expect(problemas).toEqual([]);
});

// ---- cartão do documento

type Detalhe = { resumo: string | null; fonte_analise?: string; licenca: string };
const detalhes: Record<string, Detalhe> = {};
const pastaDetalhes = join(RAIZ, '..', 'contrato', 'exemplo', 'dados', 'detalhes');
for (const arquivo of readdirSync(pastaDetalhes)) Object.assign(detalhes, ler(`detalhes/${arquivo}`).documentos);
const ids: string[] = documentos.colunas.id;
const titulo = (id: string) => documentos.colunas.titulo[ids.indexOf(id)];

test('o link com doc= abre o cartão, e os vizinhos navegam', async ({ page }) => {
	const problemas = vigiar(page);
	const id = ids.find((i) => detalhes[i].fonte_analise === 'reserva')!;
	await page.goto(`${url('RAIZ')}#/mapa?doc=${encodeURIComponent(id)}`);
	await esperarMapa(page);
	const cartao = page.getByTestId('cartao-documento');
	await expect(cartao.getByRole('heading', { level: 2 })).toHaveText(titulo(id));
	await expect(cartao.getByTestId('nota-analise')).toContainText('Sem resumo em inglês');
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.destaque)).toBe(ids.indexOf(id));

	const vizinho = ids[documentos.colunas.vizinhos[ids.indexOf(id)][0]];
	await cartao.getByTestId('vizinhos').getByRole('button').first().click();
	await expect(page).toHaveURL(new RegExp(`doc=${encodeURIComponent(vizinho).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
	await expect(cartao.getByRole('heading', { level: 2 })).toHaveText(titulo(vizinho));

	await page.keyboard.press('Escape');
	await expect(cartao).toHaveCount(0);
	await expect(page).not.toHaveURL(/doc=/);
	expect(problemas).toEqual([]);
});

test('resumo sem licença para mostrar dá o aviso; o botão fecha o cartão', async ({ page }) => {
	const id = ids.find((i) => detalhes[i].resumo === null && detalhes[i].fonte_analise !== 'so_titulo')!;
	await page.goto(`${url('RAIZ')}#/mapa?doc=${encodeURIComponent(id)}`);
	await esperarMapa(page);
	const cartao = page.getByTestId('cartao-documento');
	await expect(cartao).toContainText('não permite mostrá-lo aqui');
	await cartao.getByRole('button', { name: 'Fechar o cartão' }).click();
	await expect(cartao).toHaveCount(0);
});

test('clicar num ponto abre o cartão dele', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const caixa = (await page.getByTestId('canvas-mapa').boundingBox())!;
	// um ponto longe do painel da esquerda e dos rótulos
	const alvo = await page.evaluate((largura) => {
		const d = window.__mapaDebug!;
		for (let i = 0; i < d.pontos; i += 1) {
			const p = d.posicaoNaTela?.(i);
			if (p && p[0] > 420 && p[0] < largura - 450 && p[1] > 80) return { i, p };
		}
		return null;
	}, caixa.width);
	expect(alvo).not.toBeNull();
	await page.mouse.click(caixa.x + alvo!.p[0], caixa.y + alvo!.p[1]);
	await expect(page.getByTestId('cartao-documento')).toBeVisible();
	await expect(page).toHaveURL(/doc=/);
});

// ---- busca, laço, linha do tempo e atalhos
test('busca com "/" e sem acentos; um resultado abre o cartão', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.keyboard.press('/');
	await expect(page.getByTestId('busca-mapa')).toBeFocused();
	const palavra = documentos.colunas.titulo[0].split(' ')[0]; // a primeira palavra de um título
	const semAcento = palavra.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase();
	await page.keyboard.type(semAcento);
	await expect(page).toHaveURL(/busca=/);
	const d = await page.evaluate(() => window.__mapaDebug!);
	expect(d.visiveis).toBeGreaterThan(0);
	expect(d.visiveis).toBeLessThan(n);
	const resultados = page.getByTestId('resultados-busca').getByRole('button');
	await expect(resultados.first()).toBeVisible();
	await resultados.first().click();
	await expect(page.getByTestId('cartao-documento')).toBeVisible();
	expect(problemas).toEqual([]);
});

test('o laço fica no link e reproduz os mesmos documentos', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	// metade direita do mapa (em NDC): esperados = documentos à direita do centro do mapa
	const xs: number[] = documentos.colunas.x;
	const centro = (Math.min(...xs) + Math.max(...xs)) / 2;
	const esperados = xs.filter((x) => x > centro).length;
	await page.evaluate(() => window.__mapaDebug!.laco!([[0, -1.2], [1.2, -1.2], [1.2, 1.2], [0, 1.2]]));
	await expect(page).toHaveURL(/laco=/);
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(esperados);
	await expect(page.getByTestId('chip-laco')).toContainText(inteiro(esperados));

	// o mesmo link, numa aba nova, mostra os mesmos documentos
	const link = page.url();
	const outra = await page.context().newPage();
	await outra.goto(link);
	const d = await esperarMapa(outra);
	expect(d.visiveis).toBe(esperados);
	await expect(outra.getByTestId('aviso-laco')).toHaveCount(0);
	await outra.close();

	await page.getByRole('button', { name: 'Tirar o laço' }).click();
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(n);
});

test('laço desenhado com o mouse depois do "L"', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.getByRole('button', { name: 'Recolher' }).click(); // o painel sai da frente
	await page.keyboard.press('l');
	await expect(page.getByTestId('botao-laco')).toHaveCount(0); // recolhido, o botão some; o modo segue ligado
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.modoLaco)).toBe(true);
	const caixa = (await page.getByTestId('canvas-mapa').boundingBox())!;
	const [cx, cy, r] = [caixa.x + caixa.width / 2, caixa.y + caixa.height / 2, caixa.height / 3];
	await page.mouse.move(cx + r, cy);
	await page.mouse.down();
	for (let k = 1; k <= 40; k += 1) {
		const a = (2 * Math.PI * k) / 40;
		await page.mouse.move(cx + r * Math.cos(a), cy + r * Math.sin(a), { steps: 2 });
		await page.waitForTimeout(20); // o laço só registra um ponto 10 ms depois do anterior (lassoMinDelay)
	}
	await page.mouse.up();
	await expect(page).toHaveURL(/laco=/);
	const visiveis = await page.evaluate(() => window.__mapaDebug!.visiveis);
	expect(visiveis).toBeGreaterThan(0);
	expect(visiveis).toBeLessThan(n);
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.modoLaco)).toBe(false); // desliga sozinho
});

test('play passa ano a ano pela linha do tempo', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const primeiro = Math.min(...documentos.colunas.ano);
	await page.getByTestId('play').click();
	await expect(page).toHaveURL(new RegExp(`anos=${primeiro}(&|$)`));
	await expect(page).toHaveURL(new RegExp(`anos=${primeiro + 1}(&|$)`), { timeout: 5000 });
	await page.getByTestId('play').click(); // pausa
	const doAno = documentos.colunas.ano.filter((a: number) => a === primeiro + 1).length;
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(doAno);
});

test('"?" abre os atalhos na Ajuda', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.keyboard.press('?');
	await expect(page).toHaveURL(/#\/ajuda$/);
	await expect(page.getByTestId('atalhos-mapa')).toContainText('liga o laço');
});
