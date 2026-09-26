// Testes e2e da casca (M1), sobre o build servido por um estático sem reescrita.
// Os sites e as URLs vêm de tests/e2e/preparar.ts.
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
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

			// Redes aparece desativada, com selo; Projeto não aparece fora do painel.
			await expect(trilho(page).getByRole('link', { name: /Redes/ })).toHaveCount(0);
			await expect(trilho(page).getByText('Redes', { exact: true })).toBeVisible();
			await expect(trilho(page).getByText('v2', { exact: true })).toBeVisible();
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

	test('rota inexistente mostra a página de erro dentro da casca', async ({ page }) => {
		await page.goto(`${url('RAIZ')}#/nao-existe`);
		await expect(page.getByText('Nada neste ponto do céu')).toBeVisible();
		await expect(trilho(page)).toBeVisible();
		await page.getByRole('link', { name: 'Voltar para a Início' }).click();
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
