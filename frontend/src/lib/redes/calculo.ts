/**
 * As redes no recorte, calculadas no navegador. Nada aqui depende do Svelte nem do DOM: a vista passa quem está no
 * recorte (`passa`) e recebe arestas, contagens e séries.
 *
 * O Python grava as redes do corpus inteiro (com o desenho), mas as arestas dependem do recorte: com `anos=2015-2020`,
 * duas pessoas que só escreveram juntas em 2012 não estão ligadas. Então as autorias vão para o contrato pelo
 * índice do documento, e cada rede é refeita aqui com a mesma regra do Python (`redes/grafos.pares_ponderados`),
 * que os testes conferem contra o gabarito (`agregados.json`) no corpus inteiro.
 */
import type { Topicos } from '$lib/contrato/tipos';
import type { TabelaAfiliacoes } from '$lib/dados/afiliacoes';
import type { Csr, TabelaCitacoes, TabelaRedes } from '$lib/dados/redes';

/** Se o documento `d` está no recorte; `null` = o corpus inteiro. */
export type Passa = ((d: number) => boolean) | null;

/** Membros de um documento (pessoas, instituições ou lugares), postos em `saida`; repetidos contam uma vez. */
export type Membros = (d: number, saida: number[]) => void;

export interface Arestas {
	n: number;
	/** Os dois nós de cada aresta, com `a < b`, em ordem de (a, b). */
	a: Int32Array;
	b: Int32Array;
	/** Soma de 1/(n−1) em cada documento de n membros distintos. */
	peso: Float64Array;
	/** Documentos em que o par aparece junto. */
	documentos: Int32Array;
}

function ordenar(a: number[], b: number[], peso: number[], documentos: number[]): Arestas {
	const ordem = a.map((_, k) => k).sort((p, q) => a[p] - a[q] || b[p] - b[q]);
	return {
		n: ordem.length,
		a: Int32Array.from(ordem, (k) => a[k]),
		b: Int32Array.from(ordem, (k) => b[k]),
		peso: Float64Array.from(ordem, (k) => peso[k]),
		documentos: Int32Array.from(ordem, (k) => documentos[k])
	};
}

/**
 * Os pares ponderados de `pares_ponderados` no Python: num documento com n membros distintos, cada par ganha
 * 1/(n−1) de peso e 1 documento. Assim cada membro distribui no máximo 1 entre os parceiros daquele documento, e um
 * artigo de dez autores não pesa mais que um de dois.
 */
export function paresPonderados(nDocs: number, nMembros: number, membros: Membros, passa: Passa): Arestas {
	const indice = new Map<number, number>();
	const a: number[] = [];
	const b: number[] = [];
	const peso: number[] = [];
	const documentos: number[] = [];
	const saida: number[] = [];
	for (let d = 0; d < nDocs; d += 1) {
		if (passa && !passa(d)) continue;
		saida.length = 0;
		membros(d, saida);
		if (saida.length < 2) continue;
		const distintos = [...new Set(saida)].sort((x, y) => x - y);
		const n = distintos.length;
		if (n < 2) continue;
		const w = 1 / (n - 1);
		for (let i = 0; i < n; i += 1) {
			for (let j = i + 1; j < n; j += 1) {
				const chave = distintos[i] * nMembros + distintos[j];
				let k = indice.get(chave);
				if (k === undefined) {
					k = a.length;
					indice.set(chave, k);
					a.push(distintos[i]);
					b.push(distintos[j]);
					peso.push(0);
					documentos.push(0);
				}
				peso[k] += w;
				documentos[k] += 1;
			}
		}
	}
	return ordenar(a, b, peso, documentos);
}

/** Os membros de cada documento guardados num CSR (as pessoas de cada documento). */
export function membrosDoCsr(csr: Csr): Membros {
	return (d, saida) => {
		for (let k = csr.inicio[d]; k < csr.inicio[d + 1]; k += 1) saida.push(csr.itens[k]);
	};
}

/** Pares de coautores: pessoas que assinaram juntas um documento do recorte. */
export function arestasCoautoria(r: TabelaRedes, passa: Passa): Arestas {
	return paresPonderados(r.pessoasDoDoc.inicio.length - 1, r.pessoas.n, membrosDoCsr(r.pessoasDoDoc), passa);
}

/** As instituições identificadas de cada documento (sem autores sem afiliação e sem a "não identificada"). */
export function instituicoesDoDoc(af: TabelaAfiliacoes): Membros {
	return (d, saida) => {
		for (let k = af.inicio[d]; k < af.inicio[d + 1]; k += 1) {
			const i = af.inst[af.linhas[k]];
			if (i >= 0 && i !== af.naoIdentificada) saida.push(i);
		}
	};
}

/** Pares de instituições do mesmo documento, pelos índices de `afiliacoes.dicionarios.instituicao`. */
export function arestasInstituicoes(af: TabelaAfiliacoes, passa: Passa): Arestas {
	return paresPonderados(af.inicio.length - 1, af.instituicoes.length, instituicoesDoDoc(af), passa);
}

/**
 * Leva as arestas para outra numeração de nós (`mapa[i]`: o nó da rede para o membro `i`, ou −1), descartando as
 * que saem dela. Serve para passar das instituições de `afiliacoes.json` às da rede desenhada.
 */
export function renumerar(ar: Arestas, mapa: Int32Array): Arestas {
	const a: number[] = [];
	const b: number[] = [];
	const peso: number[] = [];
	const documentos: number[] = [];
	for (let k = 0; k < ar.n; k += 1) {
		const [x, y] = [mapa[ar.a[k]], mapa[ar.b[k]]];
		if (x < 0 || y < 0 || x === y) continue;
		a.push(Math.min(x, y));
		b.push(Math.max(x, y));
		peso.push(ar.peso[k]);
		documentos.push(ar.documentos[k]);
	}
	return ordenar(a, b, peso, documentos);
}

/** Código do exterior nos pares de lugares, como no Python (`grafos.EXTERIOR`). */
export const EXTERIOR = 'EX';

/**
 * Os lugares de cada documento, como no Python: a UF de cada afiliação no Brasil com UF conhecida e o exterior
 * (índice `af.ufs.length`) para cada afiliação num país conhecido fora do Brasil. As afiliações de país
 * desconhecido ficam de fora.
 */
export function lugaresDoDoc(af: TabelaAfiliacoes): Membros {
	const brasil = af.paises.indexOf('BR');
	const exterior = af.ufs.length;
	return (d, saida) => {
		for (let k = af.inicio[d]; k < af.inicio[d + 1]; k += 1) {
			const l = af.linhas[k];
			const pais = af.pais[l];
			if (pais >= 0 && pais === brasil) {
				if (af.uf[l] >= 0) saida.push(af.uf[l]);
			} else if (pais >= 0) {
				saida.push(exterior);
			}
		}
	};
}

/** A sigla de um lugar dos pares (`EX` para o exterior). */
export function nomeDoLugar(af: TabelaAfiliacoes, i: number): string {
	return i === af.ufs.length ? EXTERIOR : af.ufs[i];
}

/** Pares de UFs (e de UF com o exterior) que aparecem juntas nas afiliações de um documento. */
export function arestasLugares(af: TabelaAfiliacoes, passa: Passa): Arestas {
	return paresPonderados(af.inicio.length - 1, af.ufs.length + 1, lugaresDoDoc(af), passa);
}

// ---------------------------------------------------------------- nós

/** Documentos de cada linha de um CSR que passam no recorte (os documentos de cada pessoa no recorte). */
export function contarNoRecorte(csr: Csr, passa: Passa): Int32Array {
	const n = csr.inicio.length - 1;
	const saida = new Int32Array(n);
	for (let i = 0; i < n; i += 1) {
		if (!passa) {
			saida[i] = csr.inicio[i + 1] - csr.inicio[i];
			continue;
		}
		for (let k = csr.inicio[i]; k < csr.inicio[i + 1]; k += 1) if (passa(csr.itens[k])) saida[i] += 1;
	}
	return saida;
}

/** Documentos de cada instituição de `afiliacoes.json` que passam no recorte (cada documento conta uma vez). */
export function documentosPorInstituicao(af: TabelaAfiliacoes, passa: Passa): Int32Array {
	const saida = new Int32Array(af.instituicoes.length);
	const visto = new Int32Array(af.instituicoes.length).fill(-1);
	const nDocs = af.inicio.length - 1;
	for (let d = 0; d < nDocs; d += 1) {
		if (passa && !passa(d)) continue;
		for (let k = af.inicio[d]; k < af.inicio[d + 1]; k += 1) {
			const i = af.inst[af.linhas[k]];
			if (i >= 0 && visto[i] !== d) {
				visto[i] = d;
				saida[i] += 1;
			}
		}
	}
	return saida;
}

/** Vizinhos distintos de cada nó. */
export function grauDe(ar: Arestas, nNos: number): Int32Array {
	const saida = new Int32Array(nNos);
	for (let k = 0; k < ar.n; k += 1) {
		saida[ar.a[k]] += 1;
		saida[ar.b[k]] += 1;
	}
	return saida;
}

/** Soma dos pesos das arestas de cada nó. */
export function forcaDe(ar: Arestas, nNos: number): Float64Array {
	const saida = new Float64Array(nNos);
	for (let k = 0; k < ar.n; k += 1) {
		saida[ar.a[k]] += ar.peso[k];
		saida[ar.b[k]] += ar.peso[k];
	}
	return saida;
}

/** Os parceiros de um nó nas arestas, do maior peso ao menor: `[nó, peso, documentos]`. */
export function parceiros(ar: Arestas, no: number): [number, number, number][] {
	const saida: [number, number, number][] = [];
	for (let k = 0; k < ar.n; k += 1) {
		if (ar.a[k] === no) saida.push([ar.b[k], ar.peso[k], ar.documentos[k]]);
		else if (ar.b[k] === no) saida.push([ar.a[k], ar.peso[k], ar.documentos[k]]);
	}
	return saida.sort((p, q) => q[1] - p[1] || q[2] - p[2] || p[0] - q[0]);
}

/** Limites das faixas de opacidade das arestas: peso até 0,5; até 1; até 3; acima. */
export const LIMITES_FAIXAS = [0.5, 1, 3] as const;

/** A faixa (1 a 4) de uma aresta pelo peso. Quatro faixas bastam para ler a rede e cabem num só traço cada. */
export function faixaDoPeso(peso: number): 1 | 2 | 3 | 4 {
	const e = 1e-9; // 1/3 + 1/3 + 1/3 não dá 1 exato
	if (peso <= LIMITES_FAIXAS[0] + e) return 1;
	if (peso <= LIMITES_FAIXAS[1] + e) return 2;
	if (peso <= LIMITES_FAIXAS[2] + e) return 3;
	return 4;
}

/** Chave de um par para achar a mesma aresta em duas listas (a do recorte na do corpus). */
export function chaveDoPar(a: number, b: number, nNos: number): number {
	return Math.min(a, b) * nNos + Math.max(a, b);
}

/**
 * A faixa de cada aresta do corpus no recorte: 0 quando ela não aparece no recorte (fica esmaecida), senão a faixa
 * do peso que ela tem no recorte. O desenho usa sempre as arestas do corpus, para nada mudar de lugar.
 */
export function faixasNoRecorte(corpus: Arestas, recorte: Arestas, nNos: number): Uint8Array {
	const indice = new Map<number, number>();
	for (let k = 0; k < corpus.n; k += 1) indice.set(chaveDoPar(corpus.a[k], corpus.b[k], nNos), k);
	const saida = new Uint8Array(corpus.n);
	for (let k = 0; k < recorte.n; k += 1) {
		const i = indice.get(chaveDoPar(recorte.a[k], recorte.b[k], nNos));
		if (i !== undefined) saida[i] = faixaDoPeso(recorte.peso[k]);
	}
	return saida;
}

// ---------------------------------------------------------------- colaboração por ano

export interface Colaboracao {
	ano: number;
	/** Documentos do ano com ao menos uma pessoa identificada. */
	documentos: number;
	comCoautoria: number;
	autoresMedio: number;
	/** Entre os documentos com instituição identificada, os que têm duas ou mais. */
	comInstituicoes: number | null;
	/** Entre os documentos com lugar conhecido, os que têm duas ou mais UFs. */
	entreUfs: number | null;
	/** Entre os documentos com lugar conhecido, os que juntam Brasil e exterior. */
	comExterior: number | null;
}

/** A colaboração em cada ano do recorte, com a regra de `colaboracao_por_ano` no Python. */
export function colaboracaoPorAno(
	anos: ArrayLike<number>,
	r: TabelaRedes,
	af: TabelaAfiliacoes | null,
	passa: Passa
): Colaboracao[] {
	const porAno = new Map<number, number[]>();
	const csr = r.pessoasDoDoc;
	for (let d = 0; d < csr.inicio.length - 1; d += 1) {
		if (csr.inicio[d + 1] === csr.inicio[d] || (passa && !passa(d))) continue;
		const lista = porAno.get(anos[d]);
		if (lista) lista.push(d);
		else porAno.set(anos[d], [d]);
	}
	const insts = af ? instituicoesDoDoc(af) : null;
	const lugares = af ? lugaresDoDoc(af) : null;
	const exterior = af ? af.ufs.length : -1;
	const saida: Colaboracao[] = [];
	const membros: number[] = [];
	for (const ano of [...porAno.keys()].sort((x, y) => x - y)) {
		const docs = porAno.get(ano)!;
		let coautoria = 0;
		let autores = 0;
		let comInst = 0;
		let variasInst = 0;
		let comLugar = 0;
		let variasUfs = 0;
		let brasilEExterior = 0;
		for (const d of docs) {
			const n = csr.inicio[d + 1] - csr.inicio[d];
			autores += n;
			if (n > 1) coautoria += 1;
			if (insts) {
				membros.length = 0;
				insts(d, membros);
				if (membros.length) {
					comInst += 1;
					if (new Set(membros).size > 1) variasInst += 1;
				}
			}
			if (lugares) {
				membros.length = 0;
				lugares(d, membros);
				if (membros.length) {
					comLugar += 1;
					const ufs = new Set(membros.filter((m) => m !== exterior));
					if (ufs.size > 1) variasUfs += 1;
					if (ufs.size && membros.includes(exterior)) brasilEExterior += 1;
				}
			}
		}
		saida.push({
			ano,
			documentos: docs.length,
			comCoautoria: coautoria / docs.length,
			autoresMedio: autores / docs.length,
			comInstituicoes: af && comInst ? variasInst / comInst : null,
			entreUfs: af && comLugar ? variasUfs / comLugar : null,
			comExterior: af && comLugar ? brasilEExterior / comLugar : null
		});
	}
	return saida;
}

// ---------------------------------------------------------------- citações

/**
 * A posição do macrotema de cada documento em `topicos.macrotemas` (pelo tópico), ou −1 sem tópico. A posição, e
 * não o id: os ids dos macrotemas são estáveis e não contíguos (no piloto, 0, 1, 2, 5, 6, 7 e 8), e a matriz do
 * fluxo e as fatias do cânone são indexadas de 0 a n − 1, como no Python (`contrato/redes.fluxo_por_posicao`).
 */
export function posicaoDoMacro(topicoDoDoc: ArrayLike<number>, topicos: Topicos): Int32Array {
	const posicao = new Map(topicos.macrotemas.map((m, k) => [m.id, k]));
	const macro = new Map(topicos.topicos.map((t) => [t.id, posicao.get(t.macro_id) ?? -1]));
	return Int32Array.from({ length: topicoDoDoc.length }, (_, d) => macro.get(topicoDoDoc[d]) ?? -1);
}

export interface CitacoesInternas {
	/** Citações entre dois documentos do recorte. */
	n: number;
	/** Macrotema de quem cita (linha) × macrotema de quem é citado (coluna), pela posição, `nMacros × nMacros`. */
	matriz: number[][];
}

/**
 * As citações internas visíveis no recorte: as duas pontas precisam estar nele (uma citação de um artigo de 2020 a
 * um de 2012 some com `anos=2015-2020`). `macro`: a posição do macrotema de cada documento (`posicaoDoMacro`), que
 * é a linha e a coluna da matriz, como no Python.
 */
export function citacoesInternas(c: TabelaCitacoes, passa: Passa, macro: Int32Array, nMacros: number): CitacoesInternas {
	const matriz = Array.from({ length: nMacros }, () => new Array<number>(nMacros).fill(0));
	let n = 0;
	for (let k = 0; k < c.de.length; k += 1) {
		const [de, para] = [c.de[k], c.para[k]];
		if (passa && !(passa(de) && passa(para))) continue;
		n += 1;
		const [a, b] = [macro[de], macro[para]];
		if (a >= 0 && a < nMacros && b >= 0 && b < nMacros) matriz[a][b] += 1;
	}
	return { n, matriz };
}

export interface ObraNoRecorte {
	/** Índice em `canone`. */
	obra: number;
	/** Documentos do recorte que citam a obra. */
	n: number;
	/** Os mesmos documentos pela posição do macrotema de quem cita; a última posição é "sem tópico". */
	porMacro: number[];
}

/** Quantos documentos do recorte citam cada obra do cânone, e de que macrotemas eles são. */
export function canoneNoRecorte(c: TabelaCitacoes, passa: Passa, macro: Int32Array, nMacros: number): ObraNoRecorte[] {
	const saida: ObraNoRecorte[] = c.canone.map((_, obra) => ({ obra, n: 0, porMacro: new Array(nMacros + 1).fill(0) }));
	const vistos = new Set<number>();
	for (let k = 0; k < c.citanteDoc.length; k += 1) {
		const [d, obra] = [c.citanteDoc[k], c.citanteObra[k]];
		if (obra < 0 || obra >= saida.length || (passa && !passa(d))) continue;
		const chave = d * saida.length + obra;
		if (vistos.has(chave)) continue;
		vistos.add(chave);
		const m = macro[d];
		saida[obra].n += 1;
		saida[obra].porMacro[m >= 0 && m < nMacros ? m : nMacros] += 1;
	}
	return saida;
}

/** As `k` obras mais citadas no recorte (empates pela ordem do cânone, que é a do corpus inteiro). */
export function maisCitadas(lista: ObraNoRecorte[], k = 30): ObraNoRecorte[] {
	return lista
		.filter((o) => o.n > 0)
		.sort((p, q) => q.n - p.n || p.obra - q.obra)
		.slice(0, k);
}
