/**
 * Cores dos pontos do mapa, conforme o "colorir por" escolhido.
 *
 * Tópicos e macrotemas usam as cores do contrato (geradas em `topicos/paleta.py`, estáveis entre execuções).
 * Revistas usam uma paleta categórica fixa, e anos um degradê sequencial; as duas foram geradas pela mesma
 * paleta OKLCH do Python, com contraste de pelo menos 3:1 sobre os dois fundos da interface.
 *
 * O regl-scatterplot quer categorias densas (0 a k−1) e uma cor por categoria; documentos sem tópico vão
 * para a última categoria, em cinza.
 */
import type { Topicos } from '$lib/contrato/tipos';
import type { CorPor } from '$lib/estado/url';
import type { TabelaDocumentos } from '$lib/dados/documentos';

export const PALETA_REVISTAS = [
	'#cf686b', '#a55115', '#b5820c', '#707100', '#58994a', '#007f62',
	'#00999f', '#00769d', '#5c8cda', '#6c5cb1', '#af70bd', '#a14876'
];
export const DEGRADE_ANOS = ['#3e5fad', '#006fa5', '#007b8f', '#00847f', '#008d65', '#4f8f40', '#808a17', '#a58200', '#c17924'];

export interface ItemLegenda {
	rotulo: string;
	cor: string;
	/** Tópicos (ids) que o item representa, para filtrar ao clicar. */
	topicos?: number[];
	revista?: string;
}

export interface Coloracao {
	/** Valor de cada ponto: índice da categoria, ou entre 0 e 1 no degradê. */
	valores: Float32Array;
	tipo: 'categorical' | 'continuous';
	cores: string[];
	legenda: ItemLegenda[];
}

export function colorir(t: TabelaDocumentos, topicos: Topicos, modo: CorPor, cinza: string): Coloracao {
	const valores = new Float32Array(t.n);
	if (modo === 'ano') {
		const [a, b] = t.anos;
		for (let i = 0; i < t.n; i += 1) valores[i] = b > a ? (t.ano[i] - a) / (b - a) : 0.5;
		const legenda = [
			{ rotulo: String(a), cor: DEGRADE_ANOS[0] },
			{ rotulo: String(b), cor: DEGRADE_ANOS[DEGRADE_ANOS.length - 1] }
		];
		return { valores, tipo: 'continuous', cores: DEGRADE_ANOS, legenda };
	}
	if (modo === 'revista') {
		const cores = t.revistas.map((_, i) => PALETA_REVISTAS[i % PALETA_REVISTAS.length]);
		for (let i = 0; i < t.n; i += 1) valores[i] = t.revista[i];
		const legenda = t.revistas.map((r, i) => ({ rotulo: r, cor: cores[i], revista: r }));
		return { valores, tipo: 'categorical', cores, legenda };
	}
	// tópico ou macrotema: categorias densas a partir dos ids estáveis
	const grupos =
		modo === 'macrotema'
			? topicos.macrotemas.map((m) => ({ rotulo: m.rotulo, cor: m.cor, topicos: m.topicos }))
			: topicos.topicos.map((tp) => ({ rotulo: tp.rotulo, cor: tp.cor, topicos: [tp.id] }));
	const categoria = new Map<number, number>();
	grupos.forEach((g, k) => g.topicos.forEach((id) => categoria.set(id, k)));
	const semTopico = grupos.length;
	for (let i = 0; i < t.n; i += 1) valores[i] = categoria.get(t.topico[i]) ?? semTopico;
	const legenda: ItemLegenda[] = [...grupos, { rotulo: 'sem tópico', cor: cinza, topicos: [-1] }];
	return { valores, tipo: 'categorical', cores: [...grupos.map((g) => g.cor), cinza], legenda };
}
