import type {
	Afiliacoes,
	Agregados,
	Classificacoes,
	CodebookContrato,
	Detalhe,
	Documentos,
	Fragmento,
	Manifesto,
	Revistas,
	Topicos,
	Validacao
} from '$lib/contrato/tipos';
import {
	ErroDeDados,
	VERSAO_MAIOR_CONTRATO,
	type Capacidades,
	type FonteDeDados,
	type NomeArquivo
} from './fonte';
import { fragmentoDe } from './fragmentos';

export interface OpcoesFonte {
	/**
	 * Pasta dos arquivos, com ou sem barra final. O padrão, `./dados/`, é relativo à página:
	 * funciona na raiz (`/dados/`, no `mapa painel`) e num subcaminho (`/sub/dados/`).
	 */
	base?: string;
	/** `fetch` alternativo, para os testes. */
	fetch?: typeof fetch;
	/** Manifesto já carregado, para não pedir de novo. */
	manifesto?: Manifesto;
}

/**
 * Lê o contrato de arquivos JSON estáticos. Cada arquivo é pedido uma vez só: a promessa
 * fica em cache e é descartada se falhar, para permitir uma nova tentativa.
 */
export class FonteEstatica implements FonteDeDados {
	readonly capacidades: Capacidades = { escrita: false, aoVivo: false };

	readonly #base: string;
	readonly #fetch: typeof fetch;
	readonly #cache = new Map<string, Promise<unknown>>();

	constructor(opcoes: OpcoesFonte = {}) {
		const base = opcoes.base ?? './dados/';
		this.#base = base.endsWith('/') ? base : `${base}/`;
		// Sem o bind, o fetch do navegador reclama de "Illegal invocation".
		this.#fetch = opcoes.fetch ?? globalThis.fetch.bind(globalThis);
		if (opcoes.manifesto) this.#cache.set('manifesto.json', Promise.resolve(opcoes.manifesto));
	}

	manifesto(): Promise<Manifesto> {
		return this.#carregar<Manifesto>('manifesto.json');
	}

	async tem(arquivo: NomeArquivo): Promise<boolean> {
		if (arquivo === 'manifesto') return true;
		return (await this.manifesto()).arquivos.includes(arquivo);
	}

	revistas(): Promise<Revistas | null> {
		return this.#seHouver<Revistas>('revistas');
	}

	documentos(): Promise<Documentos | null> {
		return this.#seHouver<Documentos>('documentos');
	}

	afiliacoes(): Promise<Afiliacoes | null> {
		return this.#seHouver<Afiliacoes>('afiliacoes');
	}

	agregados(): Promise<Agregados | null> {
		return this.#seHouver<Agregados>('agregados');
	}

	topicos(): Promise<Topicos | null> {
		return this.#seHouver<Topicos>('topicos');
	}

	codebook(): Promise<CodebookContrato | null> {
		return this.#seHouver<CodebookContrato>('codebook');
	}

	classificacoes(): Promise<Classificacoes | null> {
		return this.#seHouver<Classificacoes>('classificacoes');
	}

	validacao(): Promise<Validacao | null> {
		return this.#seHouver<Validacao>('validacao');
	}

	async detalhe(id: string): Promise<Detalhe | null> {
		if (!(await this.tem('detalhes'))) return null;
		const fragmento = await this.#carregar<Fragmento>(`detalhes/${fragmentoDe(id)}.json`);
		return fragmento.documentos[id] ?? null;
	}

	/** Carrega `<nome>.json` só se o manifesto listar o arquivo; senão, `null` sem requisição. */
	async #seHouver<T>(nome: NomeArquivo): Promise<T | null> {
		if (!(await this.tem(nome))) return null;
		return this.#carregar<T>(`${nome}.json`);
	}

	#carregar<T>(caminho: string): Promise<T> {
		let promessa = this.#cache.get(caminho) as Promise<T> | undefined;
		if (!promessa) {
			promessa = this.#buscar<T>(caminho);
			this.#cache.set(caminho, promessa);
			promessa.catch(() => this.#cache.delete(caminho));
		}
		return promessa;
	}

	async #buscar<T>(caminho: string): Promise<T> {
		const url = this.#base + caminho;
		let resposta: Response;
		try {
			resposta = await this.#fetch(url);
		} catch (e) {
			throw new ErroDeDados(`Não foi possível buscar ${url}: ${(e as Error).message}`, url);
		}
		if (!resposta.ok) {
			throw new ErroDeDados(`Não foi possível carregar ${url} (HTTP ${resposta.status}).`, url, resposta.status);
		}
		let dados: unknown;
		try {
			dados = await resposta.json();
		} catch {
			throw new ErroDeDados(`${url} não é um JSON válido.`, url, resposta.status);
		}
		const versao = (dados as { versao_contrato?: unknown } | null)?.versao_contrato;
		if (typeof versao === 'string' && versao.split('.')[0] !== VERSAO_MAIOR_CONTRATO) {
			throw new ErroDeDados(
				`${url} usa o contrato ${versao}, e esta interface lê a versão ${VERSAO_MAIOR_CONTRATO}.x. ` +
					'Atualize o mapa-da-ciencia ou regenere os dados.',
				url,
				resposta.status
			);
		}
		return dados as T;
	}
}
