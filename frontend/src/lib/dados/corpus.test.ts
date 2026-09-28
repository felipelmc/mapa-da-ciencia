import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import type { Afiliacoes, Documentos, Manifesto, Topicos } from '$lib/contrato/tipos';
import { FILTROS_PADRAO } from '$lib/estado/url';
import { abrirCubo, aoReabrir, lacoVale, reabrirCubo, versaoDoMapa } from './corpus';
import { decodificar } from './documentos';
import type { FonteDeDados, NomeArquivo } from './fonte';

const pasta = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const ler = <T>(nome: string): T => JSON.parse(readFileSync(join(pasta, nome), 'utf8'));
const manifesto = ler<Manifesto>('manifesto.json');
const documentos = ler<Documentos>('documentos.json');
const topicos = ler<Topicos>('topicos.json');
const afiliacoes = ler<Afiliacoes>('afiliacoes.json');

/** Uma fonte falsa com o exemplo, em que `falhas[arquivo]` pedidos a esse arquivo falham antes de dar certo. */
function fonteFalsa(falhas: Partial<Record<NomeArquivo, number>> = {}) {
	const pedidos: Record<string, number> = {};
	const responder = <T>(nome: NomeArquivo, valor: T) => {
		pedidos[nome] = (pedidos[nome] ?? 0) + 1;
		return pedidos[nome] <= (falhas[nome] ?? 0)
			? Promise.reject(new Error(`Não foi possível carregar ./dados/${nome}.json (HTTP 503).`))
			: Promise.resolve(valor);
	};
	const fonte: FonteDeDados = {
		capacidades: { escrita: false, aoVivo: false },
		manifesto: async () => manifesto,
		tem: async (arquivo) => arquivo === 'manifesto' || manifesto.arquivos.includes(arquivo),
		revistas: async () => null,
		documentos: () => responder('documentos', documentos),
		afiliacoes: () => responder('afiliacoes', afiliacoes),
		topicos: () => responder('topicos', topicos),
		codebook: async () => null,
		classificacoes: async () => null,
		validacao: async () => null,
		agregados: async () => null,
		detalhe: async () => null,
		redes: async () => null,
		citacoes: async () => null
	};
	return { fonte, pedidos };
}

describe('abrirCubo', () => {
	it('uma falha passageira não fica guardada: a próxima chamada pede de novo', async () => {
		const { fonte, pedidos } = fonteFalsa({ documentos: 1 });
		await expect(abrirCubo(fonte)).rejects.toThrow('HTTP 503');
		const aberto = await abrirCubo(fonte);
		expect(aberto?.tabela.n).toBe(documentos.n);
		expect(pedidos.documentos).toBe(2);
		// depois de abrir, fica guardado
		expect(await abrirCubo(fonte)).toBe(aberto);
		expect(pedidos.documentos).toBe(2);
	});

	it('o cubo que abre depois de uma falha avisa quem ouve, mesmo sem "Tentar de novo"', async () => {
		const { fonte } = fonteFalsa({ documentos: 1 });
		const ouvinte = vi.fn();
		const parar = aoReabrir(ouvinte);
		await expect(abrirCubo(fonte)).rejects.toThrow('HTTP 503');
		expect(ouvinte).not.toHaveBeenCalled();
		await abrirCubo(fonte); // uma vista aberta pelo trilho
		expect(ouvinte).toHaveBeenCalledOnce();
		await abrirCubo(fonte); // já aberto: nada de novo
		expect(ouvinte).toHaveBeenCalledOnce();
		parar();
	});

	it('a falha das afiliações não derruba o cubo: ele abre sem lugares, com o erro para a Geografia', async () => {
		const { fonte, pedidos } = fonteFalsa({ afiliacoes: 1 });
		const aberto = await abrirCubo(fonte);
		expect(aberto).not.toBeNull();
		expect(aberto!.afiliacoes).toBeNull();
		expect(aberto!.erroAfiliacoes?.message).toContain('afiliacoes.json');
		expect(aberto!.cubo.contar(aberto!.cubo.falhas({ ...FILTROS_PADRAO }))).toBe(documentos.n);

		// "Tentar de novo" reabre, pede as afiliações outra vez e avisa quem ouve (a barra do recorte)
		const ouvinte = vi.fn();
		const parar = aoReabrir(ouvinte);
		const reaberto = await reabrirCubo(fonte);
		parar();
		expect(ouvinte).toHaveBeenCalledOnce();
		expect(pedidos.afiliacoes).toBe(2);
		expect(reaberto!.afiliacoes).not.toBeNull();
		expect(reaberto!.erroAfiliacoes).toBeNull();
		expect(await abrirCubo(fonte)).toBe(reaberto);
	});
});

describe('versão do mapa (a do laço)', () => {
	const tabela = decodificar(documentos);

	it('não muda com uma reexportação (outro gerado_em), só com as coordenadas', () => {
		expect(versaoDoMapa(decodificar(documentos))).toBe(versaoDoMapa(tabela));
		const reexportado = { ...manifesto, gerado_em: '2026-09-28T09:00:00Z' };
		expect(lacoVale(versaoDoMapa(tabela), tabela, reexportado)).toBe(true);
		// tópicos refeitos: outras coordenadas, outra versão, e o laço antigo ganha o aviso
		const x = documentos.colunas.x.map((v, i) => (i === 0 ? v + 0.5 : v));
		const refeito = decodificar({ ...documentos, colunas: { ...documentos.colunas, x } });
		expect(versaoDoMapa(refeito)).not.toBe(versaoDoMapa(tabela));
		expect(lacoVale(versaoDoMapa(tabela), refeito, manifesto)).toBe(false);
	});

	it('um laço de um link até a 1.0.1 (versão pelo manifesto) vale no mesmo manifesto', () => {
		const texto = `${manifesto.gerado_em}|${manifesto.contagens.topicos}`;
		let h = 0x811c9dc5;
		for (let i = 0; i < texto.length; i += 1) h = Math.imul(h ^ texto.charCodeAt(i), 0x01000193) >>> 0;
		const antiga = h.toString(36).slice(0, 6);
		expect(lacoVale(antiga, tabela, manifesto)).toBe(true);
		expect(lacoVale(antiga, tabela, { ...manifesto, gerado_em: '2026-09-28T09:00:00Z' })).toBe(false);
	});
});
