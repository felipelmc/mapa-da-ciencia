// A vista do mapa (M3), sobre o build servido com o exemplo sintético.
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { esperarMapa, h1, inteiro, ler, RAIZ, trilho, url, vigiar } from './comum';

const documentos = ler('documentos.json');
const topicos = ler('topicos.json');
const n: number = documentos.n;

// palavras de 5 letras ou mais dos títulos, da presente em mais títulos à mais rara (para as buscas)
const palavrasDe = (titulo: string) => titulo.toLowerCase().split(/[^\p{L}]+/u).filter((p) => p.length >= 5);
const frequencia = new Map<string, number>();
for (const t of documentos.colunas.titulo as string[]) {
	for (const p of new Set(palavrasDe(t))) frequencia.set(p, (frequencia.get(p) ?? 0) + 1);
}
const porFrequencia = [...frequencia.keys()].sort((a, b) => frequencia.get(b)! - frequencia.get(a)!);

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`desenha os documentos do exemplo (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/mapa`);
		await expect(h1(page)).toHaveText('Mapa');
		const d = await esperarMapa(page);
		expect(d.erro).toBeNull();
		expect(d.pontos).toBe(n);
		expect(d.visiveis).toBe(n);
		await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(n));
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

test('a legenda filtra por tópico, e "Limpar recorte" volta ao todo', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const primeiro = topicos.topicos[0];
	await page.getByTestId('legenda-mapa').getByRole('button', { name: primeiro.rotulo }).click();
	await expect(page).toHaveURL(new RegExp(`topicos=${primeiro.id}(&|$)`));
	const doTopico = documentos.colunas.topico.filter((t: number) => t === primeiro.id).length;
	await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(doTopico));
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBe(doTopico);

	await page.getByRole('button', { name: 'Limpar recorte' }).click();
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

test('o mapa acompanha a janela, o modo apresentação e o painel recolhido', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	// diferença, em pixels, entre o canvas e a área do mapa (a `.tela`, pai do canvas)
	const folga = () =>
		page.evaluate(() => {
			const c = document.querySelector<HTMLCanvasElement>('[data-testid=canvas-mapa]')!;
			const p = c.parentElement!;
			return Math.max(Math.abs(c.clientWidth - p.clientWidth), Math.abs(c.clientHeight - p.clientHeight));
		});
	expect(await folga()).toBeLessThanOrEqual(1);
	await page.setViewportSize({ width: 1100, height: 700 });
	await expect.poll(folga, { message: 'janela menor' }).toBeLessThanOrEqual(1);
	await page.setViewportSize({ width: 1920, height: 1080 });
	await expect.poll(folga, { message: 'janela maior' }).toBeLessThanOrEqual(1);
	await page.keyboard.press('p');
	await expect(page.getByTestId('modo-apresentacao')).toBeVisible();
	await expect.poll(folga, { message: 'modo apresentação' }).toBeLessThanOrEqual(1);
	await page.keyboard.press('Escape');
	await page.getByRole('button', { name: 'Recolher' }).click();
	await expect.poll(folga, { message: 'painel recolhido' }).toBeLessThanOrEqual(1);
	expect(problemas).toEqual([]);
});

// ---- cartão do documento

type Detalhe = {
	resumo: string | null;
	fonte_analise?: string;
	licenca: string;
	evidencias?: Record<string, { status: string }>;
};
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

test('o cartão marca no resumo as evidências da classificação', async ({ page }) => {
	const problemas = vigiar(page);
	const id = ids.find((i) => detalhes[i].resumo && Object.keys(detalhes[i].evidencias ?? {}).length)!;
	const evidencias = detalhes[id].evidencias!;
	await page.goto(`${url('RAIZ')}#/mapa?doc=${encodeURIComponent(id)}`);
	await esperarMapa(page);
	const cartao = page.getByTestId('cartao-documento');
	await expect(cartao.getByTestId('resposta')).toHaveCount(Object.keys(evidencias).length);
	const marcadas = cartao.getByTestId('resumo-marcado').locator('mark');
	await expect(marcadas.first()).toBeVisible();
	// o resumo continua inteiro, com os trechos marcados dentro dele
	await expect(cartao.getByTestId('resumo-marcado')).toHaveText(detalhes[id].resumo!);
	// passar o mouse numa resposta acende o trecho dela
	const [variavel] = Object.entries(evidencias).find(([, e]) => e.status === 'literal')!;
	const indice = Object.keys(evidencias).indexOf(variavel);
	await cartao.getByTestId('resposta').nth(indice).hover();
	await expect(cartao.locator(`mark.acesa[data-variaveis~="${variavel}"]`).first()).toBeVisible();
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

test('o link de uma busca com "&" reabre a mesma busca', async ({ page }) => {
	// duas palavras do mesmo título: a mais comum do corpus e uma rara, para "a & b" achar menos que "a"
	const comum = porFrequencia[0];
	const rara = palavrasDe((documentos.colunas.titulo as string[]).find((t) => palavrasDe(t).includes(comum))!)
		.filter((p) => p !== comum)
		.sort((a, b) => frequencia.get(a)! - frequencia.get(b)!)[0];
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.getByTestId('busca-mapa').fill(`${comum} & ${rara}`);
	await expect(page).toHaveURL(/busca=/);
	const contador = page.getByTestId('contador-recorte');
	await expect.poll(() => page.evaluate(() => window.__mapaDebug?.visiveis)).toBeLessThan(n);
	const visiveis = await page.evaluate(() => window.__mapaDebug!.visiveis);
	await expect(contador).toContainText(inteiro(visiveis));

	// o link, aberto numa aba nova (a carga do SvelteKit decodifica o hash), mostra a mesma busca
	const outra = await page.context().newPage();
	await outra.goto(page.url());
	const d = await esperarMapa(outra);
	expect(d.visiveis).toBe(visiveis);
	await expect(outra.getByTestId('busca-mapa')).toHaveValue(`${comum} ${rara}`);
	await outra.close();
});

test('fechar o cartão devolve o foco ao resultado da busca que o abriu', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.getByTestId('busca-mapa').fill(documentos.colunas.titulo[0].split(' ')[0]);
	const resultado = page.getByTestId('resultados-busca').getByRole('button').first();
	const cartao = page.getByTestId('cartao-documento');
	for (const fechar of ['Escape', 'botão']) {
		await resultado.focus();
		await page.keyboard.press('Enter');
		await expect(cartao).toBeVisible();
		if (fechar === 'botão') await cartao.getByRole('button', { name: 'Fechar o cartão' }).focus();
		await page.keyboard.press(fechar === 'botão' ? 'Enter' : 'Escape');
		await expect(cartao).toHaveCount(0);
		await expect(resultado).toBeFocused();
	}
});

test('a lista da busca aparece inteira ao lado da legenda, e diz quantos resultados ficaram de fora', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const campo = page.getByTestId('busca-mapa');
	const lista = page.getByTestId('resultados-busca');
	// a lista mostra tudo o que tem, até o próprio limite (9rem, com rolagem)
	const inteira = () => lista.evaluate((e) => e.clientHeight >= Math.min(e.scrollHeight, 144) - 1);
	await campo.fill('xyzxyz');
	await expect(lista).toContainText('Nada encontrado.');
	await expect.poll(inteira).toBe(true);
	// a palavra presente em mais títulos: dá mais de 6 resultados
	await campo.fill(porFrequencia[0]);
	await expect(lista.getByRole('button')).toHaveCount(6);
	await expect(page.getByTestId('mais-resultados')).toContainText(/^6 de [\d.]+; refine a busca/);
	await expect.poll(inteira).toBe(true);
});

test.describe('no celular', () => {
	test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });

	test('o painel e o cartão terminam acima da barra de navegação, e a legenda inteira é alcançável', async ({ page }) => {
		await page.goto(`${url('RAIZ')}#/mapa`);
		await esperarMapa(page);
		const topoDaBarra = (await page.locator('aside.lateral').boundingBox())!.y;
		const fim = async (seletor: string) => {
			const caixa = (await page.locator(seletor).boundingBox())!;
			return caixa.y + caixa.height;
		};
		expect(await fim('aside.painel')).toBeLessThanOrEqual(topoDaBarra + 0.5);
		// o último item da legenda (que antes ficava atrás da barra) recebe o toque
		await page.getByTestId('legenda-mapa').getByRole('button').last().click({ timeout: 5000 });
		await expect(page).toHaveURL(/topicos=/);

		await page.goto(`${url('RAIZ')}#/mapa?doc=${encodeURIComponent(ids[0])}`);
		await esperarMapa(page);
		await expect(page.getByTestId('cartao-documento')).toBeVisible();
		expect(await fim('.lado')).toBeLessThanOrEqual(topoDaBarra + 0.5);
	});
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

test('o laço só ganha o aviso de versão anterior quando o mapa muda, e não a cada reexportação', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.evaluate(() => window.__mapaDebug!.laco!([[0, -1.2], [1.2, -1.2], [1.2, 1.2], [0, 1.2]]));
	await expect(page).toHaveURL(/laco=/);
	const link = page.url();
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	type Json = any;
	const abrir = async (trocar: { arquivo: string; mudar: (json: Json) => Json }) => {
		const outra = await page.context().newPage();
		await outra.route(`**/dados/${trocar.arquivo}`, async (r) => {
			const resposta = await r.fetch();
			await r.fulfill({ response: resposta, json: trocar.mudar(await resposta.json()) });
		});
		await outra.goto(link);
		await esperarMapa(outra);
		await expect(outra.getByTestId('chip-laco')).toBeVisible();
		return outra;
	};
	// reexportado (classificar, geografia, publicar): só o gerado_em do manifesto muda
	const reexportado = await abrir({ arquivo: 'manifesto.json', mudar: (m) => ({ ...m, gerado_em: '2030-01-01T00:00:00+00:00' }) });
	await expect(reexportado.getByTestId('aviso-laco')).toHaveCount(0);
	await reexportado.close();
	// tópicos refeitos: outras coordenadas
	const refeito = await abrir({
		arquivo: 'documentos.json',
		mudar: (d) => ({ ...d, colunas: { ...d.colunas, x: d.colunas.x.map((v: number, i: number) => (i === 0 ? v + 0.5 : v)) } })
	});
	await expect(refeito.getByTestId('aviso-laco')).toBeVisible();
	await refeito.close();
});

test('o chip do laço conta o laço, e não o recorte inteiro', async ({ page }) => {
	const xs: number[] = documentos.colunas.x;
	const centro = (Math.min(...xs) + Math.max(...xs)) / 2;
	const noLaco = xs.filter((x) => x > centro).length;
	const c = documentos.colunas;
	const revista = documentos.dicionarios.revista[0];
	const noRecorte = xs.filter((x, i) => x > centro && c.ano[i] >= 2012 && c.ano[i] <= 2018 && c.revista[i] === 0).length;
	await page.goto(`${url('RAIZ')}#/mapa?anos=2012-2018&revistas=${revista}`);
	await esperarMapa(page);
	await page.evaluate(() => window.__mapaDebug!.laco!([[0, -1.2], [1.2, -1.2], [1.2, 1.2], [0, 1.2]]));
	await expect(page).toHaveURL(/laco=/);
	await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(noRecorte));
	await expect(page.getByTestId('chip-laco')).toContainText(`Laço: ${inteiro(noLaco)} documentos`);
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

test('um gesto na linha do tempo cria uma entrada só no histórico', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const antes = await page.evaluate(() => history.length);
	await page.getByLabel('Primeiro ano').focus();
	for (let i = 0; i < 5; i += 1) await page.keyboard.press('ArrowRight');
	const primeiro = Math.min(...documentos.colunas.ano);
	await expect(page).toHaveURL(new RegExp(`anos=${primeiro + 5}-`));
	expect(await page.evaluate(() => history.length)).toBe(antes + 1);
	// Voltar desfaz o gesto inteiro
	await page.goBack();
	await expect(page).toHaveURL(/#\/mapa$/);
});

test('Voltar leva o campo de busca junto com a URL', async ({ page }) => {
	const [a, b] = porFrequencia;
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	const campo = page.getByTestId('busca-mapa');
	await campo.fill(a);
	await expect(page).toHaveURL(new RegExp(`busca=${a}`));
	await page.getByLabel('Primeiro ano').focus();
	await page.keyboard.press('ArrowRight'); // uma entrada nova no histórico
	await expect(page).toHaveURL(/anos=/);
	await campo.fill(b);
	await expect(page).toHaveURL(new RegExp(`busca=${b}`));
	await page.goBack();
	await expect(page).toHaveURL(new RegExp(`busca=${a}$`));
	await expect(campo).toHaveValue(a);
	await expect(page.getByTestId('barra-recorte').getByText(`Busca: “${a}”`)).toBeVisible();
});

test('"?" abre os atalhos na Ajuda', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa`);
	await esperarMapa(page);
	await page.keyboard.press('?');
	await expect(page).toHaveURL(/#\/ajuda$/);
	await expect(page.getByTestId('atalhos-mapa')).toContainText('liga o laço');
});
