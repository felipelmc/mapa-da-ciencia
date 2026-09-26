import adapter from '@sveltejs/adapter-static';

// Decisões do ADR 0002 (docs/decisoes/0002-frontend-router-hash-e-regl-scatterplot.md):
// - router por hash: o mesmo build funciona na raiz (`mapa painel`) e num subcaminho sem
//   regra de reescrita (GitHub Pages);
// - adapter-static SEM `fallback`: com router por hash ele não é necessário e só
//   sobrescreveria o index.html com um aviso;
// - depois do build, scripts/relativizar-index.ts troca "/_app/ por "./_app/ no index.html.

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			precompress: false,
			strict: true
		}),
		router: {
			type: 'hash'
		},
		typescript: {
			// Os scripts de build (Node puro) também passam pelo svelte-check.
			config(tsconfig) {
				tsconfig.include.push('../scripts/**/*.ts', '../playwright.config.ts');
			}
		}
	}
};

export default config;
