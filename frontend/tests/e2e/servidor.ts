// Servidor estático SEM regra de reescrita, como o GitHub Pages ou um nginx sem try_files
// (adaptado de spikes/frontend/tests/servidor.mjs):
//   diretório com barra → index.html; diretório sem barra → 301 para a versão com barra;
//   arquivo → 200; o resto → 404.
// Escuta só em 127.0.0.1, numa porta livre, e registra cada requisição em `log`. Com `api`, as rotas `/api/…`
// vão para ela (a API falsa do painel, em `api-falsa.ts`).
import { createReadStream, existsSync, statSync } from 'node:fs';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { extname, join, normalize, sep } from 'node:path';
import type { ManipuladorApi } from './api-falsa.ts';

const MIME: Record<string, string> = {
	'.html': 'text/html; charset=utf-8',
	'.js': 'text/javascript; charset=utf-8',
	'.css': 'text/css; charset=utf-8',
	'.json': 'application/json; charset=utf-8',
	'.svg': 'image/svg+xml',
	'.png': 'image/png',
	'.woff2': 'font/woff2'
};

export interface Servidor {
	origem: string;
	log: { caminho: string; status: number }[];
	fechar: () => Promise<void>;
}

export function servir(raiz: string, api?: ManipuladorApi): Promise<Servidor> {
	const raizNormalizada = normalize(raiz + sep);
	const log: Servidor['log'] = [];

	const servidor = http.createServer((req, res) => {
		const url = new URL(req.url ?? '/', 'http://localhost');
		if (api && url.pathname.includes('/api/') && api(req, res, url)) {
			log.push({ caminho: url.pathname, status: res.statusCode });
			return;
		}
		const responder = (status: number, cabecalhos: Record<string, string> = {}, corpo = '') => {
			log.push({ caminho: url.pathname, status });
			res.writeHead(status, cabecalhos);
			res.end(corpo);
		};
		let caminho: string;
		try {
			caminho = decodeURIComponent(url.pathname);
		} catch {
			return responder(400);
		}
		let arquivo = normalize(join(raizNormalizada, caminho));
		if (!arquivo.startsWith(raizNormalizada) && arquivo + sep !== raizNormalizada) return responder(403);
		if (existsSync(arquivo) && statSync(arquivo).isDirectory()) {
			if (!url.pathname.endsWith('/')) return responder(301, { Location: `${url.pathname}/${url.search}` });
			arquivo = join(arquivo, 'index.html');
		}
		if (!existsSync(arquivo) || !statSync(arquivo).isFile()) {
			return responder(404, { 'Content-Type': 'text/plain; charset=utf-8' }, 'não encontrado');
		}
		log.push({ caminho: url.pathname, status: 200 });
		res.writeHead(200, {
			'Content-Type': MIME[extname(arquivo)] ?? 'application/octet-stream',
			'Cache-Control': 'no-store'
		});
		createReadStream(arquivo).pipe(res);
	});

	return new Promise((resolver, rejeitar) => {
		servidor.once('error', rejeitar);
		servidor.listen(0, '127.0.0.1', () => {
			const { port } = servidor.address() as AddressInfo;
			resolver({
				origem: `http://127.0.0.1:${port}`,
				log,
				fechar: () =>
					new Promise<void>((r) => {
						servidor.closeAllConnections();
						servidor.close(() => r());
					})
			});
		});
	});
}
