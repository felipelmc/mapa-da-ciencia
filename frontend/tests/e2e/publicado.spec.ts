// O site publicado (M7): o exemplo passado pelas regras do `mapa publicar` (contrato/exemplo-publicado). Sem API; a
// Metodologia diz o que a publicação retirou; o cartão de um artigo sem licença aberta mostra os valores da
// classificação, mas nem o resumo nem os trechos citados dele.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { esperarMapa, h1, inteiro, RAIZ, url, vigiar } from './comum';

const PASTA = join(RAIZ, '..', 'contrato', 'exemplo-publicado', 'dados');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ler = (arquivo: string): any => JSON.parse(readFileSync(join(PASTA, arquivo), 'utf8'));
const manifesto = ler('manifesto.json');

interface Detalhe {
	resumo: string | null;
	licenca: string;
	evidencias: Record<string, { evidencia: string }>;
}
const detalhes: Record<string, Detalhe> = {};
for (const arq of readdirSync(join(PASTA, 'detalhes'))) Object.assign(detalhes, ler(`detalhes/${arq}`).documentos);
const aberto = (d: Detalhe) => d.licenca.startsWith('cc');

test.beforeEach(async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
});

test('o exemplo publicado segue as regras', () => {
	expect(manifesto.api).toBe(false);
	const fechados = Object.values(detalhes).filter((d) => !aberto(d));
	expect(fechados.length).toBeGreaterThan(0);
	for (const d of fechados) {
		expect(d.resumo).toBeNull();
		for (const e of Object.values(d.evidencias)) expect(e.evidencia).toBe('');
	}
});

test('a Metodologia diz quando e o que foi publicado, e o site não chama API nenhuma', async ({ page }) => {
	const problemas = vigiar(page);
	const api: string[] = [];
	page.on('request', (r) => {
		if (new URL(r.url()).pathname.startsWith('/api/')) api.push(r.url());
	});
	await page.goto(`${url('PUBLICADO')}#/projeto`);
	await expect(h1(page)).toHaveText('Metodologia');
	const pub = page.getByTestId('publicacao');
	await expect(pub).toContainText(`${inteiro(manifesto.publicacao.resumos_publicados)} resumos com licença Creative Commons`);
	await expect(pub).toContainText('Nenhum e-mail');
	for (const rota of ['#/', '#/mapa', '#/classificacao', '#/validacao']) {
		await page.goto(`${url('PUBLICADO')}${rota}`);
		await expect(h1(page)).toHaveCount(1, { timeout: 15_000 }); // no CI, o Mapa (WebGL por software) demora
	}
	expect(api).toEqual([]);
	expect(problemas).toEqual([]);
});

test('o cartão de um artigo sem licença aberta: o aviso e os valores, sem os trechos', async ({ page }) => {
	const problemas = vigiar(page);
	const [id, d] = Object.entries(detalhes).find(([, d]) => !aberto(d) && Object.keys(d.evidencias).length)!;
	await page.goto(`${url('PUBLICADO')}#/mapa?doc=${encodeURIComponent(id)}`);
	await esperarMapa(page);
	const cartao = page.getByTestId('cartao-documento');
	await expect(cartao.getByTestId('aviso-licenca')).toContainText(d.licenca);
	await expect(cartao.getByTestId('resposta')).toHaveCount(Object.keys(d.evidencias).length);
	await expect(cartao.getByTestId('resumo-marcado')).toHaveCount(0);
	await expect(cartao.locator('mark')).toHaveCount(0);
	expect(problemas).toEqual([]);
});

test('o cartão de um artigo com licença aberta continua com o resumo marcado', async ({ page }) => {
	const [id, d] = Object.entries(detalhes).find(([, d]) => aberto(d) && d.resumo && Object.keys(d.evidencias).length)!;
	await page.goto(`${url('PUBLICADO')}#/mapa?doc=${encodeURIComponent(id)}`);
	await esperarMapa(page);
	const cartao = page.getByTestId('cartao-documento');
	await expect(cartao.getByTestId('resumo-marcado')).toHaveText(d.resumo!);
	await expect(cartao.getByTestId('aviso-licenca')).toHaveCount(0);
});
