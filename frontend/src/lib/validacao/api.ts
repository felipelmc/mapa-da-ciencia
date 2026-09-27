/**
 * A codificação da amostra de validação pela API do painel local (`servidor/validacao.py`):
 *
 * - `lerFila(nome)`: a amostra na ordem da fila do codificador, com o codebook e as respostas já dadas (nunca as
 *   de um modelo: a codificação é cega);
 * - `Gravador`: grava as respostas de cada ficha. Cada mudança vai primeiro para o `localStorage` (a fila de
 *   pendências, por projeto e codificador) e depois para a API; se o painel não responder (servidor parado, rede),
 *   as pendências ficam guardadas e são reenviadas na próxima mudança ou quando a página voltar a ficar on-line.
 *   Nada se perde num reload. Uma ficha que o painel recusa (fora da amostra, resposta inválida) é avisada e sai da
 *   fila, sem travar as outras. Sem `localStorage` (dados do site bloqueados), as pendências ficam na memória.
 * - `lerMetricas()`: a concordância calculada na hora (o formato de `validacao.json`).
 *
 * Os caminhos são relativos à página (`./api/...`), como os dados: funcionam na raiz e num subcaminho.
 */
import type { CodebookContrato, Validacao } from '$lib/contrato/tipos';

export type Valor = string | boolean | string[] | null;

export interface RespostaVariavel {
	valor: Valor;
	evidencia: string;
	incerto: boolean;
	nota: string;
}

export interface Ficha {
	doc: string;
	titulo: string | null;
	resumo: string;
	idioma: string;
	respostas: Record<string, RespostaVariavel>;
	completa: boolean;
}

export interface Fila {
	codificador: string;
	tipo: 'humano' | 'referencia' | null;
	amostra: { n: number; estratificar_por: string; semente: number };
	codebook: CodebookContrato;
	fila: Ficha[];
}

export const NOME_VALIDO = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$/;

export class ErroDaApi extends Error {
	readonly status: number;
	readonly problemas: string[];

	constructor(mensagem: string, status: number, problemas: string[] = []) {
		super(mensagem);
		this.name = 'ErroDaApi';
		this.status = status;
		this.problemas = problemas;
	}
}

const url = (caminho: string) => new URL(caminho, document.baseURI).toString();

async function pedir<T>(caminho: string, init?: RequestInit): Promise<T> {
	const r = await fetch(url(caminho), { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
	if (!r.ok) {
		const corpo = await r.json().catch(() => null);
		const detalhe = corpo?.detail;
		const problemas: string[] = Array.isArray(detalhe?.problemas) ? detalhe.problemas : [];
		throw new ErroDaApi(
			typeof detalhe === 'string' ? detalhe : problemas.join('; ') || r.statusText,
			r.status,
			problemas
		);
	}
	return r.json();
}

export function lerFila(codificador: string): Promise<Fila> {
	return pedir(`api/validacao/fila?codificador=${encodeURIComponent(codificador)}`);
}

export function lerMetricas(): Promise<Validacao> {
	return pedir('api/validacao/metricas');
}

interface Pendencia {
	respostas: Record<string, RespostaVariavel>;
	completa: boolean;
}

/** Guarda e envia as respostas de um codificador, com as pendências no `localStorage` (ou na memória). */
export class Gravador {
	readonly codificador: string;
	readonly chave: string;
	#enviando = false;
	#memoria: Record<string, Pendencia> | null = null; // em uso quando o localStorage não funciona
	#aoMudar: (pendentes: number, erro: string | null) => void;

	constructor(
		projeto: string,
		codificador: string,
		aoMudar: (pendentes: number, erro: string | null) => void = () => {}
	) {
		this.codificador = codificador;
		this.chave = `mapa.codificacao.pendentes.${projeto}.${codificador}`;
		this.#aoMudar = aoMudar;
	}

	pendencias(): Record<string, Pendencia> {
		if (this.#memoria) return structuredClone(this.#memoria);
		let guardado: string | null;
		try {
			guardado = localStorage.getItem(this.chave);
		} catch {
			this.#memoria = {};
			return {};
		}
		try {
			return JSON.parse(guardado ?? '{}');
		} catch {
			return {};
		}
	}

	#guardar(p: Record<string, Pendencia>) {
		if (!this.#memoria) {
			try {
				if (Object.keys(p).length) localStorage.setItem(this.chave, JSON.stringify(p));
				else localStorage.removeItem(this.chave);
				return;
			} catch {
				/* sem localStorage (dados do site bloqueados, cota cheia): as pendências passam para a memória */
			}
		}
		this.#memoria = structuredClone(p);
	}

	/** Registra as respostas de uma ficha e tenta enviar tudo o que está pendente. */
	async gravar(doc: string, respostas: Record<string, RespostaVariavel>, completa: boolean): Promise<void> {
		const p = this.pendencias();
		p[doc] = { respostas, completa: completa || !!p[doc]?.completa };
		this.#guardar(p);
		await this.enviar();
	}

	/** Envia as pendências, uma ficha por vez. Sem resposta do painel, para e guarda tudo; uma ficha recusada sai
	 * da fila com um aviso; um erro do servidor deixa a ficha para a próxima vez e segue com as outras. */
	async enviar(): Promise<void> {
		if (this.#enviando) return;
		this.#enviando = true;
		let erro: string | null = null;
		const adiadas = new Set<string>();
		try {
			// o que chegar enquanto envia entra na volta seguinte
			for (let volta = 0, parar = false; volta < 10 && !parar; volta += 1) {
				const entradas = Object.entries(this.pendencias()).filter(([doc]) => !adiadas.has(doc));
				if (!entradas.length) break;
				for (const [doc, { respostas, completa }] of entradas) {
					try {
						await pedir(`api/validacao/codificacoes/${encodeURIComponent(doc)}`, {
							method: 'PUT',
							body: JSON.stringify({ codificador: this.codificador, respostas, completa })
						});
					} catch (e) {
						if (!(e instanceof ErroDaApi)) {
							erro = 'Sem conexão com o painel: as respostas ficam guardadas neste navegador e vão quando ele voltar.';
							parar = true;
							break;
						}
						if (e.status >= 500) {
							erro = `O painel não conseguiu gravar ${doc} (${e.message}); a ficha fica guardada e vai na próxima vez.`;
							adiadas.add(doc);
							continue;
						}
						// recusada (fora da amostra, resposta inválida): não adianta reenviar
						erro = `Não foi possível gravar ${doc}: ${e.message}`;
					}
					const resto = this.pendencias();
					if (JSON.stringify(resto[doc]) === JSON.stringify({ respostas, completa })) delete resto[doc];
					this.#guardar(resto);
				}
			}
		} finally {
			this.#enviando = false;
			this.#aoMudar(Object.keys(this.pendencias()).length, erro);
		}
	}
}
