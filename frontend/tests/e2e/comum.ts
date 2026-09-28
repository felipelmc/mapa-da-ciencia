// Ajudantes compartilhados pelos testes e2e.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Page } from '@playwright/test';

export const RAIZ = fileURLToPath(new URL('../..', import.meta.url));
export const TELAS = join(RAIZ, 'test-results');
const EXEMPLO = join(RAIZ, '..', 'contrato', 'exemplo', 'dados');
const PUBLICADO = join(RAIZ, '..', 'contrato', 'exemplo-publicado', 'dados');

/** Um arquivo do exemplo sintético (o mesmo que os sites de teste servem), ou da versão publicada dele. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const ler = (arquivo: string, qual: 'exemplo' | 'publicado' = 'exemplo'): any =>
	JSON.parse(readFileSync(join(qual === 'exemplo' ? EXEMPLO : PUBLICADO, arquivo), 'utf8'));

export const inteiro = (n: number) => new Intl.NumberFormat('pt-BR').format(n);

export const url = (nome: 'RAIZ' | 'SUBCAMINHO' | 'VAZIO' | 'PAINEL' | 'PUBLICADO') => {
	const valor = process.env[`E2E_URL_${nome}`];
	if (!valor) throw new Error(`E2E_URL_${nome} não definida; o globalSetup (tests/e2e/preparar.ts) rodou?`);
	return valor;
};

/** Junta erros e avisos do console, exceções, respostas ≥ 400 e requisições que falharam. */
export function vigiar(page: Page) {
	const problemas: string[] = [];
	page.on('console', (m) => {
		// Avisos de desempenho do próprio driver WebGL do Chrome (ex.: "GPU stall due to ReadPixels"), que o
		// regl-scatterplot provoca ao ler a posição do mouse; não são erros da aplicação.
		if (m.text().includes('GL Driver Message')) return;
		if (m.type() === 'error' || m.type() === 'warning') problemas.push(`console ${m.type()}: ${m.text()}`);
	});
	page.on('pageerror', (e) => problemas.push(`exceção: ${e.message}`));
	page.on('response', (r) => {
		if (r.status() >= 400) problemas.push(`${r.status()} ${new URL(r.url()).pathname}`);
	});
	page.on('requestfailed', (r) => problemas.push(`falhou: ${r.url()} ${r.failure()?.errorText}`));
	return problemas;
}

export const h1 = (page: Page) => page.getByRole('heading', { level: 1 });
export const trilho = (page: Page) => page.getByRole('navigation', { name: 'Seções' });
export const escapar = (texto: string) => texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Espera o mapa terminar o primeiro desenho (ou falhar) e devolve o estado de depuração. */
export async function esperarMapa(page: Page) {
	await page.waitForFunction(() => window.__mapaDebug?.desenhado || window.__mapaDebug?.erro, null, {
		timeout: 30_000
	});
	return (await page.evaluate(() => window.__mapaDebug))!;
}
