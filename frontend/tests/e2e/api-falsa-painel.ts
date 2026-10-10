// A API do painel falsa (etapas, jobs com SSE, modelos, configuração e codebook), em memória, para os e2e da vista
// Projeto. Espelha as respostas de `servidor/rotas_jobs.py` e `servidor/rotas_projeto.py`, que o pytest testa.
//
// Cada job emite, a cada 150 ms: `estado` rodando, `etapa` (20 passos), um `avanco` por passo, algumas mensagens,
// `resumo` e `fim`. A PRIMEIRA conexão SSE de cada job cai depois de 5 eventos, de propósito: o navegador reconecta
// com o `Last-Event-ID`, e os testes conferem que nada se perde nem se repete.
import type { IncomingMessage, ServerResponse } from 'node:http';

interface Evento {
	seq: number;
	tipo: string;
	dados: Record<string, unknown>;
}
interface JobFalso {
	id: string;
	etapa: string;
	opcoes: Record<string, unknown>;
	estado: string;
	criado: string;
	inicio: string | null;
	fim: string | null;
	resumo: Record<string, unknown> | null;
	erro: string | null;
	eventos: Evento[];
	ouvintes: Set<() => void>;
	timer?: ReturnType<typeof setInterval>;
	conexoes: number;
}

const PASSOS = 20;
const PASSO_MS = 150; // um job leva uns 3 s: dá tempo de os testes o pegarem no meio, mesmo no CI
const REVISTAS = [
	{ issn: '0104-6276', acronimo: 'op', titulo: 'Opinião Pública', areas: ['Ciências Humanas'] },
	{ issn: '0011-5258', acronimo: 'dados', titulo: 'Dados', areas: ['Ciências Humanas'] },
	{ issn: '0103-3352', acronimo: 'rbcpol', titulo: 'Revista Brasileira de Ciência Política', areas: ['Ciências Humanas'] },
	{ issn: '1981-3821', acronimo: 'bpsr', titulo: 'Brazilian Political Science Review', areas: ['Ciências Humanas'] }
];

interface TopicoContrato {
	id: number;
	macro_id: number;
	rotulo: string;
	descricao: string;
	rotulo_fonte?: string;
	cor: string;
	palavras_chave: [string, number][];
	n_nucleo?: number;
}
interface MacroContrato {
	id: number;
	rotulo: string;
	descricao?: string;
	cor: string;
	topicos: number[];
}
type Manual = { rotulo: string; descricao: string };

/** `topicos`: o topicos.json do exemplo, de onde saem os rótulos que o editor do painel lê e grava. */
export function criarPainelFalso(
	codebookInicial: Record<string, unknown>,
	topicos?: { topicos: TopicoContrato[]; macrotemas: MacroContrato[] }
) {
	const jobs: JobFalso[] = [];
	let config: Record<string, unknown> = {
		versao_config: 1,
		nome: 'exemplo',
		titulo: 'Exemplo sintético',
		descricao: '',
		fontes: { scielo: { colecao: 'scl', revistas: ['0104-6276'], tipos: ['research-article'] }, openalex: { enriquecer: true } },
		recorte: { anos: [2010, 2025], idioma_analise: 'en', idioma_exibicao: 'pt' },
		modelos: {
			embeddings: { modelo: 'qwen3-embedding:0.6b' },
			classificacao: { modelo: 'qwen3.5:9b' },
			rotulos: { modelo: 'qwen3.5:9b' }
		},
		validacao: { n: 200, estratificar_por: 'topico', semente: 7 }
	};
	let codebook: Record<string, unknown> = { ...codebookInicial, hash: 'h0' };
	const instalados = new Set(['qwen3-embedding:0.6b', 'qwen3.5:4b']);
	let amostra: { n: number; codificados: number } | null = null;
	// uma etapa rodando "no terminal" (POST/DELETE /api/__teste/terminal), como a trava das etapas do Python
	let noTerminal: Record<string, unknown> | null = null;
	// os rótulos: os atuais (como no resultado.json) e o rotulos.yaml (as entradas à mão)
	const atuais = new Map<string, Manual & { fonte: string }>();
	for (const t of topicos?.topicos ?? []) atuais.set(`t:${t.id}`, { rotulo: t.rotulo, descricao: t.descricao, fonte: t.rotulo_fonte ?? 'llm' });
	for (const m of topicos?.macrotemas ?? []) atuais.set(`m:${m.id}`, { rotulo: m.rotulo, descricao: m.descricao ?? '', fonte: 'llm' });
	const manuais = new Map<string, Manual>();
	/** Como `aplicar_rotulos`: as entradas à mão valem; as que saíram do arquivo voltam às palavras-chave. */
	const aplicarRotulos = () => {
		for (const [k, atual] of atuais) {
			const m = manuais.get(k);
			if (m) atuais.set(k, { ...m, fonte: 'manual' });
			else if (atual.fonte === 'manual') atuais.set(k, { rotulo: 'palavras, chave', descricao: 'Palavras-chave.', fonte: 'palavras' });
		}
	};
	const pendentes = () =>
		[...atuais].filter(([k, a]) => {
			const m = manuais.get(k);
			return m ? m.rotulo !== a.rotulo || m.descricao !== a.descricao || a.fonte !== 'manual' : a.fonte === 'manual';
		}).length;
	const semAcento = (p: string) => p.normalize('NFD').replace(/\p{M}/gu, '');
	function rotulosAtuais() {
		const entrada = (k: string) => manuais.get(k) ?? null;
		return {
			topicos: (topicos?.topicos ?? []).map((t) => {
				const a = atuais.get(`t:${t.id}`)!;
				return {
					id: t.id, macro: t.macro_id, cor: t.cor, rotulo: a.rotulo, descricao: a.descricao, fonte: a.fonte,
					palavras: t.palavras_chave.slice(0, 10).map(([p]) => p), n_nucleo: t.n_nucleo ?? 0, manual: entrada(`t:${t.id}`)
				};
			}),
			macrotemas: (topicos?.macrotemas ?? []).map((m) => {
				const a = atuais.get(`m:${m.id}`)!;
				return { id: m.id, cor: m.cor, rotulo: a.rotulo, descricao: a.descricao, fonte: a.fonte, topicos: m.topicos, manual: entrada(`m:${m.id}`) };
			}),
			pendentes: pendentes()
		};
	}
	const agora = () => new Date().toISOString();
	const semEventos = (j: JobFalso) => {
		const { eventos, ouvintes, timer, conexoes, ...resto } = j;
		void eventos, ouvintes, timer, conexoes;
		return resto;
	};
	const json = (res: ServerResponse, status: number, corpo: unknown) => {
		res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
		res.end(JSON.stringify(corpo));
	};
	const corpoDe = (req: IncomingMessage) =>
		new Promise<Record<string, unknown>>((resolver) => {
			let texto = '';
			req.on('data', (c) => (texto += c));
			req.on('end', () => resolver(texto ? JSON.parse(texto) : {}));
		});

	function emitir(j: JobFalso, tipo: string, dados: Record<string, unknown> = {}) {
		j.eventos.push({ seq: j.eventos.length + 1, tipo, dados });
		for (const f of j.ouvintes) f();
	}

	function iniciar(etapa: string, opcoes: Record<string, unknown>): JobFalso {
		const j: JobFalso = {
			id: `job${jobs.length + 1}`,
			etapa,
			opcoes,
			estado: 'na_fila',
			criado: agora(),
			inicio: null,
			fim: null,
			resumo: null,
			erro: null,
			eventos: [],
			ouvintes: new Set(),
			conexoes: 0
		};
		jobs.unshift(j);
		let passo = -1;
		j.timer = setInterval(() => {
			if (passo === -1) {
				j.estado = 'rodando';
				j.inicio = agora();
				emitir(j, 'estado', { estado: 'rodando' });
				emitir(j, 'etapa', { nome: `Rodando ${etapa}`, total: PASSOS });
			} else if (passo < PASSOS) {
				emitir(j, 'avanco', { etapa: `Rodando ${etapa}`, feito: passo + 1, total: PASSOS });
				if ((passo + 1) % 5 === 0) emitir(j, 'mensagem', { texto: `passo ${passo + 1} de ${PASSOS}` });
			} else {
				clearInterval(j.timer);
				if (etapa === 'modelo') instalados.add(String(opcoes.modelo));
				j.estado = 'concluido';
				j.fim = agora();
				j.resumo = { frase: `${etapa}: ${PASSOS} passos feitos.` };
				emitir(j, 'resumo', j.resumo);
				emitir(j, 'fim', { estado: 'concluido' });
			}
			passo += 1;
		}, PASSO_MS);
		return j;
	}

	function sse(req: IncomingMessage, res: ServerResponse, j: JobFalso) {
		const ultimo = Number(req.headers['last-event-id'] ?? 0) || 0;
		j.conexoes += 1;
		const cair = j.conexoes === 1; // a primeira conexão cai depois de 5 eventos
		res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store' });
		res.write('retry: 300\n\n');
		let visto = ultimo;
		let enviados = 0;
		const enviar = () => {
			for (const e of j.eventos.filter((x) => x.seq > visto)) {
				res.write(`id: ${e.seq}\nevent: ${e.tipo}\ndata: ${JSON.stringify(e.dados)}\n\n`);
				visto = e.seq;
				enviados += 1;
				if (e.tipo === 'fim') return fechar();
				if (cair && enviados >= 5) return res.destroy();
			}
		};
		const fechar = () => {
			j.ouvintes.delete(enviar);
			res.end();
		};
		j.ouvintes.add(enviar);
		req.on('close', () => j.ouvintes.delete(enviar));
		enviar();
	}

	return (req: IncomingMessage, res: ServerResponse, url: URL): boolean => {
		const i = url.pathname.indexOf('/api/');
		if (i < 0) return false;
		const caminho = url.pathname.slice(i + '/api/'.length);
		const metodo = req.method ?? 'GET';
		const ativo = () => jobs.find((j) => j.estado === 'na_fila' || j.estado === 'rodando');

		if (metodo === 'GET' && caminho === 'projeto/etapas') {
			const feitos = new Set(jobs.filter((j) => j.estado === 'concluido').map((j) => j.etapa));
			const estado = (e: string, padrao: string) => (feitos.has(e) ? 'em_dia' : padrao);
			const ultima = { fim: '2026-09-26T12:00:00+00:00', duracao_s: 12.5, contagens: { documentos: 1500 } };
			json(res, 200, {
				coleta: { estado: estado('coleta', 'em_dia'), ultima },
				topicos: { estado: estado('topicos', 'em_dia'), ultima, ...(pendentes() ? { rotulos_pendentes: pendentes() } : {}) },
				geografia: { estado: estado('geografia', 'em_dia'), ultima },
				redes: feitos.has('redes') ? { estado: 'em_dia', ultima } : { estado: 'desatualizada', ultima, mudou: ['o pessoas.yaml'] },
				classificacao: { estado: estado('classificacao', 'desatualizada'), ultima },
				validacao: { estado: 'pendente', ultima: null, ...(amostra ? { amostra } : {}) },
				// o júri só vem num projeto com `juri.membros` (o do exemplo tem); ele não roda pelo painel
				juri: { estado: 'incompleta', ultima, proximo: 'mapa juri exportar-pedidos (e depois importar-respostas)' },
				...(noTerminal ? { em_andamento: noTerminal } : {})
			});
			return true;
		}
		if (caminho === 'rotulos') {
			if (!topicos) return (json(res, 404, { detail: 'O projeto ainda não tem tópicos.' }), true);
			if (metodo === 'GET') return (json(res, 200, rotulosAtuais()), true);
			void corpoDe(req).then((corpo) => {
				// como `PATCH /api/rotulos`: números que existem, rótulo não vazio; `null` tira a entrada
				const avisos: string[] = [];
				for (const [grupo, letra] of [['topicos', 't'], ['macrotemas', 'm']] as const) {
					for (const [id, e] of Object.entries((corpo[grupo] ?? {}) as Record<string, Manual | null>)) {
						const k = `${letra}:${id}`;
						if (!atuais.has(k)) return json(res, 422, { detail: `Não há ${grupo.slice(0, -1)} ${id} nos tópicos atuais.` });
						if (e && !e.rotulo.trim()) return json(res, 422, { detail: 'o rótulo não pode ficar vazio' });
					}
				}
				for (const [grupo, letra] of [['topicos', 't'], ['macrotemas', 'm']] as const) {
					for (const [id, e] of Object.entries((corpo[grupo] ?? {}) as Record<string, Manual | null>)) {
						const k = `${letra}:${id}`;
						if (e === null) manuais.delete(k);
						else manuais.set(k, { rotulo: e.rotulo.trim(), descricao: (e.descricao ?? '').trim() });
						const t = topicos.topicos.find((x) => letra === 't' && String(x.id) === id);
						for (const [p] of t?.palavras_chave ?? []) {
							const base = semAcento(p);
							// como `acentos_perdidos`: uma palavra do rótulo é a forma sem acento de uma palavra-chave
							if (e && base !== p && base.length >= 4 && e.rotulo.toLowerCase().split(/\s+/).includes(base))
								avisos.push(`Tópico ${id}: “${base}” perdeu o acento? As palavras do tópico têm “${p}”.`);
						}
					}
				}
				json(res, 200, { ...rotulosAtuais(), avisos });
			});
			return true;
		}
		if (caminho === '__teste/terminal') {
			void corpoDe(req).then((corpo) => {
				const etapa = String(corpo.etapa ?? 'coleta');
				noTerminal =
					metodo === 'POST'
						? {
								etapa,
								origem: 'terminal',
								pid: 4242,
								inicio: '2026-10-10T14:02:00-03:00',
								mensagem: `A etapa ${etapa} está rodando em outro terminal ou notebook (processo 4242) desde as 14:02. Espere terminar e rode de novo: duas etapas ao mesmo tempo no mesmo projeto estragam os dados uma da outra.`
							}
						: null;
				json(res, 200, { ok: true });
			});
			return true;
		}
		if (metodo === 'GET' && caminho === 'jobs') {
			json(res, 200, jobs.map(semEventos));
			return true;
		}
		if (metodo === 'POST' && (caminho.startsWith('etapas/') || caminho === 'modelos/baixar')) {
			void corpoDe(req).then((opcoes) => {
				const etapa = caminho === 'modelos/baixar' ? 'modelo' : caminho.slice('etapas/'.length);
				// como `rotas_jobs.py`: só as etapas do painel (o júri e a validação não são jobs)
				if (!['coleta', 'topicos', 'geografia', 'redes', 'classificacao', 'modelo'].includes(etapa))
					return json(res, 404, { detail: `Etapa desconhecida: ${etapa}.` });
				const a = ativo();
				if (a) return json(res, 409, { detail: { mensagem: `Já há uma etapa rodando (${a.etapa}).`, job: semEventos(a) } });
				// como `jobs.iniciar`: uma etapa no terminal trava o projeto (baixar um modelo, não)
				if (noTerminal && etapa !== 'modelo')
					return json(res, 409, { detail: { mensagem: noTerminal.mensagem, em_andamento: noTerminal } });
				if (etapa === 'topicos' && opcoes.aplicar_rotulos) aplicarRotulos(); // como `aplicar_rotulos`
				json(res, 202, semEventos(iniciar(etapa, opcoes)));
			});
			return true;
		}
		const m = caminho.match(/^jobs\/([\w-]+)(\/eventos)?$/);
		if (m) {
			const j = jobs.find((x) => x.id === m[1]);
			if (!j) return (json(res, 404, { detail: 'Job não encontrado.' }), true);
			if (m[2] && metodo === 'GET') return (sse(req, res, j), true);
			if (metodo === 'DELETE') {
				if (j.estado === 'rodando' || j.estado === 'na_fila') {
					clearInterval(j.timer);
					j.estado = 'cancelado';
					j.fim = agora();
					emitir(j, 'fim', { estado: 'cancelado' });
				}
				return (json(res, 200, semEventos(j)), true);
			}
			return (json(res, 200, semEventos(j)), true);
		}
		if (metodo === 'GET' && caminho === 'modelos') {
			const perfis = [
				{ nome: 'leve', descricao: 'Máquinas com 8 a 16 GB de memória.', ram_minima_gb: 8, embeddings: 'qwen3-embedding:0.6b', classificacao: 'qwen3.5:4b', rotulos: 'qwen3.5:4b', download_gb: 4 },
				{ nome: 'padrao', descricao: 'Máquinas com 16 a 32 GB de memória.', ram_minima_gb: 16, embeddings: 'qwen3-embedding:0.6b', classificacao: 'qwen3.5:9b', rotulos: 'qwen3.5:9b', download_gb: 7.2 },
				{ nome: 'forte', descricao: 'Máquinas com 32 GB ou mais.', ram_minima_gb: 32, embeddings: 'qwen3-embedding:0.6b', classificacao: 'qwen3.5:9b', rotulos: 'gemma4:26b', download_gb: 24.2 }
			];
			const tamanhos: Record<string, number> = { 'qwen3-embedding:0.6b': 0.64, 'qwen3.5:4b': 3.4, 'qwen3.5:9b': 6.6, 'gemma4:26b': 17 };
			const modelos = config.modelos as Record<string, { modelo: string }>;
			json(res, 200, {
				ram_gb: 24,
				perfil_sugerido: 'padrao',
				perfis,
				tamanhos_gb: tamanhos,
				ollama: { no_ar: true, erro: null },
				instalados: [...instalados].map((nome) => ({ nome, tamanho_gb: tamanhos[nome] ?? 1 })),
				projeto: Object.fromEntries(
					['embeddings', 'classificacao', 'rotulos'].map((p) => [
						p,
						{ modelo: modelos[p].modelo, instalado: instalados.has(modelos[p].modelo), download_gb: tamanhos[modelos[p].modelo] ?? null }
					])
				)
			});
			return true;
		}
		if (metodo === 'GET' && caminho === 'estimativa/classificacao') {
			json(res, 200, { modelo: 'qwen3.5:9b', documentos: 1480, classificados: 200, pendentes: 1280, segundos_por_documento: 11, estimativa_s: 14080 });
			return true;
		}
		if (metodo === 'POST' && caminho === 'validacao/amostra') {
			void corpoDe(req).then((c) => {
				amostra = { n: Number(c.n ?? 200), codificados: 0 };
				json(res, 200, { n: amostra.n, estratificar_por: 'topico', estratos: 7, semente: 7, avisos: [] });
			});
			return true;
		}
		if (metodo === 'GET' && caminho === 'revistas') {
			const semAcento = (t: string) => t.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
			const busca = semAcento(url.searchParams.get('busca') ?? '');
			const issns = (url.searchParams.get('issn') ?? '').split(',').filter(Boolean);
			const lista = issns.length
				? REVISTAS.filter((r) => issns.includes(r.issn))
				: REVISTAS.filter((r) => busca && semAcento(`${r.titulo} ${r.acronimo} ${r.issn}`).includes(busca));
			return (json(res, 200, lista), true);
		}
		if (caminho === 'configuracao') {
			if (metodo === 'GET') return (json(res, 200, config), true);
			void corpoDe(req).then((parcial) => {
				const recorte = parcial.recorte as { anos?: unknown[] } | undefined;
				if (recorte?.anos && !recorte.anos.every((a) => Number.isInteger(a)))
					return json(res, 422, { detail: 'mapa.yaml ficaria inválido: recorte.anos: Input should be a valid integer' });
				const mesclar = (a: Record<string, unknown>, b: Record<string, unknown>): Record<string, unknown> =>
					Object.fromEntries(
						[...new Set([...Object.keys(a), ...Object.keys(b)])].map((k) => {
							const [x, y] = [a[k], b[k]];
							return [k, y === undefined ? x : x && y && typeof x === 'object' && typeof y === 'object' && !Array.isArray(y) ? mesclar(x as Record<string, unknown>, y as Record<string, unknown>) : y];
						})
					);
				config = mesclar(config, parcial);
				json(res, 200, config);
			});
			return true;
		}
		if (caminho === 'codebook') {
			if (metodo === 'GET') return (json(res, 200, codebook), true);
			void corpoDe(req).then((novo) => {
				codebook = { ...novo, hash: `h${Date.now()}` };
				json(res, 200, codebook);
			});
			return true;
		}
		return false;
	};
}
