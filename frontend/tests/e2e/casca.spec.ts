// Testes e2e da casca (M1), sobre o build servido por um estático sem reescrita.
// Os sites e as URLs vêm de tests/e2e/preparar.ts.
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { escapar, esperarMapa, h1, inteiro, ler, TELAS, trilho, url, vigiar } from './comum';

declare global {
	interface Window {
		/** Marca posta na janela; se sumir, houve recarga completa em vez de navegação no cliente. */
		__semRecarga?: boolean;
	}
}

const manifesto = ler('manifesto.json');
const topicos = ler('topicos.json');
const revistas = ler('revistas.json');
const tabelaDocumentos = ler('documentos.json');

/** Seções ativas do trilho, na ordem, com o h1 esperado em cada uma. */
const SECOES = [
	{ rotulo: 'Mapa', caminho: '/mapa', h1: 'Mapa' },
	{ rotulo: 'Tópicos', caminho: '/topicos', h1: 'Tópicos' },
	{ rotulo: 'Classificação', caminho: '/classificacao', h1: 'Classificação' },
	{ rotulo: 'Geografia', caminho: '/geografia', h1: 'Geografia' },
	{ rotulo: 'Validação', caminho: '/validacao', h1: 'Validação' },
	{ rotulo: 'Redes', caminho: '/redes', h1: 'Redes' },
	{ rotulo: 'Metodologia', caminho: '/projeto', h1: 'Metodologia' },
	{ rotulo: 'Início', caminho: '/', h1: manifesto.projeto.titulo }
];


for (const site of ['RAIZ', 'SUBCAMINHO'] as const) {
	test.describe(`servido ${site === 'RAIZ' ? 'na raiz' : 'num subcaminho'}`, () => {
		test('navega por todas as seções pelo trilho, sem 404 nem erro no console', async ({ page }) => {
			const problemas = vigiar(page);
			const base = url(site);
			await page.goto(base);
			await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
			await page.evaluate(() => (window.__semRecarga = true));

			for (const s of SECOES) {
				const link = trilho(page).getByRole('link', { name: s.rotulo, exact: true });
				await link.click();
				await expect(page).toHaveURL(new RegExp(`^${escapar(base)}#${escapar(s.caminho)}$`));
				await expect(h1(page)).toHaveText(s.h1);
				await expect(link).toHaveAttribute('aria-current', 'page');
			}
			// Tudo no cliente: nenhuma recarga completa (o problema do resolve() no ADR 0002).
			expect(await page.evaluate(() => window.__semRecarga)).toBe(true);

			// nenhuma seção desativada com selo; fora do painel, Projeto vira Metodologia.
			await expect(trilho(page).getByText('v2', { exact: true })).toHaveCount(0);
			await expect(trilho(page).getByRole('link', { name: 'Projeto' })).toHaveCount(0);

			await page.getByRole('banner').getByRole('link', { name: 'Ajuda' }).click();
			await expect(h1(page)).toHaveText('Como ler este observatório');
			await expect(page).toHaveURL(new RegExp(`^${escapar(base)}#/ajuda$`));

			// Voltar do navegador também fica no cliente.
			await page.goBack();
			await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
			expect(await page.evaluate(() => window.__semRecarga)).toBe(true);

			expect(problemas).toEqual([]);
		});

		test('a Início mostra os números do manifesto e os macrotemas', async ({ page }) => {
			const problemas = vigiar(page);
			await page.goto(url(site));
			const { documentos, topicos: nTopicos, com_afiliacao } = manifesto.contagens;

			const numero = (id: string) => page.getByTestId(`numero-${id}`);
			await expect(numero('documentos')).toHaveText(inteiro(documentos));
			await expect(numero('documentos')).toHaveAttribute('data-valor', String(documentos));
			await expect(numero('topicos')).toHaveText(inteiro(nTopicos));
			await expect(numero('topicos')).toHaveAttribute('data-valor', String(nTopicos));
			await expect(numero('revistas')).toHaveText(String(revistas.revistas.length));
			const [a, b] = manifesto.recorte.anos;
			await expect(numero('periodo')).toHaveText(`${a}–${b}`);
			await expect(numero('afiliacao')).toHaveText(`${Math.round((100 * com_afiliacao) / documentos)}%`);

			// Os 7 macrotemas, com rótulo e número de tópicos vindos de topicos.json.
			const itens = page.getByTestId('lista-macrotemas').getByRole('listitem');
			await expect(itens).toHaveCount(topicos.macrotemas.length);
			for (const [i, m] of topicos.macrotemas.entries()) {
				await expect(itens.nth(i)).toContainText(m.rotulo);
				await expect(itens.nth(i)).toContainText(`${m.topicos.length} tópicos`);
			}

			// Aviso de exemplo sintético e resumo do recorte na barra superior.
			await expect(page.getByTestId('aviso-exemplo')).toContainText('FICTÍCIOS');
			await expect(page.getByTestId('recorte')).toContainText(`${inteiro(documentos)} documentos`);
			await expect(page.getByTestId('recorte')).toContainText(`${revistas.revistas.length} revistas`);
			await expect(page.getByRole('img', { name: /Os 28 tópicos do corpus/ })).toBeVisible();

			expect(problemas).toEqual([]);
		});

		test('abre direto um link com filtros no hash', async ({ page }) => {
			const problemas = vigiar(page);
			await page.goto(`${url(site)}#/mapa?anos=2012-2020&cor=macrotema`);
			await expect(h1(page)).toHaveText('Mapa');
			const d = await esperarMapa(page);
			const esperados = tabelaDocumentos.colunas.ano.filter((a: number) => a >= 2012 && a <= 2020).length;
			expect(d.visiveis).toBe(esperados);
			await expect(page.getByTestId('cor-por')).toHaveValue('macrotema');
			await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(esperados));
			expect(problemas).toEqual([]);
		});
	});
}

test('o trilho leva o recorte às vistas de análise, e só o recorte', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/mapa?anos=2015-2020&revistas=dados&uf=SP&cor=ano&doc=exemplo:00001`);
	await esperarMapa(page);
	const link = (nome: string) => trilho(page).getByRole('link', { name: nome, exact: true });
	await expect(link('Tópicos')).toHaveAttribute('href', '#/topicos?anos=2015-2020&revistas=dados&uf=SP');
	await expect(link('Geografia')).toHaveAttribute('href', '#/geografia?anos=2015-2020&revistas=dados&uf=SP');
	await expect(link('Redes')).toHaveAttribute('href', '#/redes?anos=2015-2020&revistas=dados&uf=SP');
	await expect(link('Validação')).toHaveAttribute('href', '#/validacao');
	await expect(link('Início')).toHaveAttribute('href', '#/');
	await link('Geografia').click();
	await expect(page).toHaveURL(/#\/geografia\?anos=2015-2020&revistas=dados&uf=SP$/);
});

test('a barra do recorte mostra os filtros como chips, conta os documentos e limpa o recorte', async ({ page }) => {
	const problemas = vigiar(page);
	const [t1, t2] = topicos.topicos;
	const revista = tabelaDocumentos.dicionarios.revista[0];
	await page.goto(`${url('RAIZ')}#/mapa?anos=2014-2021&revistas=${revista}&topicos=${t1.id},${t2.id}&busca=coalizão`);
	await esperarMapa(page);
	const barra = page.getByTestId('barra-recorte');
	await expect(barra.getByRole('listitem').filter({ hasText: t1.rotulo })).toBeVisible();
	await expect(barra.getByText('Busca: “coalizão”')).toBeVisible();
	const c = tabelaDocumentos.colunas;
	const esperados = c.id.filter(
		(_: string, i: number) =>
			c.ano[i] >= 2014 && c.ano[i] <= 2021 && c.revista[i] === 0 && [t1.id, t2.id].includes(c.topico[i])
	).length;
	await barra.getByRole('button', { name: 'Tirar Busca: “coalizão”' }).click();
	await expect(page).not.toHaveURL(/busca=/);
	await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(esperados));
	await page.screenshot({ path: join(TELAS, 'recorte-1440x900.png') });
	await barra.getByRole('button', { name: 'Limpar recorte' }).click();
	await expect(page).toHaveURL(/#\/mapa$/);
	await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(tabelaDocumentos.n));
	await expect(barra.getByRole('button', { name: 'Limpar recorte' })).toHaveCount(0);
	// a barra não aparece fora das vistas de análise
	await trilho(page).getByRole('link', { name: 'Validação', exact: true }).click();
	await expect(page.getByTestId('barra-recorte')).toHaveCount(0);
	expect(problemas).toEqual([]);
});

test.describe('tema', () => {
	test('alterna, lembra a escolha e salva as telas nos dois temas', async ({ page }) => {
		// Sem movimento, para as capturas não pegarem uma transição no meio.
		await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
		await page.goto(url('RAIZ'));
		const html = page.locator('html');
		await expect(html).toHaveAttribute('data-tema', 'observatorio');
		await expect(page.getByTestId('lista-macrotemas').getByRole('listitem')).toHaveCount(7);
		await page.evaluate(() => document.fonts.ready.then(() => true));
		await page.screenshot({ path: join(TELAS, 'tema-observatorio-1440x900.png') });

		await page.getByRole('button', { name: /^Tema Observatório/ }).click();
		await expect(html).toHaveAttribute('data-tema', 'prancha');
		await expect(page.getByRole('button', { name: /^Tema Prancha/ })).toBeVisible();
		await page.screenshot({ path: join(TELAS, 'tema-prancha-1440x900.png') });

		// A escolha fica em localStorage e vale mais que o sistema.
		await page.reload();
		await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
		await expect(html).toHaveAttribute('data-tema', 'prancha');
		await page.emulateMedia({ colorScheme: 'dark' });
		await expect(html).toHaveAttribute('data-tema', 'prancha');
	});

	test('sem escolha, segue prefers-color-scheme', async ({ page }) => {
		await page.emulateMedia({ colorScheme: 'light' });
		await page.goto(url('RAIZ'));
		const html = page.locator('html');
		await expect(html).toHaveAttribute('data-tema', 'prancha');
		await page.emulateMedia({ colorScheme: 'dark' });
		await expect(html).toHaveAttribute('data-tema', 'observatorio');
	});
});

test.describe('acessibilidade e casos de borda', () => {
	test('o link de pular leva o foco ao conteúdo sem mudar a rota', async ({ page }) => {
		const problemas = vigiar(page);
		await page.goto(`${url('RAIZ')}#/topicos`);
		await expect(h1(page)).toHaveText('Tópicos');
		await expect(page.locator('html')).toHaveAttribute('lang', 'pt-BR');

		await page.keyboard.press('Tab');
		const pular = page.getByRole('link', { name: 'Pular para o conteúdo' });
		await expect(pular).toBeFocused();
		await expect(pular).toBeInViewport();
		await page.keyboard.press('Enter');
		await expect(page.locator('main#conteudo')).toBeFocused();
		await expect(page).toHaveURL(/#\/topicos$/);
		await expect(h1(page)).toHaveText('Tópicos');
		expect(problemas).toEqual([]);
	});

	test('o leitor de tela ouve o título da seção nova, mesmo na primeira visita', async ({ page }) => {
		await page.goto(url('RAIZ'));
		await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
		for (const secao of ['Tópicos', 'Classificação', 'Geografia', 'Validação']) {
			await trilho(page).getByRole('link', { name: secao, exact: true }).click();
			await expect(page.locator('#svelte-announcer')).toHaveText(new RegExp(`^${secao} ·`));
			await expect(h1(page)).toHaveText(secao);
		}
	});

	test('uma falha passageira de rede mostra "Tentar de novo", que abre a vista sem recarregar', async ({ page }) => {
		let falhou = false;
		await page.route('**/dados/documentos.json', (r) => {
			if (falhou) return r.continue();
			falhou = true;
			return r.fulfill({ status: 503, body: '' });
		});
		const excecoes: string[] = [];
		page.on('pageerror', (e) => excecoes.push(e.message));
		await page.goto(`${url('RAIZ')}#/mapa`);
		await expect(page.getByTestId('falha-ao-abrir')).toContainText('HTTP 503');
		await page.evaluate(() => (window.__semRecarga = true));
		await page.getByRole('button', { name: 'Tentar de novo' }).click();
		const d = await esperarMapa(page);
		expect(d.erro).toBeNull();
		await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(tabelaDocumentos.n)); // a barra também
		await trilho(page).getByRole('link', { name: 'Tópicos', exact: true }).click();
		await expect(h1(page)).toHaveText('Tópicos');
		expect(await page.evaluate(() => window.__semRecarga)).toBe(true);
		expect(excecoes).toEqual([]);
	});

	test('depois de uma falha passageira, a barra do recorte volta quando a pessoa segue pelo trilho', async ({ page }) => {
		let falhou = false;
		await page.route('**/dados/documentos.json', (r) => {
			if (falhou) return r.continue();
			falhou = true;
			return r.fulfill({ status: 503, body: '' });
		});
		await page.goto(`${url('RAIZ')}#/mapa`);
		await expect(page.getByTestId('falha-ao-abrir')).toBeVisible();
		await expect(page.getByTestId('barra-recorte')).toHaveCount(0);
		// sem clicar em "Tentar de novo": vai a Tópicos pelo trilho
		await trilho(page).getByRole('link', { name: 'Tópicos', exact: true }).click();
		await expect(page.getByTestId('figura-fluxo')).toBeVisible();
		await expect(page.getByTestId('contador-recorte')).toContainText(inteiro(tabelaDocumentos.n));
	});

	test('sem o arquivo das afiliações, só a Geografia falha, e "Tentar de novo" a abre', async ({ page }) => {
		let bloqueado = true;
		await page.route('**/dados/afiliacoes.json', (r) => (bloqueado ? r.fulfill({ status: 503, body: '' }) : r.continue()));
		const excecoes: string[] = [];
		page.on('pageerror', (e) => excecoes.push(e.message));
		await page.goto(`${url('RAIZ')}#/mapa`);
		expect((await esperarMapa(page)).erro).toBeNull();
		for (const [rotulo, titulo] of [
			['Tópicos', 'Tópicos'],
			['Classificação', 'Classificação']
		]) {
			await trilho(page).getByRole('link', { name: rotulo, exact: true }).click();
			await expect(h1(page)).toHaveText(titulo);
		}
		await trilho(page).getByRole('link', { name: 'Geografia', exact: true }).click();
		await expect(page.getByTestId('falha-ao-abrir')).toContainText('as afiliações');
		bloqueado = false;
		await page.getByRole('button', { name: 'Tentar de novo' }).click();
		await expect(page.getByTestId('figura-ufs')).toHaveAttribute('data-pronto', 'sim');
		expect(excecoes).toEqual([]);
	});

	test('rota inexistente mostra a página de erro dentro da casca', async ({ page }) => {
		await page.goto(`${url('RAIZ')}#/nao-existe`);
		await expect(page.getByText('Nada neste ponto do céu')).toBeVisible();
		await expect(trilho(page)).toBeVisible();
		await page.getByRole('link', { name: 'Voltar ao Início' }).click();
		await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
	});

	test('em tela estreita, o trilho vira uma barra embaixo', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
		await page.goto(url('RAIZ'));
		await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
		const caixa = await trilho(page).boundingBox();
		expect(caixa).not.toBeNull();
		expect(caixa!.y + caixa!.height).toBeGreaterThan(844 - 100);
		// Sem rolagem horizontal da página.
		expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
		await page.evaluate(() => document.fonts.ready.then(() => true));
		await page.screenshot({ path: join(TELAS, 'estreita-observatorio-390x844.png') });
		await trilho(page).getByRole('link', { name: 'Tópicos', exact: true }).click();
		await expect(h1(page)).toHaveText('Tópicos');
	});
});

test.describe('no celular', () => {
	test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });

	test('a barra de navegação mostra que rola e traz todas as seções, com as Redes', async ({ page }) => {
		await page.goto(url('RAIZ'));
		await expect(h1(page)).toHaveText(manifesto.projeto.titulo);
		const nav = trilho(page);
		// as Redes deixaram de ser a seção desativada ("v2"): são um link como os outros
		await expect(nav.getByRole('link', { name: 'Redes' })).toHaveCount(1);
		// os itens não cabem em 375 px: a borda direita ganha um degradê
		expect(await nav.evaluate((n) => n.scrollWidth > n.clientWidth)).toBe(true);
		await expect.poll(() => nav.evaluate((n) => getComputedStyle(n).maskImage)).not.toBe('none');
		// rolando até o fim, a Metodologia aparece, e o degradê passa para a borda esquerda
		await nav.evaluate((n) => n.scrollTo({ left: n.scrollWidth }));
		await expect(nav.getByRole('link', { name: 'Metodologia' })).toBeInViewport({ ratio: 1 });
		await expect
			.poll(() => nav.evaluate((n) => n.classList.contains('mais-a-esquerda') && !n.classList.contains('mais-a-direita')))
			.toBe(true);
	});
});

test.describe('nenhuma rota rola de lado', () => {
	const LARGURAS = [
		{ nome: 'celular', viewport: { width: 375, height: 812 }, isMobile: true },
		{ nome: 'tablet', viewport: { width: 768, height: 1024 }, isMobile: false },
		{ nome: 'tablet deitado', viewport: { width: 900, height: 700 }, isMobile: false },
		{ nome: 'notebook', viewport: { width: 1024, height: 768 }, isMobile: false }
	];
	const ROTAS = [
		'/',
		'/mapa',
		'/topicos',
		'/geografia',
		'/classificacao',
		'/validacao',
		'/redes',
		'/redes?rede=instituicoes&no=' + encodeURIComponent(ler('redes.json').instituicoes.id[0]),
		'/redes?rede=estados',
		'/redes?rede=citacoes',
		'/ajuda',
		'/projeto'
	];
	// quanto a página passa da largura da tela (no celular emulado, a viewport de layout se estica com o conteúdo:
	// por isso a conta é contra a largura pedida, e não contra o clientWidth)
	const transbordo = (page: Page, largura: number) =>
		page.evaluate((l) => document.documentElement.scrollWidth - l, largura);

	for (const l of LARGURAS) {
		test(`${l.viewport.width} px (${l.nome})`, async ({ browser }) => {
			for (const r of ROTAS) {
				// um contexto novo por rota: os gráficos medem a largura na montagem
				const contexto = await browser.newContext({
					viewport: l.viewport,
					isMobile: l.isMobile,
					hasTouch: l.isMobile,
					reducedMotion: 'reduce'
				});
				const page = await contexto.newPage();
				await page.goto(`${url('RAIZ')}#${r}`);
				await expect(h1(page)).toBeVisible();
				if (r === '/mapa') await esperarMapa(page);
				await expect(page.locator('[data-testid^="figura-"]:not([data-pronto])')).toHaveCount(0);
				await expect
					.poll(() => transbordo(page, l.viewport.width), { message: `${r} em ${l.viewport.width} px` })
					.toBeLessThanOrEqual(0);
				if (l.isMobile) {
					// no celular, a barra de navegação fica na tela
					await expect(trilho(page)).toBeInViewport();
					if (r === '/mapa') {
						await page.getByRole('button', { name: /^Recorte/ }).click();
						await expect(page.getByTestId('linha-do-tempo')).toBeVisible();
						await expect
							.poll(() => transbordo(page, l.viewport.width), { message: 'mapa com o recorte aberto' })
							.toBeLessThanOrEqual(0);
					}
				}
				// nas vistas com a barra do recorte, o menu das revistas aberto também cabe
				if (await page.getByTestId('barra-recorte').count()) {
					const menu = page.locator('details.revistas');
					if (!(await menu.isVisible())) {
						await page.getByTestId('barra-recorte').getByRole('button', { name: /^Recorte/ }).click();
					}
					await menu.locator('summary').click();
					await expect(menu.locator('ul')).toBeVisible();
					await expect
						.poll(() => transbordo(page, l.viewport.width), { message: `${r} com o menu das revistas aberto` })
						.toBeLessThanOrEqual(0);
				}
				await contexto.close();
			}
		});
	}
});

test.describe('projeto vazio (só o manifesto, como depois do `mapa novo`)', () => {
	test('a Início explica o que fazer e nenhum arquivo ausente é pedido', async ({ page }) => {
		const problemas = vigiar(page);
		const dados: string[] = [];
		page.on('request', (r) => {
			const caminho = new URL(r.url()).pathname;
			if (caminho.startsWith('/dados/')) dados.push(caminho);
		});

		await page.goto(url('VAZIO'));
		await expect(h1(page)).toHaveText('Projeto novo');
		await expect(page.getByRole('heading', { name: 'Este projeto ainda não tem dados.' })).toBeVisible();
		await expect(page.locator('code', { hasText: 'mapa coletar' })).toBeVisible();
		await expect(page.locator('code', { hasText: 'mapa topicos' })).toBeVisible();
		await expect(page.getByTestId('numero-documentos')).toHaveCount(0);
		await expect(page.getByTestId('aviso-exemplo')).toHaveCount(0);
		await expect(page.getByTestId('recorte')).toContainText('sem documentos');

		// Com api: true, o trilho ganha "Projeto".
		await trilho(page).getByRole('link', { name: 'Projeto', exact: true }).click();
		await expect(h1(page)).toHaveText('Projeto');

		// As outras seções dizem que os arquivos ainda não foram gerados.
		await trilho(page).getByRole('link', { name: 'Tópicos', exact: true }).click();
		await expect(h1(page)).toHaveText('Tópicos');
		await expect(page.getByText('ainda não gerado').first()).toBeVisible();

		expect(dados).toEqual(['/dados/manifesto.json']);
		expect(problemas).toEqual([]);
	});
});

test('a capa leva aos macrotemas e à geografia; a Ajuda explica o recorte', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto(url('RAIZ'));
	const lista = page.getByTestId('lista-macrotemas');
	await expect(lista.getByRole('img', { name: /^Participação de/ })).toHaveCount(7);
	const emAlta = topicos.macrotemas.filter((m: { tendencia?: { direcao: string } }) =>
		['alta', 'queda'].includes(m.tendencia?.direcao ?? '')
	).length;
	await expect(page.getByTestId('tendencia-macro')).toHaveCount(emAlta);
	const primeiro = topicos.macrotemas[0];
	await lista.getByRole('link', { name: primeiro.rotulo }).click();
	await expect(page).toHaveURL(new RegExp(`#/topicos\\?macro=${primeiro.id}$`));
	await expect(page.getByTestId('macro-aberto')).toHaveText(primeiro.rotulo);

	await page.goto(url('RAIZ'));
	await page.getByTestId('numero-afiliacao').click();
	await expect(page).toHaveURL(/#\/geografia$/);
	await expect(h1(page)).toHaveText('Geografia');

	await page.goto(`${url('RAIZ')}#/ajuda`);
	await expect(page.getByTestId('ajuda-recorte')).toContainText('um documento passa se tiver ao menos uma afiliação');
	await expect(page.getByRole('heading', { name: 'Como ler a geografia' })).toBeVisible();
});

test.describe('telas largas', () => {
	for (const [largura, altura] of [
		[1920, 1080],
		[2560, 1440]
	] as const) {
		test(`em ${largura} px, o conteúdo fica centrado e as figuras crescem`, async ({ browser }) => {
			const contexto = await browser.newContext({ viewport: { width: largura, height: altura }, reducedMotion: 'reduce' });
			const page = await contexto.newPage();
			const problemas = vigiar(page);
			await page.goto(`${url('RAIZ')}#/topicos`);
			await expect(h1(page)).toHaveText('Tópicos');
			await expect(page.locator('[data-testid^="figura-"]:not([data-pronto])')).toHaveCount(0);
			const m = await page.evaluate(() => {
				const principal = document.querySelector('main')!;
				// a coluna do trilho, no grid da casca
				const trilho = parseFloat(getComputedStyle(principal.parentElement!).gridTemplateColumns.split(' ')[0]);
				const main = principal.getBoundingClientRect();
				const figura = document.querySelector('[data-testid="figura-fluxo"] svg')?.getBoundingClientRect().width ?? 0;
				return { esquerda: main.left - trilho, direita: innerWidth - main.right, largura: main.width, figura };
			});
			// as sobras dos dois lados da coluna do conteúdo são iguais (a da esquerda, a partir do trilho)
			expect(Math.abs(m.esquerda - m.direita)).toBeLessThanOrEqual(2);
			// e a figura principal passa da largura antiga (76rem de casca, 1.104 px de figura)
			expect(m.figura).toBeGreaterThan(1200);
			expect(problemas).toEqual([]);
			await contexto.close();
		});
	}
});

test('no celular, a seção aberta fica à vista na barra de baixo', async ({ browser }) => {
	const contexto = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
	const page = await contexto.newPage();
	// a última seção da barra (no painel, Projeto), que ficava fora da tela, à direita
	await page.goto(`${url('PAINEL')}#/projeto`);
	await expect(h1(page)).toBeVisible();
	await expect(trilho(page).locator('[aria-current="page"]')).toBeInViewport({ ratio: 0.9 });
	await contexto.close();
});

/** `true` se o centro do elemento está na tela e é ele (ou um filho dele) que recebe o clique ali. */
const clicavel = (loc: import('@playwright/test').Locator) =>
	loc.evaluate((el) => {
		const c = el.getBoundingClientRect();
		const [x, y] = [c.left + c.width / 2, c.top + c.height / 2];
		if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
		const topo = document.elementFromPoint(x, y);
		return !!topo && (topo === el || el.contains(topo));
	});

test('rolando a página, a barra do recorte fica abaixo da barra do topo, e a Ajuda continua clicável', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 700 });
	await page.goto(`${url('RAIZ')}#/topicos`);
	await expect(h1(page)).toHaveText('Tópicos');
	await page.mouse.wheel(0, 1500);
	await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(300);
	await expect.poll(() => clicavel(page.getByRole('link', { name: /Ajuda/ }).first())).toBe(true);
	await expect.poll(() => clicavel(page.getByTestId('linha-do-tempo'))).toBe(true);
});

test('no celular, o "Baixar" da última figura não fica embaixo da barra de navegação', async ({ browser }) => {
	const contexto = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
	const page = await contexto.newPage();
	await page.goto(`${url('RAIZ')}#/geografia`);
	await expect(h1(page)).toHaveText('Geografia');
	await expect(page.locator('[data-testid^="figura-"]:not([data-pronto])')).toHaveCount(0);
	const ultimo = page.getByTestId('abrir-exportar').last();
	await ultimo.scrollIntoViewIfNeeded();
	await ultimo.click();
	const baixar = page.getByTestId('baixar-figura');
	await expect(baixar).toBeVisible();
	await expect.poll(() => clicavel(baixar)).toBe(true);
	const caixa = (await page.locator('[aria-label="Exportar a figura"]').boundingBox())!;
	expect(caixa.x).toBeGreaterThanOrEqual(0);
	expect(caixa.x + caixa.width).toBeLessThanOrEqual(375);
	await contexto.close();
});

test('um "%" solto no endereço não deixa a página em branco', async ({ page }) => {
	const problemas = vigiar(page);
	for (const [rota, titulo] of [
		['#/mapa?busca=50%', 'Mapa'],
		['#/topicos?busca=%FF', 'Tópicos'],
		['#/redes?no=%ZZ', 'Redes'],
		['#/topicos?busca=S%C3%A3o%', 'Tópicos']
	] as const) {
		// trocar só o hash faz o SvelteKit recarregar a página inteira: num computador lento, cada passo é uma carga
		await page.goto(`${url('RAIZ')}${rota}`);
		await expect(h1(page), rota).toHaveText(titulo, { timeout: 15000 });
	}
	// um link bem formado com %25 (ou %26) abre, sem deixar no endereço um % solto (ou um & que parte a busca), e
	// recarregar também
	const decodifica = () =>
		page.evaluate(() => {
			try {
				decodeURIComponent(location.hash);
				return true;
			} catch {
				return false;
			}
		});
	const busca = () => page.evaluate(() => new URLSearchParams(location.hash.split('?')[1] ?? '').get('busca'));
	await page.goto(`${url('RAIZ')}#/topicos?busca=100%25`);
	await expect(h1(page)).toHaveText('Tópicos', { timeout: 15000 });
	expect(await decodifica()).toBe(true);
	await page.reload();
	await expect(h1(page)).toHaveText('Tópicos', { timeout: 15000 });
	await page.goto('about:blank');
	await page.goto(`${url('RAIZ')}#/topicos?busca=voto%26partido`);
	await expect(h1(page)).toHaveText('Tópicos', { timeout: 15000 });
	expect(await busca()).toBe('voto partido');
	await page.reload();
	await expect(h1(page)).toHaveText('Tópicos', { timeout: 15000 });
	expect(await busca()).toBe('voto partido');
	expect(problemas.filter((p) => p.includes('URI malformed'))).toEqual([]);
});

test('sem WebGL, o mapa avisa (e aponta as outras vistas), em vez de ficar em branco', async ({ page }) => {
	await page.addInitScript(() => {
		const original = HTMLCanvasElement.prototype.getContext;
		// @ts-expect-error: a assinatura sobrecarregada do getContext
		HTMLCanvasElement.prototype.getContext = function (tipo: string, ...resto: unknown[]) {
			return /webgl/.test(tipo) ? null : original.call(this, tipo, ...resto);
		};
	});
	await page.goto(`${url('RAIZ')}#/mapa`);
	await expect(page.getByTestId('mapa-sem-webgl')).toContainText('O mapa não conseguiu desenhar');
	await expect(page.getByTestId('mapa-sem-webgl').getByRole('link', { name: 'Tópicos' })).toBeVisible();
});

test('no celular, o painel de exportação da primeira figura abre à vista, e só a barra do recorte gruda', async ({ browser }) => {
	const contexto = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
	const page = await contexto.newPage();
	await page.goto(`${url('RAIZ')}#/topicos`);
	await expect(h1(page)).toHaveText('Tópicos');
	await expect(page.locator('[data-testid^="figura-"]:not([data-pronto])')).toHaveCount(0);
	const primeiro = page.getByTestId('abrir-exportar').first();
	await primeiro.scrollIntoViewIfNeeded();
	await primeiro.click();
	await expect.poll(() => clicavel(page.getByTestId('baixar-figura'))).toBe(true);
	await page.keyboard.press('Escape');
	// rolando, a barra do topo sai da tela e a do recorte fica no alto, sem as duas se sobreporem
	await page.evaluate(() => scrollTo(0, 1200));
	const topo = (await page.locator('header.barra').boundingBox())!;
	expect(topo.y + topo.height).toBeLessThanOrEqual(1);
	await contexto.close();
});
