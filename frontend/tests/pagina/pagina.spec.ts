// A abertura do site ("Céu que se forma"): o céu desenha uma estrela por artigo e forma as constelações, o
// movimento reduzido mostra o céu pronto, o idioma e o tema ficam guardados, cabe num celular, os links levam a
// páginas que existem, e o peso e o contraste ficam dentro do combinado.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { SITE } from './preparar';

const url = () => process.env.E2E_URL_PAGINA!;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const dados: any = JSON.parse(readFileSync(join(SITE, 'assets', 'pagina', 'dados.json'), 'utf8'));

/** Erros do console e respostas ≥ 400 do próprio site. Os recursos de terceiros ficam de fora: as fontes do Google e
 * a API do GitHub (o cabeçalho do Material busca as estrelas do repositório e leva 403 quando passa do limite). */
function vigiar(page: Page) {
	const problemas: string[] = [];
	page.on('console', (m) => {
		const deFora = m.text().startsWith('Failed to load resource') && !m.location().url.startsWith(url());
		if (m.type() === 'error' && !deFora) problemas.push(`console: ${m.text()}`);
	});
	page.on('pageerror', (e) => problemas.push(`exceção: ${e.message}`));
	page.on('response', (r) => {
		if (r.status() >= 400 && r.url().startsWith(url())) problemas.push(`${r.status()} ${r.url()}`);
	});
	return problemas;
}

const fase = (page: Page) => page.evaluate(() => (window as unknown as { __ceu: { fase: string } }).__ceu.fase);

test('o céu acende uma estrela por artigo e forma as constelações', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(url());
	await expect.poll(() => fase(page), { timeout: 20_000 }).toBe('formado');
	const ceu = await page.evaluate(() => (window as unknown as { __ceu: Record<string, number> }).__ceu);
	expect(ceu.pontos).toBe(dados.ceu.n);
	expect(ceu.estrelas).toBe(dados.ceu.estrelas.length);
	await expect(page.locator('.ceu__rotulo')).toHaveCount(dados.ceu.constelacoes.length);
	await expect(page.locator('.ceu__rotulo').first()).toBeVisible();
	await expect(page.locator('#ceu-ano')).toHaveText(String(dados.ceu.anos.at(-1)));
	await expect(page.getByRole('button', { name: 'Ver de novo' })).toBeVisible();
	await expect(page.locator('.historia')).toHaveCount(await page.evaluate(() => (window as unknown as { __ceu: { historias: number } }).__ceu.historias));
	await expect(page.locator('#metodo li')).toHaveCount(6);
	expect(problemas).toEqual([]);
});

test('com movimento reduzido, o céu já aparece formado', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await expect.poll(() => fase(page), { timeout: 3_000 }).toBe('formado');
	await expect(page.getByRole('button', { name: 'Ver de novo' })).toBeHidden();
	await expect(page.locator('#numeros [data-alvo]').first()).toHaveText(new Intl.NumberFormat('pt-BR').format(dados.numeros.artigos));
});

test('o idioma e o tema ficam guardados', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await page.getByRole('button', { name: 'EN', exact: true }).click();
	await expect(page.locator('#abertura-titulo')).toContainText('What does');
	await expect(page.locator('#ceu-pagina')).toHaveAttribute('lang', 'en');
	await expect(page.locator('#numeros [data-alvo]').first()).toHaveText(new Intl.NumberFormat('en-US').format(dados.numeros.artigos));
	const antes = await page.evaluate(() => document.body.getAttribute('data-md-color-scheme'));
	await page.locator('form[data-md-component="palette"] label:visible').first().click();
	await expect.poll(() => page.evaluate(() => document.body.getAttribute('data-md-color-scheme'))).not.toBe(antes);
	const depois = await page.evaluate(() => document.body.getAttribute('data-md-color-scheme'));
	await page.reload();
	await expect(page.locator('#abertura-titulo')).toContainText('What does');
	expect(await page.evaluate(() => document.body.getAttribute('data-md-color-scheme'))).toBe(depois);
	await page.getByRole('button', { name: 'PT', exact: true }).click();
	await expect(page.locator('#abertura-titulo')).toContainText('Sobre o que escreve');
});

test('num celular: sem rolagem horizontal, e os rótulos cabem no céu', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await expect.poll(() => fase(page)).toBe('formado');
	await page.evaluate(() => document.fonts.ready);
	const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
	expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
	const caixa = (await page.locator('#ceu').boundingBox())!;
	for (const rotulo of await page.locator('.ceu__rotulo').all()) {
		const r = (await rotulo.boundingBox())!;
		expect(r.x).toBeGreaterThanOrEqual(caixa.x - 1);
		expect(r.x + r.width).toBeLessThanOrEqual(caixa.x + caixa.width + 1);
	}
});

test('no celular, a gaveta do menu mostra a navegação; o link de pular tem alvo', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await page.locator('label.md-header__button[for="__drawer"]').click();
	await expect(page.locator('.md-nav--primary').getByRole('link', { name: 'Tutoriais' }).first()).toBeVisible();
	const alvo = await page.locator('a.md-skip').getAttribute('href');
	expect(alvo).toBe('#abertura');
	await expect(page.locator('#abertura')).toHaveCount(1);
});

test('os links da abertura levam a páginas do site ou às vistas da demo', async ({ page, request }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	await expect.poll(() => fase(page)).toBe('formado');
	await page.fill('#busca-campo', 'eleição');
	await expect(page.locator('#busca-resultados li').first()).toBeVisible();
	const hrefs = await page.locator('#ceu-pagina a[href]').evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).href));
	const internos = [...new Set(hrefs.filter((h) => h.startsWith(url()) && !h.includes('/demo/')).map((h) => h.split('#')[0]))];
	expect(internos.length).toBeGreaterThan(5);
	for (const h of internos) expect((await request.get(h)).status(), h).toBe(200);
	const demo = hrefs.filter((h) => h.includes('/demo/'));
	expect(demo.length).toBeGreaterThan(10);
	for (const h of demo) expect(h, h).toMatch(/\/demo\/(#\/(mapa|topicos|geografia|classificacao|validacao|redes)(\?.*)?)?$/);
});

test('a colaboração: os dois períodos, os denominadores e o gráfico com os números, em PT e EN', async ({ page }) => {
	const col = dados.historias.colaboracao;
	test.skip(!col, 'o projeto não tem redes');
	const [pt, en] = [new Intl.NumberFormat('pt-BR'), new Intl.NumberFormat('en-US')];
	const [p0, p1] = col.periodos;
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	const cartao = page.locator('.historia', { hasText: 'Mais artigos em coautoria' });
	await expect(cartao.locator('.historia__numero')).toHaveText(`${col.varios[0]}% → ${col.varios[1]}%`);
	await expect(cartao.locator('.historia__texto')).toContainText(`Em ${p0}, ${col.varios[0]}% dos artigos tinham mais de um autor; em ${p1}, ${col.varios[1]}%.`);
	await expect(cartao.locator('.historia__texto')).toContainText(`mais de uma UF foram de ${col.ufs[0]}% para ${col.ufs[1]}%`);
	await expect(cartao.locator('.historia__texto')).toContainText(`no exterior${col.exterior_difere ? ',' : ' mudaram pouco,'} de ${col.exterior[0]}% para ${col.exterior[1]}%`);
	// os denominadores, visíveis: a autoria conhecida e a afiliação localizada
	const nota = cartao.locator('.historia__nota');
	await expect(nota).toBeVisible();
	await expect(nota).toContainText(`autoria conhecida (${pt.format(col.autoria[0])} em ${p0} e ${pt.format(col.autoria[1])} em ${p1})`);
	await expect(nota).toContainText(`afiliação localizada, numa UF ou fora do Brasil (${pt.format(col.localizados[0])} e ${pt.format(col.localizados[1])})`);
	const [primeiro, ultimo] = [Math.round(col.serie_varios[0]), Math.round(col.serie_varios.at(-1))];
	await expect(cartao.locator('svg')).toHaveAttribute('aria-label', `Artigos com mais de um autor, por ano: ${primeiro}% em ${col.anos[0]} e ${ultimo}% em ${col.anos.at(-1)}. Com autores de mais de uma UF: ${Math.round(col.serie_ufs[0])}% e ${Math.round(col.serie_ufs.at(-1))}%.`);
	await expect(cartao.getByRole('link')).toHaveAttribute('href', /#\/redes\?rede=estados$/);

	await page.getByRole('button', { name: 'EN', exact: true }).click();
	const card = page.locator('.historia', { hasText: 'More co-authored articles' });
	await expect(card.locator('.historia__texto')).toContainText(`In ${p0}, ${col.varios[0]}% of articles had more than one author; in ${p1}, ${col.varios[1]}%.`);
	await expect(card.locator('.historia__texto')).toContainText(`more than one Brazilian state went from ${col.ufs[0]}% to ${col.ufs[1]}%`);
	await expect(card.locator('.historia__nota')).toContainText(`known authorship (${en.format(col.autoria[0])} in ${p0} and ${en.format(col.autoria[1])} in ${p1})`);
	await expect(card.locator('svg')).toHaveAttribute('aria-label', new RegExp(`^Articles with more than one author, per year: ${primeiro}% in ${col.anos[0]}`));
});

test('o cânone: a parte dos artigos, sem nomes nem títulos, e a ressalva da cobertura à vista, em PT e EN', async ({ page }) => {
	const can = dados.historias.canone;
	test.skip(!can, 'o projeto não tem citações');
	const [pt, en] = [new Intl.NumberFormat('pt-BR'), new Intl.NumberFormat('en-US')];
	const todas = can.degraus.at(-1);
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url());
	const cartao = page.locator('.historia', { hasText: 'O cânone que o OpenAlex vê' });
	await expect(cartao.locator('.historia__numero')).toHaveText(`${can.pct}%`);
	await expect(cartao.locator('.historia__texto')).toContainText(`${can.pct}% dos artigos citam ao menos uma das ${can.topo} obras de fora do corpus mais citadas`);
	await expect(cartao.locator('.historia__texto')).toContainText(`${todas.obras} mais citadas`);
	if (can.antes_2000 !== null) await expect(cartao.locator('.historia__texto')).toContainText(`${can.antes_2000} são de antes de 2000`);
	if (can.ingles !== null) await expect(cartao.locator('.historia__texto')).toContainText(`${can.ingles} estão em inglês`);
	// a ressalva: visível, entre o texto e o gráfico, com a cobertura e o denominador
	const ressalva = cartao.locator('.historia__ressalva');
	await expect(ressalva).toBeVisible();
	await expect(ressalva).toContainText('Ressalva: o cânone só vê obras que o OpenAlex indexa');
	await expect(ressalva).toContainText('livros e capítulos em português ficam de fora');
	await expect(ressalva).toContainText(`os ${pt.format(can.base)} artigos (de ${pt.format(can.documentos)}) com referências no OpenAlex`);
	const [caixaTexto, caixaRessalva, caixaGrafico] = await Promise.all(['.historia__texto', '.historia__ressalva', 'svg'].map((s) => cartao.locator(s).boundingBox()));
	expect(caixaTexto!.y).toBeLessThan(caixaRessalva!.y);
	expect(caixaRessalva!.y).toBeLessThan(caixaGrafico!.y);
	const degraus = can.degraus.map((d: { obras: number; pct: number }) => `${d.obras} ${d.obras === 1 ? 'obra' : 'obras'}, ${d.pct}%`).join('; ');
	await expect(cartao.locator('svg')).toHaveAttribute('aria-label', `Artigos que citam ao menos uma das obras de fora do corpus mais citadas: ${degraus}.`);
	await expect(cartao.getByRole('link', { name: 'Ver nas Redes' })).toHaveAttribute('href', /#\/redes\?rede=citacoes$/);
	// nenhuma obra nem autor pelo nome: o cartão só tem números (e o gerador não publica títulos)
	expect(JSON.stringify(can)).not.toMatch(/titulo|autores|"W\d/);

	await page.getByRole('button', { name: 'EN', exact: true }).click();
	const card = page.locator('.historia', { hasText: 'The canon OpenAlex can see' });
	await expect(card.locator('.historia__texto')).toContainText(`${can.pct}% of articles cite at least one of the ${can.topo} most cited works from outside the corpus`);
	await expect(card.locator('.historia__ressalva')).toBeVisible();
	await expect(card.locator('.historia__ressalva')).toContainText(`Caveat: the canon only sees works indexed by OpenAlex`);
	await expect(card.locator('.historia__ressalva')).toContainText(`Only the ${en.format(can.base)} articles (of ${en.format(can.documentos)}) with references in OpenAlex are counted.`);
	await expect(card.locator('svg')).toHaveAttribute('aria-label', /^Articles citing at least one of the most cited works from outside the corpus: 1 work, /);
});

test('a seção "Como citar" traz o DOI e copia o BibTeX', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await page.goto(url());
	const bibtex = await page.locator('#citar-bibtex').textContent();
	expect(bibtex).toMatch(/^@software\{/);
	expect(bibtex).toMatch(/doi +=+ \{10\.5281\/zenodo\.\d+\}/);
	await expect(page.locator('.citar__referencia a')).toHaveAttribute('href', /^https:\/\/doi\.org\/10\.5281\/zenodo\.\d+$/);
	await page.getByRole('button', { name: 'Copiar o BibTeX' }).click();
	await expect(page.locator('#citar-aviso')).toHaveText('BibTeX copiado.');
	expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(bibtex);
});

test('a abertura pesa menos de 400 KB, dados incluídos', () => {
	const pasta = join(SITE, 'assets', 'pagina');
	const total = readdirSync(pasta).reduce((s, f) => s + statSync(join(pasta, f)).size, 0);
	expect(total).toBeLessThan(400 * 1024);
});

test('o contraste dos textos passa do AA nos dois temas', async ({ page }) => {
	await page.goto(url());
	for (const tema of ['default', 'slate']) {
		const razoes = await page.evaluate((t) => {
			document.body.setAttribute('data-md-color-scheme', t);
			const estilo = getComputedStyle(document.getElementById('ceu-pagina')!);
			const cor = (v: string) => estilo.getPropertyValue(v).trim();
			const lum = (hex: string) => {
				const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
				return 0.2126 * r + 0.7152 * g + 0.0722 * b;
			};
			const razao = (a: string, b: string) => {
				const [x, y] = [lum(cor(a)), lum(cor(b))].sort((p, q) => q - p);
				return (x + 0.05) / (y + 0.05);
			};
			const fundos = ['--ceu-fundo', '--ceu-superficie'];
			const textos = ['--ceu-texto', '--ceu-suave', '--ceu-fraco', '--ceu-acento'];
			return [
				...textos.flatMap((t) => fundos.map((f) => ({ par: `${t} sobre ${f}`, r: razao(t, f) }))),
				{ par: '--ceu-sobre-acento sobre --ceu-acento', r: razao('--ceu-sobre-acento', '--ceu-acento') }
			];
		}, tema);
		for (const { par, r } of razoes) expect(r, `${tema}: ${par}`).toBeGreaterThanOrEqual(4.5);
	}
});
