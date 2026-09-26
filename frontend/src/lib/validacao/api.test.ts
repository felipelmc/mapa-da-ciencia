import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Gravador, type RespostaVariavel } from './api';

const R: Record<string, RespostaVariavel> = { abordagem: { valor: 'mista', evidencia: '', incerto: false, nota: '' } };

/** Um localStorage em memória, ou um que lança em tudo (dados do site bloqueados). */
function armazenamento(bloqueado = false) {
	const dados = new Map<string, string>();
	const talvez = <T>(f: () => T) => {
		if (bloqueado) throw new DOMException('bloqueado', 'SecurityError');
		return f();
	};
	return {
		getItem: (k: string) => talvez(() => dados.get(k) ?? null),
		setItem: (k: string, v: string) => talvez(() => void dados.set(k, v)),
		removeItem: (k: string) => talvez(() => void dados.delete(k)),
		dados
	};
}

/** fetch falso: `respostas[doc]` é o status devolvido para a ficha (ou 'rede' para uma falha de conexão). */
function painel(respostas: Record<string, number | 'rede'>) {
	const pedidos: string[] = [];
	const fetch = vi.fn(async (url: string) => {
		const doc = decodeURIComponent(url.split('/').at(-1)!);
		pedidos.push(doc);
		const status = respostas[doc] ?? 200;
		if (status === 'rede') throw new TypeError('Failed to fetch');
		return new Response(JSON.stringify(status === 200 ? { ok: true } : { detail: `erro ${status}` }), { status });
	});
	return { fetch, pedidos };
}

beforeEach(() => {
	vi.stubGlobal('document', { baseURI: 'http://127.0.0.1:8000/' });
});
afterEach(() => vi.unstubAllGlobals());

describe('Gravador', () => {
	it('uma ficha recusada ou com erro do servidor não trava as outras', async () => {
		const ls = armazenamento();
		vi.stubGlobal('localStorage', ls);
		const { fetch, pedidos } = painel({ fora: 404, falhou: 500 });
		vi.stubGlobal('fetch', fetch);
		const avisos: (string | null)[] = [];
		const g = new Gravador('op', 'maria', (_, e) => avisos.push(e));
		ls.setItem(g.chave, JSON.stringify({ fora: { respostas: R, completa: false }, falhou: { respostas: R, completa: false } }));
		await g.gravar('d1', R, true);
		expect(pedidos).toEqual(['fora', 'falhou', 'd1']); // uma volta, sem repetir a que falhou
		expect(Object.keys(g.pendencias())).toEqual(['falhou']); // a recusada sai; a do erro 500 fica para depois
		expect(avisos.at(-1)).toContain('falhou');
	});

	it('sem conexão, para e guarda tudo', async () => {
		vi.stubGlobal('localStorage', armazenamento());
		vi.stubGlobal('fetch', painel({ d1: 'rede' }).fetch);
		const g = new Gravador('op', 'maria');
		await g.gravar('d1', R, false);
		await g.gravar('d2', R, true);
		expect(Object.keys(g.pendencias()).sort()).toEqual(['d1', 'd2']);
	});

	it('a chave separa projetos e codificadores', () => {
		expect(new Gravador('op', 'maria').chave).not.toBe(new Gravador('cp-scielo', 'maria').chave);
	});

	it('sem localStorage, as pendências ficam na memória e são enviadas', async () => {
		vi.stubGlobal('localStorage', armazenamento(true));
		const rede = painel({ d1: 'rede' });
		vi.stubGlobal('fetch', rede.fetch);
		const g = new Gravador('op', 'maria');
		await g.gravar('d1', R, true);
		expect(Object.keys(g.pendencias())).toEqual(['d1']); // não sumiu por falta de onde guardar
		vi.stubGlobal('fetch', painel({}).fetch);
		await g.enviar();
		expect(g.pendencias()).toEqual({});
	});
});
