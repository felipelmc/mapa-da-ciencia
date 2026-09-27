// Gera a captura da abertura do site (docs/imagens/abertura.png) para o README, a partir do site montado pelo
// MkDocs em ../site (`uv run --group docs mkdocs build` antes), no tema Observatório, com o céu já formado.
//
// Uso (da pasta frontend/):
//   node scripts/captura-abertura.ts
import { chromium } from '@playwright/test';
import { existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { servir } from '../tests/e2e/servidor.ts';

const RAIZ = fileURLToPath(new URL('../..', import.meta.url));
const SITE = join(RAIZ, 'site');
const DESTINO = join(RAIZ, 'docs', 'imagens', 'abertura.png');
if (!existsSync(join(SITE, 'index.html'))) {
	console.error('Falta o site: rode `uv run --group docs mkdocs build` na raiz antes.');
	process.exit(1);
}

const servidor = await servir(SITE);
const navegador = await chromium.launch();
try {
	const page = await navegador.newPage({ viewport: { width: 1280, height: 800 }, colorScheme: 'dark', reducedMotion: 'reduce' });
	await page.goto(`${servidor.origem}/`);
	await page.waitForFunction(() => (window as unknown as { __ceu?: { fase: string } }).__ceu?.fase === 'formado');
	await page.evaluate(() => document.fonts.ready);
	await page.waitForTimeout(500);
	await page.screenshot({ path: DESTINO });
	console.log(`${DESTINO} (${Math.round(statSync(DESTINO).size / 1024)} KB)`);
} finally {
	await navegador.close();
	await servidor.fechar();
}
