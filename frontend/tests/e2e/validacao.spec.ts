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
	const doPar = validacao.metricas.filter(
		(m: { referencia: string; comparado: string }) => m.referencia === 'referencia-exemplo' && m.comparado === 'exemplo'
	);
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

test('o júri: estágios por variável, auditoria e o par circular marcado', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/validacao`);
	await expect(page.getByTestId('secao-juri')).toBeVisible();
	await expect(page.getByTestId('tabela-juri').locator('tbody tr')).toHaveCount(Object.keys(validacao.juri.etapas).length);
	await expect(page.getByTestId('auditoria-juri')).toContainText(`conferiu ${validacao.juri.auditoria.n} decisões`);
	await expect(page.getByTestId('concordancia-supervisor')).toContainText('circular');
	const circular = page.getByTestId('par').filter({ hasText: 'juri-supervisor' });
	await expect(circular).toContainText('circular');
	await circular.click();
	await expect(page.getByTestId('aviso-circular')).toBeVisible();
	expect(problemas).toEqual([]);
});

test('o cartão de um documento da amostra mostra os votos do júri', async ({ page }) => {
	const problemas = vigiar(page);
	await page.goto(`${url('RAIZ')}#/mapa?doc=${encodeURIComponent('exemplo:00689')}`);
	const juri = page.getByTestId('votos-do-juri');
	await expect(juri).toBeVisible({ timeout: 15_000 });
	await juri.locator('summary').click();
	await expect(juri.getByTestId('decisao-juri').first()).toBeVisible();
	expect(problemas).toEqual([]);
});

test('sem maioria e sem supervisor, o cartão diz o que valeu; a mudança na deliberação é dita em texto', async ({ page }) => {
	const problemas = vigiar(page);
	const doc = 'exemplo:00689';
	await page.route('**/detalhes/*.json', async (route) => {
		const resposta = await route.fetch();
		const dados = await resposta.json();
		const juri = dados.documentos?.[doc]?.juri;
		if (juri) {
			const [id] = Object.keys(juri);
			const votos = juri[id].votos.filter((v: { rodada: number }) => v.rodada === 1);
			juri[id] = {
				...juri[id],
				etapa: 'sem_maioria',
				supervisor: null,
				justificativa: null,
				valor: votos[0].valor,
				valor_sem_supervisor: votos[0].valor,
				votos: [...votos, { ...votos[1], rodada: 2, valor: votos[0].valor, revisou: true }]
			};
		}
		await route.fulfill({ response: resposta, json: dados });
	});
	await page.goto(`${url('RAIZ')}#/mapa?doc=${encodeURIComponent(doc)}`);
	const juri = page.getByTestId('votos-do-juri');
	await expect(juri).toBeVisible({ timeout: 15_000 });
	await juri.locator('summary').click();
	await expect(juri.getByTestId('valeu-presidente')).toContainText('o voto do primeiro membro');
	await expect(juri.getByTestId('mudou-na-deliberacao').first()).toContainText('mudou na deliberação para');
	await expect(juri.getByText('A seta (→) mostra o voto mudado na deliberação.')).toBeVisible();
	await expect(juri.locator('q.trecho').first()).toBeVisible();
	expect(problemas).toEqual([]);
});

for (const site of ['RAIZ', 'PUBLICADO'] as const) {
	test(`a comparação entre modelos lista cada par significativo, mais de um por variável (${site === 'RAIZ' ? 'raiz' : 'publicado'})`, async ({ page }) => {
		// no piloto, com o júri, são 6 modelos e 15 pares por variável: dois pares com p < 0,05 na mesma variável
		// repetiam a chave da lista, e o Svelte parava a página em "Carregando a validação…"
		const dados = site === 'RAIZ' ? validacao : ler('validacao.json', 'publicado');
		const significativos = dados.comparacoes_modelos.filter((c: { p: number }) => c.p < 0.05);
		const porVariavel = new Map<string, number>();
		for (const c of significativos) porVariavel.set(c.variavel, (porVariavel.get(c.variavel) ?? 0) + 1);
		expect(Math.max(...porVariavel.values())).toBeGreaterThan(1); // o exemplo cobre o caso
		const problemas = vigiar(page);
		await page.goto(`${url(site)}#/validacao`);
		await expect(h1(page)).toHaveText('Validação');
		await expect(page.getByTestId('lista-mcnemar').locator('li')).toHaveCount(significativos.length);
		expect(problemas).toEqual([]);
	});
}

test('um erro ao desenhar a vista vira um aviso com "Tentar de novo", e a outra rota abre normalmente', async ({ page }) => {
	// uma métrica sem a matriz faz a vista falhar ao desenhar; sem a proteção da casca, a página ficava parada
	await page.route('**/dados/validacao.json', async (rota) => {
		const resposta = await rota.fetch();
		const dados = await resposta.json();
		dados.metricas[0].matriz = null;
		await rota.fulfill({ response: resposta, json: dados });
	});
	await page.goto(`${url('RAIZ')}#/validacao`);
	await expect(page.getByTestId('falha-ao-abrir')).toContainText('Não foi possível abrir a vista Validação');
	await expect(page.getByRole('button', { name: 'Tentar de novo' })).toBeVisible();
	await page.goto(`${url('RAIZ')}#/topicos`);
	await expect(h1(page)).toHaveText('Tópicos');
	await expect(page.getByTestId('falha-ao-abrir')).toHaveCount(0);
});

test('no painel, um erro da API de métricas aparece, em vez das métricas antigas do arquivo', async ({ page }) => {
	await page.route('**/api/validacao/metricas', (rota) => rota.fulfill({ status: 500, json: { detail: 'falhou ao calcular' } }));
	await page.goto(`${url('PAINEL')}#/validacao`);
	await expect(page.getByTestId('falha-ao-abrir')).toContainText('falhou ao calcular');
	await expect(page.getByTestId('tabela-metricas')).toHaveCount(0);
});

test('a comparação entre modelos diz quem acerta mais que quem, e o p pequeno como "< 0,001"', async ({ page }) => {
	await page.goto(`${url('RAIZ')}#/validacao`);
	const itens = page.getByTestId('lista-mcnemar').locator('li');
	await expect(itens.first()).toContainText('acerta mais que');
	await expect(page.getByTestId('lista-mcnemar')).not.toContainText('p = 0,000');
});

test('numa tela larga, a tabela do par acompanha a rolagem ao lado do detalhe', async ({ page }) => {
	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto(`${url('RAIZ')}#/validacao`);
	await expect(page.getByTestId('figura-concordancia')).toHaveCSS('position', 'sticky');
	await page.setViewportSize({ width: 1440, height: 900 });
	await expect(page.getByTestId('figura-concordancia')).toHaveCSS('position', 'static');
});
