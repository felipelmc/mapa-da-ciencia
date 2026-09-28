/**
 * O `redes.json` e o `citacoes.json` em arrays tipados, com índices por documento e por pessoa (CSR), para a vista
 * Redes recalcular as arestas no recorte sem varrer listas de objetos: as pessoas de cada documento, os documentos
 * de cada pessoa, as citações internas e os citantes do cânone.
 *
 * Os documentos entram pelo índice em `documentos.json` (a mesma ordem da `TabelaDocumentos`). Uma pessoa repetida
 * no mesmo documento conta uma vez, como no Python (`pares_ponderados` usa o conjunto dos membros).
 */
import type { Citacoes, ColaboracaoAno, ComunidadeRede, MetricasRede, ObraCitada, Redes } from '$lib/contrato/tipos';
import type { FonteDeDados } from './fonte';

/** Lista de listas compacta: os itens da linha `i` são `itens[inicio[i] .. inicio[i+1])`. */
export interface Csr {
	inicio: Int32Array;
	itens: Int32Array;
}

/** Agrupa os pares (linha, item) por linha, sem itens repetidos numa linha e em ordem crescente. */
export function agrupar(nLinhas: number, linha: ArrayLike<number>, item: ArrayLike<number>): Csr {
	const pares = Array.from({ length: linha.length }, (_, k) => k)
		.filter((k) => linha[k] >= 0 && linha[k] < nLinhas && item[k] >= 0)
		.sort((p, q) => linha[p] - linha[q] || item[p] - item[q]);
	const inicio = new Int32Array(nLinhas + 1);
	const itens: number[] = [];
	let anterior = -1;
	let itemAnterior = -1;
	for (const k of pares) {
		if (linha[k] === anterior && item[k] === itemAnterior) continue;
		anterior = linha[k];
		itemAnterior = item[k];
		inicio[linha[k] + 1] += 1;
		itens.push(item[k]);
	}
	for (let i = 0; i < nLinhas; i += 1) inicio[i + 1] += inicio[i];
	return { inicio, itens: Int32Array.from(itens) };
}

export interface TabelaPessoas {
	n: number;
	ids: string[];
	nomes: string[];
	/** Documentos no corpus inteiro. */
	documentos: Int32Array;
	/** Coautores distintos no corpus inteiro. */
	grau: Int32Array;
	/** Comunidade na rede de coautoria (id em `comunidades`), ou −1 nas pequenas. */
	comunidade: Int32Array;
	/** Posição no desenho; `NaN` para quem nunca teve coautor (fica fora do desenho). */
	x: Float64Array;
	y: Float64Array;
	indice: Map<string, number>;
}

export interface TabelaInstituicoesRede {
	n: number;
	/** Os mesmos ids de `afiliacoes.json`. */
	ids: string[];
	grau: Int32Array;
	comunidade: Int32Array;
	x: Float64Array;
	y: Float64Array;
	indice: Map<string, number>;
}

export interface TabelaRedes {
	pessoas: TabelaPessoas;
	/** Pessoas de cada documento. */
	pessoasDoDoc: Csr;
	/** Documentos de cada pessoa. */
	docsDaPessoa: Csr;
	/** `null` quando o projeto não tem a geografia em dia (sem a rede de instituições). */
	instituicoes: TabelaInstituicoesRede | null;
	/** Comunidades de cada rede, pelo id. */
	comunidades: { coautoria: Map<number, ComunidadeRede>; instituicoes: Map<number, ComunidadeRede> };
	metricas: Record<string, MetricasRede>;
	colaboracao: ColaboracaoAno[];
}

const numeroOuNaN = (v: number | null) => (v === null || v === undefined ? NaN : v);

export function decodificarRedes(r: Redes, nDocs: number): TabelaRedes {
	const p = r.pessoas;
	const n = p.id.length;
	const inst = r.instituicoes ?? null;
	const comunidades = { coautoria: new Map<number, ComunidadeRede>(), instituicoes: new Map<number, ComunidadeRede>() };
	for (const c of r.comunidades ?? []) comunidades[c.rede].set(c.id, c);
	return {
		pessoas: {
			n,
			ids: p.id,
			nomes: p.nome,
			documentos: Int32Array.from(p.documentos),
			grau: Int32Array.from(p.grau),
			comunidade: Int32Array.from(p.comunidade),
			x: Float64Array.from(p.x, numeroOuNaN),
			y: Float64Array.from(p.y, numeroOuNaN),
			indice: new Map(p.id.map((id, i) => [id, i]))
		},
		pessoasDoDoc: agrupar(nDocs, r.autorias.doc, r.autorias.pessoa),
		docsDaPessoa: agrupar(n, r.autorias.pessoa, r.autorias.doc),
		instituicoes: inst
			? {
					n: inst.id.length,
					ids: inst.id,
					grau: Int32Array.from(inst.grau),
					comunidade: Int32Array.from(inst.comunidade),
					x: Float64Array.from(inst.x),
					y: Float64Array.from(inst.y),
					indice: new Map(inst.id.map((id, i) => [id, i]))
				}
			: null,
		comunidades,
		metricas: r.metricas ?? {},
		colaboracao: r.colaboracao ?? []
	};
}

export interface TabelaCitacoes {
	/** Referências de cada documento no OpenAlex; −1 quando o documento não casou com o OpenAlex. */
	nReferencias: Int32Array;
	/** Citações internas: o documento `de[k]` cita o documento `para[k]`. */
	de: Int32Array;
	para: Int32Array;
	canone: ObraCitada[];
	/** Pares (documento, obra do cânone). */
	citanteDoc: Int32Array;
	citanteObra: Int32Array;
	fluxo: number[][];
	cobertura: Record<string, number>;
}

export function decodificarCitacoes(c: Citacoes): TabelaCitacoes {
	return {
		nReferencias: Int32Array.from(c.n_referencias),
		de: Int32Array.from(c.internas.de),
		para: Int32Array.from(c.internas.para),
		canone: c.canone,
		citanteDoc: Int32Array.from(c.canone_citantes.doc),
		citanteObra: Int32Array.from(c.canone_citantes.obra),
		fluxo: c.fluxo_macrotemas,
		cobertura: c.cobertura ?? {}
	};
}

const redes = new WeakMap<FonteDeDados, Promise<TabelaRedes | null>>();
const citacoes = new WeakMap<FonteDeDados, Promise<TabelaCitacoes | null>>();

/** As redes decodificadas, uma vez por fonte (`null`, sem pedido, quando o projeto não rodou `mapa redes`). */
export function abrirRedes(fonte: FonteDeDados, nDocs: number): Promise<TabelaRedes | null> {
	let p = redes.get(fonte);
	if (!p) {
		p = fonte.redes().then((r) => (r ? decodificarRedes(r, nDocs) : null));
		p.catch(() => redes.delete(fonte));
		redes.set(fonte, p);
	}
	return p;
}

/** As citações decodificadas, uma vez por fonte. */
export function abrirCitacoes(fonte: FonteDeDados): Promise<TabelaCitacoes | null> {
	let p = citacoes.get(fonte);
	if (!p) {
		p = fonte.citacoes().then((c) => (c ? decodificarCitacoes(c) : null));
		p.catch(() => citacoes.delete(fonte));
		citacoes.set(fonte, p);
	}
	return p;
}
