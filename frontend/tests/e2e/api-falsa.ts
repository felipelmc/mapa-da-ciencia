// Uma API de codificação falsa, em memória, para os testes e2e do painel (o CI do frontend não tem Python).
// Espelha a forma das respostas de `src/mapa_da_ciencia/servidor/validacao.py`, que o pytest testa de verdade:
//   GET  /api/validacao/fila?codificador=NOME   → { codificador, tipo, amostra, codebook, fila: [...] }
//   PUT  /api/validacao/codificacoes/{doc}      → { ok, completa } | 422 { detail: { problemas } }
//   GET  /api/validacao/metricas                → o validacao.json do exemplo
// A "amostra" são os primeiros N documentos do exemplo sintético.
import { readdirSync, readFileSync } from 'node:fs';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { join } from 'node:path';

interface Categoria {
	valor: string;
}
interface Variavel {
	id: string;
	tipo: string;
	categorias?: Categoria[];
}

export type ManipuladorApi = (req: IncomingMessage, res: ServerResponse, url: URL) => boolean;

export function criarApiFalsa(pastaExemplo: string, n = 24): ManipuladorApi {
	const ler = (arquivo: string) => JSON.parse(readFileSync(join(pastaExemplo, arquivo), 'utf8'));
	const documentos = ler('documentos.json');
	const codebook = ler('codebook.json');
	const validacao = ler('validacao.json');
	const detalhes: Record<string, { resumo: string | null; idioma: string | null }> = {};
	for (const f of readdirSync(join(pastaExemplo, 'detalhes'))) Object.assign(detalhes, ler(join('detalhes', f)).documentos);
	const amostra: string[] = documentos.colunas.id.filter((id: string) => detalhes[id]?.resumo).slice(0, n);
	const titulo = new Map<string, string>(documentos.colunas.id.map((id: string, i: number) => [id, documentos.colunas.titulo[i]]));
	const variaveis: Variavel[] = codebook.variaveis;
	const guardadas = new Map<string, Map<string, Record<string, unknown>>>();

	const json = (res: ServerResponse, status: number, corpo: unknown) => {
		res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
		res.end(JSON.stringify(corpo));
	};
	const semente = (texto: string) => [...texto].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 0x01000193) >>> 0, 0x811c9dc5);
	const completa = (r: Record<string, unknown>) => variaveis.every((v) => v.id in r);

	return (req, res, url) => {
		if (!url.pathname.includes('/api/validacao/')) return false;
		const caminho = url.pathname.slice(url.pathname.indexOf('/api/validacao/') + '/api/validacao/'.length);
		if (req.method === 'GET' && caminho === 'fila') {
			const nome = url.searchParams.get('codificador') ?? '';
			if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$/.test(nome)) {
				json(res, 400, { detail: 'Nome de codificador inválido.' });
				return true;
			}
			const dele = guardadas.get(nome) ?? new Map();
			// embaralhada com uma semente tirada do nome (Fisher–Yates com um gerador linear), como no Python
			const ordem = [...amostra];
			let x = semente(nome) || 1;
			for (let i = ordem.length - 1; i > 0; i -= 1) {
				x = (Math.imul(x, 1664525) + 1013904223) >>> 0;
				const j = x % (i + 1);
				[ordem[i], ordem[j]] = [ordem[j], ordem[i]];
			}
			json(res, 200, {
				codificador: nome,
				tipo: guardadas.has(nome) ? 'humano' : null,
				amostra: { n: amostra.length, estratificar_por: 'topico', semente: 7 },
				codebook,
				fila: ordem.map((doc) => ({
					doc,
					titulo: titulo.get(doc),
					resumo: detalhes[doc].resumo,
					idioma: detalhes[doc].idioma ?? 'pt',
					respostas: dele.get(doc) ?? {},
					completa: completa(dele.get(doc) ?? {})
				}))
			});
			return true;
		}
		if (req.method === 'PUT' && caminho.startsWith('codificacoes/')) {
			const doc = decodeURIComponent(caminho.slice('codificacoes/'.length));
			let corpo = '';
			req.on('data', (c) => (corpo += c));
			req.on('end', () => {
				const { codificador, respostas, completa: exigir } = JSON.parse(corpo);
				if (!amostra.includes(doc)) return json(res, 404, { detail: `O documento ${doc} não está na amostra.` });
				const problemas: string[] = [];
				for (const [id, r] of Object.entries(respostas as Record<string, { valor: unknown }>)) {
					const v = variaveis.find((x) => x.id === id);
					if (!v) problemas.push(`variáveis que não estão no codebook: ${id}`);
					else if (v.tipo === 'categorica' && !v.categorias!.some((c) => c.valor === r.valor))
						problemas.push(`\`${id}\`: ${JSON.stringify(r.valor)} não é uma das categorias`);
				}
				if (exigir) for (const v of variaveis) if (!(v.id in respostas)) problemas.push(`\`${v.id}\`: faltou a variável`);
				if (problemas.length) return json(res, 422, { detail: { problemas } });
				const dele = guardadas.get(codificador) ?? new Map();
				dele.set(doc, { ...(dele.get(doc) ?? {}), ...respostas });
				guardadas.set(codificador, dele);
				json(res, 200, { ok: true, completa: completa(dele.get(doc)) });
			});
			return true;
		}
		if (req.method === 'GET' && caminho === 'metricas') {
			json(res, 200, validacao);
			return true;
		}
		json(res, 404, { detail: 'não encontrado' });
		return true;
	};
}
