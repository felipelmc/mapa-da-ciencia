import adapter from '@sveltejs/adapter-static';

// Spike M0d. O mesmo código gera várias variantes de build, escolhidas por SPIKE_VARIANTE,
// para comparar como cada uma se comporta servida na raiz e num subcaminho:
//
//   sem-fallback  router por hash, adapter-static sem `fallback` (configuração mínima)
//   com-fallback  idem, com `fallback: 'index.html'`
//   inline        idem a sem-fallback, com `output.bundleStrategy: 'inline'` (JS/CSS dentro do HTML)
//   base-fixa     idem a sem-fallback, com `paths.base: '/base-fixa'` (subcaminho conhecido no build)
//
// A variante `relativo` não passa por aqui: é a sem-fallback com o index.html reescrito
// por scripts/relativizar.mjs. Cada variante vai para build/<variante>/.
const VARIANTES = ['sem-fallback', 'com-fallback', 'inline', 'base-fixa'];
const variante = process.env.SPIKE_VARIANTE ?? 'sem-fallback';
if (!VARIANTES.includes(variante)) {
	throw new Error(`SPIKE_VARIANTE inválida: ${variante} (use ${VARIANTES.join(', ')})`);
}
const saida = `build/${variante}`;

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({
			pages: saida,
			assets: saida,
			fallback: variante === 'com-fallback' ? 'index.html' : undefined,
			precompress: false,
			strict: true
		}),
		router: {
			type: 'hash'
		},
		output: {
			bundleStrategy: variante === 'inline' ? 'inline' : 'split'
		},
		paths: {
			base: variante === 'base-fixa' ? '/base-fixa' : ''
		}
	}
};

export default config;
