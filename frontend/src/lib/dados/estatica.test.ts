import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import type { Manifesto } from '$lib/contrato/tipos';
import { abrirFonte, ErroDeDados, FonteApi, FonteEstatica, fragmentoDe } from './index';

const EXEMPLO = join(import.meta.dirname, '..', '..', '..', '..', 'contrato', 'exemplo', 'dados');
const BASE = 'http://teste/dados/';

/** `fetch` falso que serve uma pasta do disco (ou um dicionário em memória) e registra os pedidos. */
function servir(arquivos: string | Record<string, unknown>) {
	const pedidos: string[] = [];
	const fetch = vi.fn(async (entrada: RequestInfo | URL) => {
		const url = String(entrada);
		pedidos.push(url.replace(BASE, ''));
		const caminho = url.replace(BASE, '');
		let corpo: string | null = null;
		if (typeof arquivos === 'string') {
			const arquivo = join(arquivos, caminho);
			if (existsSync(arquivo)) corpo = readFileSync(arquivo, 'utf8');
		} else if (caminho in arquivos) {
			corpo = JSON.stringify(arquivos[caminho]);
		}
		return corpo === null ? new Response('não encontrado', { status: 404 }) : new Response(corpo);
	});
	return { fetch: fetch as unknown as typeof globalThis.fetch, pedidos };
}

/** Manifesto de um projeto recém-criado pelo `mapa novo`: só ele existe. */
const MANIFESTO_VAZIO: Manifesto = {
	versao_contrato: '1.0',
	api: true,
	gerado_em: '2026-09-26T12:00:00Z',
	projeto: { nome: 'novo', titulo: 'Projeto novo', descricao: '' },
	recorte: { anos: [2015, 2024], fontes: ['scielo:scl'], idioma_analise: 'en', idioma_exibicao: 'pt' },
	contagens: { documentos: 0, topicos: 0, classificados: 0, validados: 0, com_afiliacao: 0 },
	arquivos: ['manifesto'],
	execucao: { versao_pacote: '0.1.0', modelos: {}, hash_codebook: null, sementes: {}, duracao_s: {} },
	licencas: {}
};

describe('FonteEstatica com o exemplo sintético', () => {
	it('lê cada arquivo uma vez só (cache)', async () => {
		const { fetch, pedidos } = servir(EXEMPLO);
		const fonte = new FonteEstatica({ base: BASE, fetch });
		const [a, b] = await Promise.all([fonte.topicos(), fonte.topicos()]);
		expect(a).toBe(b);
		expect(a?.topicos.length).toBeGreaterThan(0);
		await fonte.topicos();
		expect(pedidos).toEqual(['manifesto.json', 'topicos.json']);
	});

	it('busca o detalhe no fragmento certo e reaproveita o fragmento', async () => {
		const { fetch, pedidos } = servir(EXEMPLO);
		const fonte = new FonteEstatica({ base: BASE, fetch });
		const detalhe = await fonte.detalhe('exemplo:00000');
		expect(detalhe?.autores.length).toBeGreaterThan(0);
		expect(pedidos).toContain(`detalhes/${fragmentoDe('exemplo:00000')}.json`);

		// Outro documento do mesmo fragmento não gera nova requisição.
		const documentos = await fonte.documentos();
		const vizinho = documentos!.colunas.id.find(
			(id) => id !== 'exemplo:00000' && fragmentoDe(id) === fragmentoDe('exemplo:00000')
		)!;
		const antes = pedidos.length;
		expect(await fonte.detalhe(vizinho)).not.toBeNull();
		expect(pedidos.length).toBe(antes);

		expect(await fonte.detalhe('nao:existe')).toBeNull();
	});

	it('abrirFonte escolhe a fonte pelo manifesto.api', async () => {
		const estatico = await abrirFonte({ base: BASE, fetch: servir(EXEMPLO).fetch });
		expect(estatico.manifesto.api).toBe(false);
		expect(estatico.fonte).toBeInstanceOf(FonteEstatica);
		expect(estatico.fonte).not.toBeInstanceOf(FonteApi);
		expect(estatico.fonte.capacidades).toEqual({ escrita: false, aoVivo: false });

		const painel = servir({ 'manifesto.json': MANIFESTO_VAZIO });
		const comApi = await abrirFonte({ base: BASE, fetch: painel.fetch });
		expect(comApi.fonte).toBeInstanceOf(FonteApi);
		expect(comApi.fonte.capacidades.escrita).toBe(true);
		// O manifesto lido para escolher a fonte é reaproveitado.
		await comApi.fonte.manifesto();
		expect(painel.pedidos).toEqual(['manifesto.json']);
	});
});

describe('FonteEstatica com um projeto vazio', () => {
	it('devolve null para os arquivos ausentes sem fazer requisição', async () => {
		const { fetch, pedidos } = servir({ 'manifesto.json': MANIFESTO_VAZIO });
		const fonte = new FonteEstatica({ base: BASE, fetch });

		expect((await fonte.manifesto()).contagens.documentos).toBe(0);
		expect(await fonte.revistas()).toBeNull();
		expect(await fonte.documentos()).toBeNull();
		expect(await fonte.afiliacoes()).toBeNull();
		expect(await fonte.topicos()).toBeNull();
		expect(await fonte.codebook()).toBeNull();
		expect(await fonte.classificacoes()).toBeNull();
		expect(await fonte.validacao()).toBeNull();
		expect(await fonte.detalhe('exemplo:00000')).toBeNull();
		expect(await fonte.tem('topicos')).toBe(false);

		expect(pedidos).toEqual(['manifesto.json']);
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('só pede os arquivos listados no manifesto', async () => {
		const manifesto = { ...MANIFESTO_VAZIO, arquivos: ['manifesto', 'revistas'] };
		const revistas = { versao_contrato: '1.0', revistas: [] };
		const { fetch, pedidos } = servir({ 'manifesto.json': manifesto, 'revistas.json': revistas });
		const fonte = new FonteEstatica({ base: BASE, fetch });
		expect(await fonte.revistas()).toEqual(revistas);
		expect(await fonte.topicos()).toBeNull();
		expect(pedidos).toEqual(['manifesto.json', 'revistas.json']);
	});
});

describe('FonteEstatica com erros', () => {
	it('explica a falha e permite tentar de novo', async () => {
		let falhar = true;
		const fetch = vi.fn(async () =>
			falhar ? new Response('', { status: 503 }) : new Response(JSON.stringify(MANIFESTO_VAZIO))
		) as unknown as typeof globalThis.fetch;
		const fonte = new FonteEstatica({ base: BASE, fetch });

		const erro = await fonte.manifesto().catch((e: unknown) => e);
		expect(erro).toBeInstanceOf(ErroDeDados);
		expect((erro as ErroDeDados).status).toBe(503);
		expect((erro as ErroDeDados).message).toContain('manifesto.json');

		falhar = false;
		expect((await fonte.manifesto()).projeto.nome).toBe('novo');
	});

	it('recusa um contrato de versão maior diferente', async () => {
		const { fetch } = servir({ 'manifesto.json': { ...MANIFESTO_VAZIO, versao_contrato: '2.0' } });
		const fonte = new FonteEstatica({ base: BASE, fetch });
		await expect(fonte.manifesto()).rejects.toThrow(/contrato 2\.0/);
	});
});
