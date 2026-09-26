import { createReadStream, existsSync, statSync } from 'node:fs';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { join, normalize, resolve, sep } from 'node:path';
import { sveltekit } from '@sveltejs/kit/vite';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

/**
 * Serve uma pasta do contrato de dados em `/dados/` no `vite dev` e no `vite preview`.
 *
 * Por padrão, é o exemplo sintético versionado em `contrato/exemplo/dados`. Para ver um
 * projeto de verdade, aponte `MAPA_DADOS` para a pasta `saida/dados` dele:
 *
 *     MAPA_DADOS=~/meu-projeto/saida/dados npm run dev
 *
 * No build não entra nada: o app lê `./dados/*.json` relativo à página, e quem serve essa
 * pasta é o `mapa painel` (ou o site publicado).
 */
function servirDados(): Plugin {
	const pasta = resolve(process.env.MAPA_DADOS ?? '../contrato/exemplo/dados');
	const raiz = normalize(pasta + sep);

	function responder(req: IncomingMessage, res: ServerResponse, seguir: () => void) {
		// O `use('/dados', ...)` do connect já tirou o prefixo: req.url é `/manifesto.json`.
		const caminho = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname);
		const arquivo = normalize(join(raiz, caminho));
		if (!arquivo.startsWith(raiz)) {
			res.statusCode = 403;
			return res.end();
		}
		if (!existsSync(arquivo) || !statSync(arquivo).isFile()) {
			if (caminho === '/' || caminho === '') return seguir();
			res.statusCode = 404;
			return res.end(`não encontrado em ${pasta}: ${caminho}`);
		}
		res.setHeader('Content-Type', 'application/json; charset=utf-8');
		res.setHeader('Cache-Control', 'no-store');
		createReadStream(arquivo).pipe(res);
	}

	return {
		name: 'mapa-da-ciencia:dados',
		configureServer(server) {
			server.middlewares.use('/dados', responder);
		},
		configurePreviewServer(server) {
			server.middlewares.use('/dados', responder);
		}
	};
}

export default defineConfig({
	plugins: [sveltekit(), servirDados()],
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node'
	}
});
