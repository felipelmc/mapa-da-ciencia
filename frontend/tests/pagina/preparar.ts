// Serve o site da documentação (../site, do `mkdocs build`) com o mesmo servidor estático dos testes e2e.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { servir } from '../e2e/servidor.ts';

export const SITE = join(fileURLToPath(new URL('../../..', import.meta.url)), 'site');

export default async function preparar() {
	if (!existsSync(join(SITE, 'index.html'))) {
		throw new Error('site/index.html não existe. Rode `uv run --group docs mkdocs build` na raiz antes.');
	}
	const servidor = await servir(SITE);
	process.env.E2E_URL_PAGINA = `${servidor.origem}/`;
	return () => servidor.fechar();
}
