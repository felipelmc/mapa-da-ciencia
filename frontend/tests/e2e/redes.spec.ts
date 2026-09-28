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
		// o lide e a nota contam as mesmas pessoas com coautor (as desenhadas), com as métricas explicadas
		await expect(page.getByTestId('lide-redes')).toContainText(`${inteiro(redes.metricas.coautoria.nos)} delas desenhadas`);
		await expect(page.getByTestId('metricas-rede')).toContainText(`${inteiro(redes.metricas.coautoria.nos)} pessoas com coautor`);
		await expect(page.getByTestId('metricas-rede')).toContainText('grupos ligados por algum caminho');
		expect(await page.getByTestId('metricas-rede').innerText()).not.toMatch(/[\p{L}\d)]\.\p{Lu}/u);
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
	// a revista pelo nome (revistas.json), e não pela sigla interna
	const titulos = ler('revistas.json').revistas.map((r: { titulo: string }) => r.titulo);
	const revista = (await page.getByTestId('revista-no').first().innerText()).split(' · ')[0];
	expect(titulos).toContain(revista);
	// o cartão diz o que é cada número dos parceiros
	await expect(page.getByTestId('cartao-no').locator('.parceiros .numero').first()).toContainText('peso');
	// Esc fecha o cartão, e o foco volta para a busca (quem usa o teclado não volta ao topo da página)
	await page.keyboard.press('Tab');
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('cartao-no')).toHaveCount(0);
	await expect(page).not.toHaveURL(/no=/);
	await expect(campo).toBeFocused();
	// o × também devolve o foco
	await campo.fill(nome.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase());
	await campo.press('Enter');
	await page.getByRole('button', { name: 'Fechar o cartão' }).click();
	await expect(campo).toBeFocused();
});

test('a vista leva à ajuda das redes, e as comunidades têm rótulo e lista', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	await expect(page.getByTestId('rotulo-comunidade').first()).toBeVisible();
	await expect(page.getByTestId('lista-comunidades').getByRole('listitem')).not.toHaveCount(0);
	await page.getByTestId('como-ler-redes').click();
	await expect(page.getByTestId('ajuda-redes')).toBeInViewport();
	await expect(page.getByTestId('glossario-redes')).toContainText('Modularidade');
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
	// a figura se lê sozinha: a legenda (cores, faixas de peso e comunidades) vai junto, o fundo é opaco e o
	// subtítulo não repete o período que o título do projeto já traz
	expect(svg).toContain('>Peso da parceria no recorte:</text>');
	expect(svg).toContain('>As maiores comunidades');
	expect(ler('topicos.json').macrotemas.some((m: { rotulo: string }) => svg.includes(`>${m.rotulo}</text>`))).toBe(true);
	expect(svg).not.toMatch(/<rect width="[\d.]+" height="[\d.]+" fill="(rgba\(0, 0, 0, 0\)|transparent)"/);
	expect(svg).not.toMatch(/(\d{4}–\d{4}) · \1/);
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
	// as UFs com as parcerias mais fortes têm a sigla escrita ao lado do ponto
	await expect(page.getByTestId('sigla-uf').first()).toBeVisible();
	// a dica de uma UF chama o exterior pelo nome (e não "EX")
	const paresUf = agregados.uf_pares as [string, string, number, number][];
	const parceirasDe = (k: string) =>
		paresUf
			.filter((p) => p[0] === k || p[1] === k)
			.sort((p, q) => q[2] - p[2])
			.map((p) => (p[0] === k ? p[1] : p[0]));
	const uf = [...new Set(paresUf.flatMap((p) => [p[0], p[1]]))].find((k) => k !== 'EX' && parceirasDe(k).slice(0, 3).includes('EX'))!;
	await page.locator(`[data-testid="uf-rede"][data-chave="${uf}"]`).focus();
	const dica = page.locator('.dica');
	await expect(dica).toContainText('Exterior (');
	await expect(dica).not.toContainText('EX (');
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
	// as frases condicionais não colam na anterior ("105.763.Nesses")
	expect(await nota.innerText()).not.toMatch(/[\p{L}\d)]\.\p{Lu}/u);
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
		m.mudancas = { redes: ['o pessoas.yaml'] };
		await rota.fulfill({ response: resposta, json: m });
	});
	await page.goto(`${url('RAIZ')}#/redes`);
	await expect(page.getByText('As redes deste projeto estão desatualizadas.')).toBeVisible();
	// o que mudou, e os arquivos como desatualizados (e não "ainda não gerado")
	await expect(page.getByTestId('redes-desatualizadas')).toContainText('Mudou o pessoas.yaml depois da última mapa redes');
	await expect(page.getByText('redes.json').locator('..')).toContainText('desatualizado');
	await expect(page.getByText('ainda não gerado')).toHaveCount(0);
	await expect(page.getByText('Este projeto ainda não tem redes.')).toHaveCount(0);
});

test('site publicado sem redes: a vista some do trilho e não dá instrução de linha de comando', async ({ page }) => {
	await page.route('**/dados/manifesto.json', async (rota) => {
		const resposta = await rota.fetch();
		const m = await resposta.json();
		m.arquivos = m.arquivos.filter((a: string) => a !== 'redes' && a !== 'citacoes');
		m.desatualizadas = ['redes'];
		await rota.fulfill({ response: resposta, json: m });
	});
	await page.goto(`${url('PUBLICADO')}#/`);
	await expect(h1(page)).toBeVisible();
	await expect(page.getByRole('navigation', { name: 'Seções' }).getByRole('link', { name: 'Redes' })).toHaveCount(0);
	await page.goto(`${url('PUBLICADO')}#/redes`);
	await expect(page.getByText('As redes não fazem parte desta publicação.')).toBeVisible();
	await expect(page.getByRole('main')).not.toContainText('mapa redes');
	await expect(page.getByRole('main')).not.toContainText('Rode');
	// a Ajuda não explica uma vista que o site não tem
	await page.goto(`${url('PUBLICADO')}#/ajuda`);
	await expect(page.getByRole('heading', { name: 'Como ler este observatório' })).toBeVisible();
	await expect(page.getByTestId('ajuda-redes')).toHaveCount(0);
	await expect(page.getByTestId('atalhos-redes')).toHaveCount(0);
});

test('um recorte fora do período não quebra as séries', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes?anos=2030-2031`);
	await expect(page.getByTestId('serie-coautoria')).toBeVisible();
	await page.waitForTimeout(300);
	expect(problemas).toEqual([]);
});

test('a Ajuda explica como ler as redes', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/ajuda`);
	const secao = page.getByTestId('ajuda-redes');
	await expect(secao.getByRole('heading', { name: 'Como ler as redes' })).toBeVisible();
	await expect(secao).toContainText('1/(n−1)');
	await expect(secao).toContainText('agrupamentos automáticos');
	await expect(secao).toContainText('favorece o que tem DOI');
});

// ---- a interação com o grafo (2.1): destaque, comunidade, arrasto, roda, teclado e tela cheia

/** Os vizinhos (no corpus inteiro) de uma pessoa, pelas autorias do exemplo. */
function vizinhosDe(p: number): Set<number> {
	const saida = new Set<number>();
	for (const pessoas of pessoasPorDoc(() => true).values()) if (pessoas.has(p)) for (const q of pessoas) if (q !== p) saida.add(q);
	return saida;
}
const estadoDoGrafo = (page: Page) => page.evaluate(() => window.__redesDebug!.estadoDoGrafo!()!);
/** `true` se todos os nós estão dentro da área do grafo (depois de enquadrar). */
async function todosNaTela(page: Page, indices: number[]) {
	const caixa = (await page.getByTestId('canvas-rede').boundingBox())!;
	for (const i of indices) {
		const [x, y] = (await naTela(page, redes.pessoas.id[i]))!;
		if (x < 0 || x > caixa.width || y < 0 || y > caixa.height) return false;
	}
	return true;
}
const naTela = (page: Page, id: string) => page.evaluate((i) => window.__redesDebug!.posicaoNaTela!(i), id);
/** A pessoa desenhada com mais coautores. */
const central = () => {
	const desenhadas = redes.pessoas.id.map((_: string, i: number) => i).filter((i: number) => redes.pessoas.x[i] !== null);
	return desenhadas.sort((a: number, b: number) => redes.pessoas.grau[b] - redes.pessoas.grau[a])[0] as number;
};

test('passar o mouse num nó acende ele e os vizinhos, e escreve o nome deles', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	expect((await estadoDoGrafo(page)).destacados).toBe(0);
	const p = central();
	const [x, y] = (await naTela(page, redes.pessoas.id[p]))!;
	await page.getByTestId('canvas-rede').hover({ position: { x, y } });
	await expect.poll(async () => (await estadoDoGrafo(page)).destacados).toBe(1 + vizinhosDe(p).size);
	const nomes = (await estadoDoGrafo(page)).nomes;
	expect(nomes.length).toBeGreaterThan(0);
	// só os nomes da vizinhança (a pessoa sob o mouse e os coautores dela)
	const daVizinhanca = [p, ...vizinhosDe(p)].map((q) => redes.pessoas.nome[q]);
	expect(nomes.filter((n: string) => !daVizinhanca.includes(n))).toEqual([]);
	// fora do nó, o destaque some
	await page.getByTestId('canvas-rede').hover({ position: { x: 2, y: 2 } });
	await expect.poll(async () => (await estadoDoGrafo(page)).destacados).toBe(0);
	expect(problemas).toEqual([]);
});

test('uma comunidade escolhida na legenda fica acesa, enquadrada e no link; "Todas" solta', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	const botao = page.getByTestId('comunidade').first();
	await botao.click();
	await expect(page).toHaveURL(/comunidade=\d+/);
	await expect(botao).toHaveAttribute('aria-pressed', 'true');
	const c = Number(new URL(page.url().replace('#/', '')).searchParams.get('comunidade'));
	const membros = redes.pessoas.id.map((_: string, i: number) => i).filter((i: number) => redes.pessoas.comunidade[i] === c && redes.pessoas.x[i] !== null);
	await expect.poll(async () => (await estadoDoGrafo(page)).destacados).toBe(membros.length);
	// enquadrada: o zoom mudou, e a comunidade inteira está na tela
	await expect.poll(async () => (await estadoDoGrafo(page)).vista.k).not.toBe(1);
	expect(await todosNaTela(page, membros)).toBe(true);
	await expect(page.getByTestId('zoom-enquadrar')).toHaveText('Enquadrar a comunidade');
	// o link reproduz a tela
	await page.reload();
	await esperarRedes(page, 'coautoria');
	await expect.poll(async () => (await estadoDoGrafo(page)).destacados).toBe(membros.length);
	await page.getByTestId('todas-comunidades').click();
	await expect(page).not.toHaveURL(/comunidade=/);
	await expect.poll(async () => (await estadoDoGrafo(page)).vista.k).toBe(1);
	// trocar de rede solta a comunidade
	await page.getByTestId('comunidade').first().click();
	await page.getByTestId('rede-instituicoes').click();
	await expect(page).not.toHaveURL(/comunidade=/);
	expect(problemas).toEqual([]);
});

test('arrastar um nó o move sem abrir o cartão; "Reiniciar" devolve o desenho; o clique abre sem rolar a página', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	const id = redes.pessoas.id[central()];
	const canvas = page.getByTestId('canvas-rede');
	await canvas.scrollIntoViewIfNeeded();
	const caixa = (await canvas.boundingBox())!;
	const [x, y] = (await naTela(page, id))!;
	await page.mouse.move(caixa.x + x, caixa.y + y);
	await page.mouse.down();
	await page.mouse.move(caixa.x + x + 60, caixa.y + y + 30, { steps: 6 });
	await page.mouse.up();
	const [x2, y2] = (await naTela(page, id))!;
	expect(Math.round(x2 - x)).toBe(60);
	expect(Math.round(y2 - y)).toBe(30);
	expect((await estadoDoGrafo(page)).movidos).toBe(1);
	await expect(page.getByTestId('cartao-no')).toHaveCount(0);
	await page.getByTestId('zoom-reiniciar').click();
	await expect.poll(async () => (await estadoDoGrafo(page)).movidos).toBe(0);
	expect(await naTela(page, id)).toEqual([x, y]);
	// o clique abre o cartão, e a página não rola até ele
	const rolagem = await page.evaluate(() => scrollY);
	await canvas.click({ position: { x, y } });
	await expect(page.getByTestId('cartao-no')).toBeVisible();
	expect(await page.evaluate(() => scrollY)).toBe(rolagem);
	await expect(page.getByTestId('zoom-enquadrar')).toHaveText('Enquadrar o nó');
	await page.getByTestId('zoom-enquadrar').click();
	await expect.poll(async () => (await estadoDoGrafo(page)).vista.k).not.toBe(1);
	expect(await todosNaTela(page, [central(), ...vizinhosDe(central())])).toBe(true);
	expect(problemas).toEqual([]);
});

test('a roda sozinha rola a página (com um aviso); Ctrl + roda e o teclado aproximam', async ({ page }) => {
	const problemas = vigiar(page);
	await page.setViewportSize({ width: 1440, height: 700 });
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	const canvas = page.getByTestId('canvas-rede');
	await canvas.scrollIntoViewIfNeeded();
	const caixa = (await canvas.boundingBox())!;
	await page.mouse.move(caixa.x + caixa.width / 2, caixa.y + 40);
	const antes = await page.evaluate(() => scrollY);
	await page.mouse.wheel(0, 200);
	await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(antes);
	await expect(page.getByTestId('aviso-roda')).toBeVisible();
	expect((await estadoDoGrafo(page)).vista.k).toBe(1);
	const caixa2 = (await canvas.boundingBox())!;
	await page.mouse.move(caixa2.x + caixa2.width / 2, caixa2.y + 40);
	await page.keyboard.down('Control');
	await page.mouse.wheel(0, -300);
	await page.keyboard.up('Control');
	await expect.poll(async () => (await estadoDoGrafo(page)).vista.k).toBeGreaterThan(1);
	// o teclado, com a área do grafo em foco: 0 volta, + aproxima
	await page.locator('[data-grafo]').focus();
	await page.keyboard.press('0');
	await expect.poll(async () => (await estadoDoGrafo(page)).vista.k).toBe(1);
	await page.keyboard.press('+');
	await expect.poll(async () => (await estadoDoGrafo(page)).vista.k).toBeGreaterThan(1);
	expect(problemas).toEqual([]);
});

test('tela cheia: o grafo ocupa a tela e volta', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/redes`);
	await esperarRedes(page, 'coautoria');
	const botao = page.getByTestId('tela-cheia');
	test.skip((await botao.count()) === 0, 'navegador sem a API de tela cheia');
	await botao.click();
	await expect(botao).toHaveAttribute('aria-pressed', 'true');
	await expect.poll(async () => (await estadoDoGrafo(page)).telaCheia).toBe(true);
	await botao.click();
	await expect(botao).toHaveAttribute('aria-pressed', 'false');
	expect(problemas).toEqual([]);
});
