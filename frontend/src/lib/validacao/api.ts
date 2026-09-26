/**
 * A codificação da amostra de validação pela API do painel local (`servidor/validacao.py`):
 *
 * - `lerFila(nome)`: a amostra na ordem da fila do codificador, com o codebook e as respostas já dadas (nunca as
 *   de um modelo: a codificação é cega);
 * - `Gravador`: grava as respostas de cada ficha. Cada mudança vai primeiro para o `localStorage` (a fila de
 *   pendências) e depois para a API; se a API falhar (servidor parado, rede), as pendências ficam guardadas e são
 *   reenviadas na próxima mudança ou quando a página voltar a ficar on-line. Nada se perde num reload.
 * - `lerMetricas()`: a concordância calculada na hora (o formato de `validacao.json`).
 *
 * Os caminhos são relativos à página (`./api/...`), como os dados: funcionam na raiz e num subcaminho.
 */
import type { CodebookContrato, Validacao } from '$lib/contrato/tipos';
import { ErroDaApi, pedirApi } from '$lib/dados/pedir';

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

export { ErroDaApi } from '$lib/dados/pedir';

const pedir = pedirApi;

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

/** Guarda e envia as respostas de um codificador, com as pendências no `localStorage`. */
export class Gravador {
	readonly codificador: string;
	readonly chave: string;
	#enviando = false;
	#aoMudar: (pendentes: number, erro: string | null) => void;

	constructor(codificador: string, aoMudar: (pendentes: number, erro: string | null) => void = () => {}) {
		this.codificador = codificador;
		this.chave = `mapa.codificacao.pendentes.${codificador}`;
		this.#aoMudar = aoMudar;
	}

	pendencias(): Record<string, Pendencia> {
		try {
			return JSON.parse(localStorage.getItem(this.chave) ?? '{}');
		} catch {
			return {};
		}
	}

	#guardar(p: Record<string, Pendencia>) {
		try {
			if (Object.keys(p).length) localStorage.setItem(this.chave, JSON.stringify(p));
			else localStorage.removeItem(this.chave);
		} catch {
			/* sem localStorage (modo privado): segue só com a API */
		}
	}

	/** Registra as respostas de uma ficha e tenta enviar tudo o que está pendente. */
	async gravar(doc: string, respostas: Record<string, RespostaVariavel>, completa: boolean): Promise<void> {
		const p = this.pendencias();
		p[doc] = { respostas, completa: completa || !!p[doc]?.completa };
		this.#guardar(p);
		await this.enviar();
	}

	/** Envia as pendências, uma ficha por vez. Devolve os problemas de validação, se a API recusar alguma. */
	async enviar(): Promise<void> {
		if (this.#enviando) return;
		this.#enviando = true;
		let erro: string | null = null;
		try {
			// o que chegar enquanto envia entra na volta seguinte; a rede fora do ar interrompe tudo
			for (let volta = 0, parar = false; volta < 10 && !parar; volta += 1) {
				const entradas = Object.entries(this.pendencias());
				if (!entradas.length) break;
				for (const [doc, { respostas, completa }] of entradas) {
					try {
						await pedir(`api/validacao/codificacoes/${encodeURIComponent(doc)}`, {
							method: 'PUT',
							body: JSON.stringify({ codificador: this.codificador, respostas, completa })
						});
					} catch (e) {
						if (e instanceof ErroDaApi && e.status === 422) {
							// resposta inválida (ex.: variável que saiu do codebook): não adianta reenviar
							erro = `Não foi possível gravar ${doc}: ${e.message}`;
						} else {
							erro = 'Sem conexão com o painel: as respostas ficam guardadas neste navegador e vão quando ele voltar.';
							parar = true;
							break;
						}
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
