/**
 * O filtro cruzado: quais documentos o recorte deixa passar, e contagens por ano, tópico, revista e lugar.
 *
 * Cada dimensão do recorte (ano, revista, tópico, busca, laço, UF, país, instituição) tem um bit. Para cada
 * documento, `falhas[i]` guarda os bits das dimensões que ele NÃO atende. Assim:
 *
 * - o documento passa no recorte inteiro quando `falhas[i] === 0`;
 * - passa em tudo menos nas dimensões `m` quando `(falhas[i] & ~m) === 0`.
 *
 * É o truque do crossfilter: cada vista agrega **excluindo a própria dimensão** (o fluxo por ano ignora o filtro
 * de anos, para mostrar o período inteiro com o intervalo destacado; o mapa das UFs ignora o filtro de UF, para
 * as outras UFs continuarem clicáveis), e tudo sai de uma passada pelos documentos.
 *
 * Os filtros de lugar valem por documento: um documento passa em `uf=SP` se tiver alguma afiliação em SP. O peso
 * fracionário só entra nas somas geográficas (`somarAfiliacoesPor`); no mapa e nos tópicos, cada documento vale 1.
 *
 * Os bits de uma dimensão só são recalculados quando o valor dela muda (a busca e o laço são os mais caros).
 */
import type { Topicos } from '$lib/contrato/tipos';
import type { Filtros } from '$lib/estado/url';
import { dentro, type Ponto } from '$lib/graficos/geometria';
import type { TabelaAfiliacoes } from './afiliacoes';
import { buscar, indiceDe } from './busca';
import { paraNdc, type TabelaDocumentos } from './documentos';

export const D = { ANO: 1, REVISTA: 2, TOPICO: 4, BUSCA: 8, LACO: 16, UF: 32, PAIS: 64, INST: 128 } as const;
export type Dimensao = (typeof D)[keyof typeof D];

type Chaves = Record<Dimensao, string>;

export interface TopicoPorAno {
	/** Ids dos tópicos, na ordem das linhas de `n` (a última linha é "sem tópico"). */
	ids: number[];
	anos: number[];
	/** (ids.length + 1) × anos.length, em ordem de linha: `n[linha * anos.length + coluna]`. */
	n: Float64Array;
	/** Documentos do recorte em cada ano (o denominador da participação). */
	total: Float64Array;
}

export class Cubo {
	readonly t: TabelaDocumentos;
	readonly topicos: Topicos;
	readonly a: TabelaAfiliacoes | null;
	#falhas: Uint8Array;
	#chaves: Chaves = { 1: '', 2: '', 4: '', 8: '', 16: '', 32: '', 64: '', 128: '' };
	#linhaTopico = new Map<number, number>();

	constructor(t: TabelaDocumentos, topicos: Topicos, a: TabelaAfiliacoes | null = null) {
		this.t = t;
		this.topicos = topicos;
		this.a = a;
		this.#falhas = new Uint8Array(t.n);
		topicos.topicos.forEach((x, i) => this.#linhaTopico.set(x.id, i));
	}

	/** Os bits de falha de cada documento para o recorte `f`. Devolve uma cópia (bom para `$derived`). */
	falhas(f: Filtros): Uint8Array {
		const chaves: Chaves = {
			[D.ANO]: f.anos ? `${f.anos[0]}-${f.anos[1]}` : '',
			[D.REVISTA]: f.revistas.join(','),
			[D.TOPICO]: f.topicos.join(','),
			[D.BUSCA]: f.busca,
			[D.LACO]: f.laco ? f.laco.pontos.join(';') : '',
			[D.UF]: this.a ? f.uf.join(',') : '',
			[D.PAIS]: this.a ? f.pais.join(',') : '',
			[D.INST]: this.a ? f.inst.join(',') : ''
		} as Chaves;
		for (const bit of Object.values(D)) {
			if (chaves[bit] === this.#chaves[bit]) continue;
			this.#chaves[bit] = chaves[bit];
			this.#marcar(bit, chaves[bit] ? this.#teste(bit, f) : null);
		}
		return this.#falhas.slice();
	}

	/** Documentos que passam (ignorando as dimensões em `exceto`). */
	contar(falhas: Uint8Array, exceto = 0): number {
		const m = ~exceto & 0xff;
		let n = 0;
		for (let i = 0; i < falhas.length; i += 1) if ((falhas[i] & m) === 0) n += 1;
		return n;
	}

	/** Índices dos documentos que passam, ou `null` quando todos passam (o atalho do mapa). */
	indices(falhas: Uint8Array, exceto = 0): number[] | null {
		const m = ~exceto & 0xff;
		const saida: number[] = [];
		for (let i = 0; i < falhas.length; i += 1) if ((falhas[i] & m) === 0) saida.push(i);
		return saida.length === falhas.length ? null : saida;
	}

	/** Documentos que passam, por célula (`celula(i)` devolve a célula do documento, ou -1 para ignorar). */
	contarPor(falhas: Uint8Array, exceto: number, nCelulas: number, celula: (i: number) => number): Float64Array {
		const m = ~exceto & 0xff;
		const saida = new Float64Array(nCelulas);
		for (let i = 0; i < falhas.length; i += 1) {
			if ((falhas[i] & m) !== 0) continue;
			const c = celula(i);
			if (c >= 0) saida[c] += 1;
		}
		return saida;
	}

	/** Soma dos pesos fracionários das afiliações dos documentos que passam, por célula da linha. */
	somarAfiliacoesPor(
		falhas: Uint8Array,
		exceto: number,
		nCelulas: number,
		celula: (linha: number) => number
	): Float64Array {
		const saida = new Float64Array(nCelulas);
		const a = this.a;
		if (!a) return saida;
		const m = ~exceto & 0xff;
		for (let linha = 0; linha < a.n; linha += 1) {
			if ((falhas[a.doc[linha]] & m) !== 0) continue;
			const c = celula(linha);
			if (c >= 0) saida[c] += a.peso[linha];
		}
		return saida;
	}

	/** Documentos que passam e têm alguma linha em cada célula (a contagem inteira dos lugares). */
	documentosPorLugar(
		falhas: Uint8Array,
		exceto: number,
		nCelulas: number,
		celula: (linha: number) => number
	): Float64Array {
		const saida = new Float64Array(nCelulas);
		const a = this.a;
		if (!a) return saida;
		const m = ~exceto & 0xff;
		const vistos = new Int32Array(nCelulas).fill(-1);
		for (let d = 0; d < falhas.length; d += 1) {
			if ((falhas[d] & m) !== 0) continue;
			for (let k = a.inicio[d]; k < a.inicio[d + 1]; k += 1) {
				const c = celula(a.linhas[k]);
				if (c >= 0 && vistos[c] !== d) {
					vistos[c] = d;
					saida[c] += 1;
				}
			}
		}
		return saida;
	}

	/** Documentos por tópico e ano (mais a linha "sem tópico") e o total de cada ano. */
	topicoPorAno(falhas: Uint8Array, exceto: number): TopicoPorAno {
		const anos = this.topicos.anos;
		const ids = this.topicos.topicos.map((x) => x.id);
		const k = ids.length;
		const nAnos = anos.length;
		const primeiro = anos[0];
		const n = new Float64Array((k + 1) * nAnos);
		const total = new Float64Array(nAnos);
		const m = ~exceto & 0xff;
		for (let i = 0; i < falhas.length; i += 1) {
			if ((falhas[i] & m) !== 0) continue;
			const coluna = this.t.ano[i] - primeiro;
			if (coluna < 0 || coluna >= nAnos) continue;
			const linha = this.#linhaTopico.get(this.t.topico[i]) ?? k;
			n[linha * nAnos + coluna] += 1;
			total[coluna] += 1;
		}
		return { ids, anos, n, total };
	}

	// ---------------------------------------------------------------- bits de cada dimensão

	#marcar(bit: number, passa: ((i: number) => boolean) | null): void {
		const falhas = this.#falhas;
		const apagar = ~bit & 0xff;
		for (let i = 0; i < falhas.length; i += 1) {
			falhas[i] = passa === null || passa(i) ? falhas[i] & apagar : falhas[i] | bit;
		}
	}

	#teste(bit: number, f: Filtros): (i: number) => boolean {
		const t = this.t;
		switch (bit) {
			case D.ANO: {
				const [de, ate] = f.anos!;
				return (i) => t.ano[i] >= de && t.ano[i] <= ate;
			}
			case D.REVISTA: {
				const revistas = new Set(f.revistas.map((r) => t.revistas.indexOf(r)));
				return (i) => revistas.has(t.revista[i]);
			}
			case D.TOPICO: {
				const topicos = new Set(f.topicos);
				return (i) => topicos.has(t.topico[i]);
			}
			case D.BUSCA: {
				const achados = new Set(buscar(indiceDe(t), f.busca));
				return (i) => achados.has(i);
			}
			case D.LACO: {
				const poligono = f.laco!.pontos.map(([x, y]) => paraNdc(t.escala, x, y) as Ponto);
				return (i) => dentro(t.x[i], t.y[i], poligono);
			}
			default:
				return this.#testeDeLugar(bit, f);
		}
	}

	#testeDeLugar(bit: number, f: Filtros): (i: number) => boolean {
		const a = this.a!;
		const [coluna, valores, dicionario] =
			bit === D.UF
				? [a.uf, f.uf, a.ufs]
				: bit === D.PAIS
					? [a.pais, f.pais, a.paises]
					: [a.inst, f.inst, a.instituicoes.map((x) => x.id)];
		const aceitos = new Set(valores.map((v) => dicionario.indexOf(v)).filter((i) => i >= 0));
		return (d) => {
			for (let k = a.inicio[d]; k < a.inicio[d + 1]; k += 1) if (aceitos.has(coluna[a.linhas[k]])) return true;
			return false;
		};
	}
}
