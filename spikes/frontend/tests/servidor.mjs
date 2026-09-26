// Servidores estáticos SEM regra de reescrita, para o spike M0d.
//
// servirComNode: diretório com barra -> index.html (se existir); diretório sem barra -> 301
//   para a versão com barra; arquivo -> 200; o resto -> 404. É o comportamento de um servidor
//   estático comum (nginx sem try_files, GitHub Pages, python -m http.server).
// servirComPython: `python3 -m http.server`, como segunda opinião independente.
//
// Os dois registram cada requisição em `log` ({ caminho, status }) e escutam só em 127.0.0.1.
import { spawn } from 'node:child_process';
import { createReadStream, existsSync, statSync } from 'node:fs';
import http from 'node:http';
import { extname, join, normalize, sep } from 'node:path';

const MIME = {
	'.html': 'text/html; charset=utf-8',
	'.js': 'text/javascript; charset=utf-8',
	'.css': 'text/css; charset=utf-8',
	'.json': 'application/json; charset=utf-8',
	'.png': 'image/png',
	'.svg': 'image/svg+xml',
	'.ico': 'image/x-icon',
	'.txt': 'text/plain; charset=utf-8',
	'.woff2': 'font/woff2'
};

export function servirComNode(raiz) {
	const raizNormalizada = normalize(raiz + sep);
	const log = [];
	const servidor = http.createServer((req, res) => {
		const url = new URL(req.url ?? '/', 'http://localhost');
		const responder = (status, cabecalhos = {}, corpo = '') => {
			log.push({ caminho: url.pathname, status });
			res.writeHead(status, cabecalhos);
			res.end(corpo);
		};
		let caminho;
		try {
			caminho = decodeURIComponent(url.pathname);
		} catch {
			return responder(400);
		}
		let arquivo = normalize(join(raizNormalizada, caminho));
		if (!arquivo.startsWith(raizNormalizada) && arquivo + sep !== raizNormalizada) {
			return responder(403);
		}
		if (existsSync(arquivo) && statSync(arquivo).isDirectory()) {
			if (!url.pathname.endsWith('/')) {
				return responder(301, { Location: url.pathname + '/' + url.search });
			}
			arquivo = join(arquivo, 'index.html');
		}
		if (!existsSync(arquivo) || !statSync(arquivo).isFile()) {
			return responder(404, { 'Content-Type': 'text/plain' }, 'não encontrado');
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
			const { port } = /** @type {import('node:net').AddressInfo} */ (servidor.address());
			resolver({
				tipo: 'node',
				origem: `http://127.0.0.1:${port}`,
				log,
				fechar: () =>
					new Promise((r) => {
						servidor.closeAllConnections();
						servidor.close(() => r());
					})
			});
		});
	});
}

export function servirComPython(raiz) {
	const log = [];
	const processo = spawn(
		'python3',
		['-u', '-m', 'http.server', '--bind', '127.0.0.1', '--directory', raiz, '0'],
		{ stdio: ['ignore', 'pipe', 'pipe'] }
	);
	processo.stderr.setEncoding('utf8');
	processo.stderr.on('data', (texto) => {
		for (const m of texto.matchAll(/"GET (\S+) HTTP\/[\d.]+" (\d{3})/g)) {
			log.push({ caminho: new URL(m[1], 'http://x').pathname, status: Number(m[2]) });
		}
	});
	const encerrado = new Promise((r) => processo.once('exit', r));
	const fechar = async () => {
		if (processo.exitCode === null) processo.kill('SIGTERM');
		await encerrado;
	};

	return new Promise((resolver, rejeitar) => {
		const limite = setTimeout(() => {
			fechar();
			rejeitar(new Error('python3 -m http.server não respondeu em 10 s'));
		}, 10_000);
		processo.once('error', (e) => {
			clearTimeout(limite);
			rejeitar(e);
		});
		processo.stdout.setEncoding('utf8');
		processo.stdout.on('data', (texto) => {
			const m = texto.match(/port (\d+)/);
			if (m) {
				clearTimeout(limite);
				resolver({ tipo: 'python', origem: `http://127.0.0.1:${m[1]}`, log, fechar });
			}
		});
	});
}
