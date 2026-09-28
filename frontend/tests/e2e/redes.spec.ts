// A vista Redes, sobre o build servido com o exemplo sintético. O desenho vem do `__redesDebug`; os números esperados
// são contados aqui, direto dos JSON do exemplo, sem passar pelo código da vista.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { h1, inteiro, ler, TELAS, url, vigiar } from './comum';

const redes = ler('redes.json');
const agregados = ler('agregados.json');
const documentos = ler('documentos.json');
const afiliacoes = ler('afiliacoes.json');
const anoDoDoc: number[] = documentos.colunas.ano;

/** Espera o modo desenhar e devolve o estado de depuração (sem a função, que não atravessa o `evaluate`). */
async function esperarRedes(page: Page, modo: string) {
	await page.waitForFunction((m) => window.__redesDebug?.modo === m && window.__redesDebug.desenhado, modo, {
		timeout: 15_000
	});
	return page.evaluate(() => ({ ...window.__redesDebug!, posicaoNaTela: undefined }));
}

/** Pessoas de cada documento cujo ano passa no filtro. */
function pessoasPorDoc(passa: (d: number) => boolean): Map<number, Set<number>> {
	const saida = new Map<number, Set<number>>();
	redes.autorias.doc.forEach((d: number, k: number) => {
		if (!passa(d)) return;
		if (!saida.has(d)) saida.set(d, new Set());
		saida.get(d)!.add(redes.autorias.pessoa[k]);
	});
	return saida;
}

/** Pares distintos de coautores nos documentos que passam. */
function pares(passa: (d: number) => boolean): number {
	const vistos = new Set<string>();
	for (const pessoas of pessoasPorDoc(passa).values()) {
		const lista = [...pessoas].sort((a, b) => a - b);
		for (let i = 0; i < lista.length; i += 1) for (let j = i + 1; j < lista.length; j += 1) vistos.add(`${lista[i]}-${lista[j]}`);
	}
	return vistos.size;
}

const comPosicao = redes.pessoas.x.filter((x: number | null) => x !== null).length;

/** Pares distintos de lugares (UFs e `EX`) nos documentos que passam, pela regra do Python. */
function paresDeLugares(passa: (d: number) => boolean): number {
	const c = afiliacoes.colunas;
	const { uf, pais } = afiliacoes.dicionarios;
	const porDoc = new Map<number, Set<string>>();
	c.doc.forEach((d: number, k: number) => {
		if (!passa(d) || c.pais[k] < 0) return;
		const lugar = pais[c.pais[k]] === 'BR' ? (c.uf[k] >= 0 ? uf[c.uf[k]] : null) : 'EX';
		if (!lugar) return;
		if (!porDoc.has(d)) porDoc.set(d, new Set());
		porDoc.get(d)!.add(lugar);
	});
	const vistos = new Set<string>();
	for (const lugares of porDoc.values()) {
		const lista = [...lugares].sort();
		for (let i = 0; i < lista.length; i += 1) for (let j = i + 1; j < lista.length; j += 1) vistos.add(`${lista[i]}|${lista[j]}`);
	}
	return vistos.size;
}

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test(`coautoria e instituições desenham pela URL (${site === 'RAIZ' ? 'raiz' : 'subcaminho'})`, async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/redes`);
		await expect(h1(page)).toHaveText('Redes');
		const d = await esperarRedes(page, 'coautoria');
		expect(d.nos).toBe(comPosicao);
		expect(d.arestas).toBe(agregados.arestas_coautoria);
		expect(d.arestasNoRecorte).toBe(agregados.arestas_coautoria);
		expect(d.msAtePrimeiroDesenho).toBeLessThan(5000);
		await expect(page.getByTestId('rede-coautoria')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('lide-redes')).toContainText(`${inteiro(agregados.arestas_coautoria)} pares de coautores`);
		await expect(page.getByTestId('metricas-rede')).toContainText(`${inteiro(redes.metricas.coautoria.arestas)} pares`);
		await expect(page.getByTestId('rotulo-comunidade').first()).toBeVisible();

		await page.getByTestId('rede-instituicoes').click();
		await expect(page).toHaveURL(/rede=instituicoes/);
		const i = await esperarRedes(page, 'instituicoes');
		expect(i.nos).toBe(redes.instituicoes.id.length);
		expect(i.arestas).toBe(redes.metricas.instituicoes.arestas);
		if (site === 'RAIZ') await page.screenshot({ path: join(TELAS, 'redes-instituicoes-1440x900.png'), fullPage: true });
		expect(problemas).toEqual([]);
	});
}

test('um filtro de anos reduz as arestas no recorte como a contagem prevê, sem mexer no desenho', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/redes?anos=2015-2018`);
	const d = await esperarRedes(page, 'coautoria');
	const esperadas = pares((doc) => anoDoDoc[doc] >= 2015 && anoDoDoc[doc] <= 2018);
	expect(esperadas).toBeLessThan(agregados.arestas_coautoria);
	expect(d.arestasNoRecorte).toBe(esperadas);
	expect(d.arestas).toBe(agregados.arestas_coautoria);
	expect(d.nos).toBe(comPosicao);
	// outro período, outro número
	await page.goto(`${url('RAIZ')}#/redes?anos=2020-2020`);
	await esperarRedes(page, 'coautoria');
	await expect
		.poll(() => page.evaluate(() => window.__redesDebug?.arestasNoRecorte))
		.toBe(pares((doc) => anoDoDoc[doc] === 2020));
});

test('clicar num nó abre o cartão com os documentos da pessoa no recorte', async ({ page }) => {
	const problemas = vigiar(page);
	const [de, ate] = [2015, 2018];
	await page.goto(`${url('RAIZ')}#/redes?anos=${de}-${ate}`);
	await esperarRedes(page, 'coautoria');
	// a pessoa com mais documentos no período
	const porPessoa = new Map<number, Set<number>>();
	for (const [doc, pessoas] of pessoasPorDoc((d) => anoDoDoc[d] >= de && anoDoDoc[d] <= ate)) {
		for (const p of pessoas) porPessoa.set(p, (porPessoa.get(p) ?? new Set()).add(doc));
	}
	const [p, docs] = [...porPessoa.entries()].filter(([q]) => redes.pessoas.x[q] !== null).sort((a, b) => b[1].size - a[1].size)[0];
	const id = redes.pessoas.id[p];
	const posicao = await page.evaluate((i) => window.__redesDebug!.posicaoNaTela!(i), id);
	expect(posicao).toBeDefined();
	await page.getByTestId('canvas-rede').click({ position: { x: posicao![0], y: posicao![1] } });
	await expect(page).toHaveURL(new RegExp(`no=${id}`));
	const cartao = page.getByTestId('cartao-no');
	await expect(cartao.getByRole('heading', { level: 2 })).toHaveText(redes.pessoas.nome[p]);
	await expect(cartao.getByTestId('numeros-no')).toContainText(`${inteiro(docs.size)} no recorte`);
	const itens = cartao.getByTestId('documentos-no').getByRole('listitem');
	await expect(itens).toHaveCount(Math.min(12, docs.size));
	if (docs.size > 12) {
		await cartao.getByRole('button', { name: `Mostrar todos (${docs.size})` }).click();
		await expect(itens).toHaveCount(docs.size);
	}
	// cada documento leva ao Mapa com o recorte
	await expect(itens.first().getByRole('link')).toHaveAttribute('href', new RegExp(`^#/mapa\\?anos=${de}-${ate}&doc=`));
	expect(await page.evaluate(() => window.__redesDebug?.selecionado)).toBe(id);
	// um coautor abre o próprio cartão; o × fecha
	await cartao.getByRole('listitem').first().getByRole('button').click();
	await expect(page).not.toHaveURL(new RegExp(`no=${id}(&|$)`));
	await cartao.getByRole('button', { name: 'Fechar o cartão' }).click();
	await expect(page).not.toHaveURL(/no=/);
	await expect(cartao).toHaveCount(0);
	expect(problemas).toEqual([]);
});

test('a busca pelo teclado abre o cartão de uma pessoa', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	const nome: string = redes.pessoas.nome[7];
	const campo = page.getByRole('combobox', { name: 'Buscar uma pessoa' });
	await campo.fill(nome.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase()); // sem acentos
	await expect(campo).toHaveAttribute('aria-expanded', 'true');
	await expect(page.getByRole('option').first()).toContainText(nome);
	await campo.press('Enter');
	await expect(page).toHaveURL(new RegExp(`no=${redes.pessoas.id[7]}`));
	await expect(page.getByTestId('cartao-no').getByRole('heading', { level: 2 })).toHaveText(nome);
	await expect(page.getByTestId('cartao-no').getByRole('heading', { level: 2 })).toBeFocused();
	await expect(campo).toHaveAttribute('aria-expanded', 'false');
	// Esc fecha o cartão
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('cartao-no')).toHaveCount(0);
	await expect(page).not.toHaveURL(/no=/);
});

test('instituições: o cartão põe a instituição no recorte', async ({ page }) => {
	const problemas = vigiar(page);
	const id: string = redes.instituicoes.id[0];
	const inst = afiliacoes.dicionarios.instituicao.find((i: { id: string }) => i.id === id);
	await page.goto(`${url('RAIZ')}#/redes?rede=instituicoes&no=${encodeURIComponent(id)}`);
	const antes = await esperarRedes(page, 'instituicoes');
	const cartao = page.getByTestId('cartao-no');
	await expect(cartao.getByRole('heading', { level: 2 })).toContainText(inst.nome);
	await cartao.getByTestId('filtrar-instituicao').click();
	await expect(page).toHaveURL(new RegExp(`inst=${encodeURIComponent(id)}`));
	await expect(page.getByTestId('barra-recorte')).toContainText(inst.sigla ?? inst.nome);
	await expect(cartao.getByTestId('filtrar-instituicao')).toHaveAttribute('aria-pressed', 'true');
	await expect.poll(() => page.evaluate(() => window.__redesDebug?.arestasNoRecorte)).toBeLessThan(antes.arestasNoRecorte);
	expect(problemas).toEqual([]);
});

test('ver como tabela: um nó por linha e a colaboração ano a ano', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	await page.getByTestId('figura-grafo').getByRole('button', { name: 'Ver como tabela' }).click();
	const comDocs = redes.pessoas.documentos.filter((n: number) => n > 0).length;
	await expect(page.getByTestId('tabela-grafo').locator('tbody tr')).toHaveCount(comDocs);
	await page.getByTestId('figura-colaboracao').getByRole('button', { name: 'Ver como tabela' }).click();
	await expect(page.getByTestId('tabela-colaboracao').locator('tbody tr')).toHaveCount(ler('topicos.json').anos.length);
});

test('exportar o grafo: o canvas vira imagem embaixo dos rótulos, no tema do preset', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	const figura = page.getByTestId('figura-grafo');
	const baixar = async (formato: 'SVG' | 'PNG', preset: string) => {
		await figura.getByTestId('abrir-exportar').click();
		await figura.getByLabel(formato).check();
		await figura.getByTestId('preset-exportar').selectOption(preset);
		const esperar = page.waitForEvent('download', { timeout: 15_000 });
		await figura.getByTestId('baixar-figura').click();
		return readFileSync((await (await esperar).path())!);
	};
	const svg = (await baixar('SVG', 'artigo-2')).toString('utf8');
	expect(svg).toContain('>Quem escreve com quem</text>');
	expect(svg).toMatch(/<image href="data:image\/png;base64,[A-Za-z0-9+/]{1000}/);
	expect(svg).not.toContain('var(--');
	const png = await baixar('PNG', 'slide');
	expect(png.readUInt32BE(16)).toBe(1920);
	writeFileSync(join(TELAS, 'exportado-rede-slide.png'), png);
	expect(problemas).toEqual([]);
});

test('estados: os arcos são os pares do gabarito, e clicar numa UF põe no recorte', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes?rede=estados`);
	const d = await esperarRedes(page, 'estados');
	expect(d.arestas).toBe(agregados.uf_pares.length);
	expect(d.arestasNoRecorte).toBe(agregados.uf_pares.length);
	await expect(page.getByTestId('figura-estados')).toHaveAttribute('data-pronto', 'sim');
	const arcos = page.getByTestId('arco');
	await expect(arcos).toHaveCount(agregados.uf_pares.length);
	// o arco mais grosso é a parceria de maior peso do gabarito, com o mesmo peso
	const [a, b, peso] = [...agregados.uf_pares].sort((p: number[], q: number[]) => q[2] - p[2])[0];
	const pares = await arcos.evaluateAll((els) => els.map((e) => [e.getAttribute('data-par'), Number(e.getAttribute('data-peso'))] as const));
	const maior = pares.sort((p, q) => q[1] - p[1])[0];
	expect(maior[0]!.split('|').sort()).toEqual([a, b].sort());
	expect(maior[1]).toBeCloseTo(peso, 5);
	await page.getByTestId('figura-estados').getByRole('button', { name: 'Ver como tabela' }).click();
	await expect(page.getByTestId('tabela-estados').locator('tbody tr')).toHaveCount(agregados.uf_pares.length);

	await page.locator('[data-testid="uf-rede"][data-chave="SP"]').click();
	await expect(page).toHaveURL(/uf=SP/);
	const iSp = afiliacoes.dicionarios.uf.indexOf('SP');
	const docsSp = new Set(afiliacoes.colunas.doc.filter((_: number, k: number) => afiliacoes.colunas.uf[k] === iSp));
	await expect
		.poll(() => page.evaluate(() => window.__redesDebug?.arestasNoRecorte))
		.toBe(paresDeLugares((doc) => docsSp.has(doc)));
	await expect(page.locator('[data-testid="uf-rede"][data-chave="SP"]')).toHaveAttribute('aria-pressed', 'true');
	// as outras UFs continuam botões, para somar ao recorte
	await expect(page.locator('[data-testid="uf-rede"][data-chave="RJ"]')).toHaveAttribute('aria-pressed', 'false');
	expect(problemas).toEqual([]);
});

test('citações: o cânone do gabarito, a nota da cobertura e a matriz entre macrotemas', async ({ page }) => {
	const problemas = vigiar(page);
	const citacoes = ler('citacoes.json');
	await page.goto(`${url('RAIZ')}#/redes?rede=citacoes`);
	const d = await esperarRedes(page, 'citacoes');
	expect(d.nos).toBe(citacoes.canone.length);
	expect(d.arestas).toBe(citacoes.internas.de.length);
	expect(d.arestasNoRecorte).toBe(citacoes.internas.de.length);
	const obras = page.getByTestId('obra');
	await expect(obras).toHaveCount(Math.min(30, agregados.canone_n.length));
	const ns = await obras.evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-n'))));
	expect(ns).toEqual([...agregados.canone_n].sort((x: number, y: number) => y - x).slice(0, 30));
	const nota = page.getByTestId('nota-cobertura');
	await expect(nota).toContainText('sem DOI');
	await expect(nota).toContainText(inteiro(citacoes.cobertura.com_referencias));
	// a cobertura por referência e o aviso das resenhas (o exemplo tem uma obra que chega por uma resenha)
	await expect(nota).toContainText(`das ${inteiro(citacoes.cobertura.referencias_listadas)} referências que a ArticleMeta lista`);
	expect(citacoes.canone.some((o: { resenha: boolean }) => o.resenha)).toBe(true);
	await expect(nota).toContainText('registro de uma resenha');
	// a matriz é a do Python
	const celulas = await page.getByTestId('celula-fluxo').evaluateAll((els) =>
		els.map((e) => [Number(e.getAttribute('data-de')), Number(e.getAttribute('data-para')), Number(e.getAttribute('data-n'))])
	);
	expect(celulas).toHaveLength(citacoes.fluxo_macrotemas.length ** 2);
	for (const [i, j, n] of celulas) expect(n).toBe(citacoes.fluxo_macrotemas[i][j]);
	// as linhas são os macrotemas, na ordem de topicos.json (os ids não são contíguos: nada de "Macrotema 3")
	const rotulos = await page.getByTestId('linha-fluxo').evaluateAll((els) => els.map((e) => e.getAttribute('data-rotulo')));
	expect(rotulos).toEqual(ler('topicos.json').macrotemas.map((m: { rotulo: string }) => m.rotulo));
	// com um período, só as citações com as duas pontas nele
	await page.goto(`${url('RAIZ')}#/redes?rede=citacoes&anos=2018-2025`);
	await esperarRedes(page, 'citacoes');
	const dentro = (doc: number) => anoDoDoc[doc] >= 2018 && anoDoDoc[doc] <= 2025;
	const esperadas = citacoes.internas.de.filter((de: number, k: number) => dentro(de) && dentro(citacoes.internas.para[k])).length;
	await expect.poll(() => page.evaluate(() => window.__redesDebug?.arestasNoRecorte)).toBe(esperadas);
	await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
	await page.screenshot({ path: join(TELAS, 'redes-citacoes-prancha-1440x900.png'), fullPage: true });
	expect(problemas).toEqual([]);
});

test('o site publicado também abre as redes', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('PUBLICADO')}#/redes`);
	await expect(h1(page)).toHaveText('Redes');
	const d = await esperarRedes(page, 'coautoria');
	expect(d.nos).toBeGreaterThan(0);
	await page.getByTestId('rede-citacoes').click();
	await esperarRedes(page, 'citacoes');
	await expect(page.getByTestId('obra').first()).toBeVisible();
	expect(problemas).toEqual([]);
});

test('celular (375 px): sem rolagem horizontal em nenhuma rede', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	for (const [rota, modo] of [
		['#/redes?no=p0001', 'coautoria'],
		['#/redes?rede=instituicoes', 'instituicoes'],
		['#/redes?rede=estados', 'estados'],
		['#/redes?rede=citacoes', 'citacoes']
	]) {
		await page.goto(`${url('RAIZ')}${rota}`);
		await esperarRedes(page, modo);
		expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
	}
	await page.screenshot({ path: join(TELAS, 'redes-375x812.png'), fullPage: true });
});

test('movimento reduzido: nada anima, nem ao aproximar ou abrir um nó', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	// com o movimento reduzido, as transições da casca duram 0,01 ms: conta só o que duraria mais que 1 ms
	const animando = () =>
		page.evaluate(
			() =>
				document
					.getAnimations()
					.filter((a) => a.playState === 'running' && Number(a.effect?.getComputedTiming().duration ?? 0) > 1).length
		);
	await expect.poll(animando).toBe(0);
	await page.getByTestId('zoom-mais').click();
	await page.getByRole('combobox').fill(redes.pessoas.nome[3]);
	await page.getByRole('combobox').press('Enter');
	await expect(page.getByTestId('cartao-no')).toBeVisible();
	expect(await animando()).toBe(0);
});

test('projeto vazio: estado vazio, sem pedir arquivos ausentes', async ({ page }) => {
	const pedidos: string[] = [];
	page.on('request', (r) => pedidos.push(new URL(r.url()).pathname));
	await page.goto(`${url('VAZIO')}#/redes`);
	await expect(page.getByText('Este projeto ainda não tem redes.')).toBeVisible();
	await expect(page.locator('code', { hasText: 'mapa redes' }).first()).toBeVisible();
	expect(pedidos.filter((p) => p.endsWith('.json') && !p.endsWith('manifesto.json'))).toEqual([]);
});

test('redes desatualizadas: a vista diz o que rodar, em vez de "sem redes"', async ({ page }) => {
	// o manifesto de um projeto cujas entradas mudaram depois da última `mapa redes`
	await page.route('**/dados/manifesto.json', async (rota) => {
		const resposta = await rota.fetch();
		const m = await resposta.json();
		m.arquivos = m.arquivos.filter((a: string) => a !== 'redes' && a !== 'citacoes');
		m.desatualizadas = ['redes'];
		await rota.fulfill({ response: resposta, json: m });
	});
	await page.goto(`${url('RAIZ')}#/redes`);
	await expect(page.getByText('As redes deste projeto estão desatualizadas.')).toBeVisible();
	await expect(page.getByTestId('redes-desatualizadas')).toContainText('mapa redes');
	await expect(page.getByText('Este projeto ainda não tem redes.')).toHaveCount(0);
});

test('a Ajuda explica como ler as redes', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/ajuda`);
	const secao = page.getByTestId('ajuda-redes');
	await expect(secao.getByRole('heading', { name: 'Como ler as redes' })).toBeVisible();
	await expect(secao).toContainText('1/(n−1)');
	await expect(secao).toContainText('agrupamentos automáticos');
	await expect(secao).toContainText('favorece o que tem DOI');
});
