/**
 * As contas da vista Classificação, sobre o cubo do filtro cruzado:
 *
 * - `porAno`: documentos de cada valor de uma variável, por ano (ignora o filtro de anos, como o fluxo dos
 *   tópicos: o gráfico mostra o período inteiro, com o intervalo do recorte destacado);
 * - `cruzamento`: a variável cruzada com os macrotemas, os tópicos ou as revistas, no recorte inteiro;
 * - `documentosDaCelula`: os documentos de uma célula do cruzamento, para ler as evidências;
 * - `referenciaDe`: a concordância que acompanha a variável (o selo de kappa), da validação.
 *
 * Cada documento classificado conta 1. Os não classificados (sem resumo, ou ainda na fila) ficam de fora das
 * proporções e aparecem à parte.
 */
import type { CodebookContrato, MetricaVariavel, Participante, Topicos, Validacao } from '$lib/contrato/tipos';
import { D, type Cubo } from '$lib/dados/cubo';
import type { TabelaDocumentos } from '$lib/dados/documentos';
import { PALETA_REVISTAS } from '$lib/mapa/cores';

/** Respostas que dizem que o resumo não informa a variável: aparecem em cinza. */
export const SEM_INFORMACAO = new Set(['nao_informado', 'nao_se_aplica']);

export interface VariavelVista {
	id: string;
	rotulo: string;
	tipo: 'categorica' | 'multipla' | 'booleana' | 'texto';
	pergunta: string;
	/** Os valores como estão em `dicionarios.cls` (a coluna guarda o índice). */
	valores: string[];
	/** Como cada valor aparece na tela. */
	rotulos: string[];
	/** A definição do codebook de cada valor (vazia em booleanas e combinações). */
	definicoes: string[];
	/** O valor diz "sem informação" (cinza nos gráficos). */
	semInformacao: boolean[];
}

const rotuloDe = (valor: string) => valor.replaceAll('_', ' ');

/** As variáveis que a vista mostra: as do codebook com coluna em `documentos.json` (as de texto ficam de fora). */
export function variaveisDaVista(codebook: CodebookContrato, t: TabelaDocumentos): VariavelVista[] {
	return codebook.variaveis
		.filter((v) => t.cls[v.id] && t.clsValores[v.id])
		.map((v) => {
			const valores = t.clsValores[v.id];
			const categoria = new Map((v.categorias ?? []).map((c) => [c.valor, c]));
			const nome = (valor: string) => categoria.get(valor)?.rotulo || rotuloDe(valor);
			let rotulos: string[];
			if (v.tipo === 'booleana') rotulos = valores.map((x) => (x === 'true' ? 'Sim' : 'Não'));
			else if (v.tipo === 'multipla')
				rotulos = valores.map((x) => {
					const lista = JSON.parse(x) as string[];
					return lista.length ? lista.map(nome).join(' + ') : 'nenhuma';
				});
			else rotulos = valores.map(nome);
			return {
				id: v.id,
				rotulo: v.rotulo,
				tipo: v.tipo,
				pergunta: v.pergunta,
				valores,
				rotulos,
				definicoes: valores.map((x) => categoria.get(x)?.definicao ?? ''),
				semInformacao: valores.map((x) =>
					v.tipo === 'multipla'
						? (JSON.parse(x) as string[]).every((c) => SEM_INFORMACAO.has(c))
						: SEM_INFORMACAO.has(x)
				)
			};
		});
}

export interface PorAno {
	anos: number[];
	/** anos × valores, em ordem de linha: `n[j * k + valor]`. */
	n: Float64Array;
	/** Documentos classificados em cada ano (o denominador das proporções). */
	classificados: Float64Array;
	/** Documentos do recorte em cada ano, classificados ou não. */
	total: Float64Array;
}

/** Documentos de cada valor por ano, no recorte sem o filtro de anos. */
export function porAno(cubo: Cubo, falhas: Uint8Array, v: VariavelVista, anos: number[]): PorAno {
	const k = v.valores.length;
	const col = cubo.t.cls[v.id];
	const primeiro = anos[0];
	const largura = k + 1; // a última célula de cada ano: não classificado
	const c = cubo.contarPor(falhas, D.ANO, anos.length * largura, (i) => {
		const j = cubo.t.ano[i] - primeiro;
		if (j < 0 || j >= anos.length) return -1;
		return j * largura + (col[i] >= 0 ? col[i] : k);
	});
	const n = new Float64Array(anos.length * k);
	const classificados = new Float64Array(anos.length);
	const total = new Float64Array(anos.length);
	for (let j = 0; j < anos.length; j += 1) {
		for (let x = 0; x < k; x += 1) {
			n[j * k + x] = c[j * largura + x];
			classificados[j] += c[j * largura + x];
		}
		total[j] = classificados[j] + c[j * largura + k];
	}
	return { anos, n, classificados, total };
}

export const LINHAS_CRUZAMENTO = ['macrotema', 'topico', 'revista'] as const;
export type LinhasCruzamento = (typeof LINHAS_CRUZAMENTO)[number];

export interface LinhaCruzamento {
	chave: string;
	rotulo: string;
	cor: string | null;
}

export interface Cruzamento {
	linhas: LinhaCruzamento[];
	/** linhas × valores: `n[l * k + valor]`. */
	n: Float64Array;
	/** Documentos classificados em cada linha. */
	classificados: Float64Array;
	/** A linha de cada documento (−1 = fora de todas). */
	linhaDe: (i: number) => number;
}

function linhasDe(t: TabelaDocumentos, topicos: Topicos, por: LinhasCruzamento) {
	if (por === 'revista') {
		const linhas = t.revistas.map((r) => ({ chave: r, rotulo: r, cor: null }));
		return { linhas, linhaDe: (i: number) => t.revista[i] };
	}
	const semTopico = { chave: '-1', rotulo: 'Sem tópico', cor: null };
	if (por === 'topico') {
		const ordem = topicos.macrotemas.flatMap((m) => m.topicos);
		const porId = new Map(topicos.topicos.map((x) => [x.id, x]));
		const ids = [...ordem, ...topicos.topicos.map((x) => x.id).filter((id) => !ordem.includes(id))];
		const pos = new Map(ids.map((id, l) => [id, l]));
		const linhas = [
			...ids.map((id) => ({
				chave: String(id),
				rotulo: porId.get(id)?.rotulo ?? `Tópico ${id}`,
				cor: porId.get(id)?.cor ?? null
			})),
			semTopico
		];
		return {
			linhas,
			linhaDe: (i: number) => pos.get(t.topico[i]) ?? ids.length
		};
	}
	const macroDe = new Map<number, number>();
	topicos.macrotemas.forEach((m, l) => m.topicos.forEach((id) => macroDe.set(id, l)));
	const linhas = [
		...topicos.macrotemas.map((m) => ({
			chave: String(m.id),
			rotulo: m.rotulo,
			cor: m.cor
		})),
		semTopico
	];
	return {
		linhas,
		linhaDe: (i: number) => macroDe.get(t.topico[i]) ?? topicos.macrotemas.length
	};
}

/** A variável cruzada com macrotemas, tópicos ou revistas, no recorte inteiro. */
export function cruzamento(cubo: Cubo, falhas: Uint8Array, v: VariavelVista, por: LinhasCruzamento): Cruzamento {
	const { linhas, linhaDe } = linhasDe(cubo.t, cubo.topicos, por);
	const k = v.valores.length;
	const col = cubo.t.cls[v.id];
	const n = cubo.contarPor(falhas, 0, linhas.length * k, (i) => (col[i] >= 0 ? linhaDe(i) * k + col[i] : -1));
	const classificados = new Float64Array(linhas.length);
	for (let l = 0; l < linhas.length; l += 1) for (let x = 0; x < k; x += 1) classificados[l] += n[l * k + x];
	return { linhas, n, classificados, linhaDe };
}

/** Os documentos (índices) do recorte numa célula do cruzamento; `linha` = −1 para qualquer linha. */
export function documentosDaCelula(
	cubo: Cubo,
	falhas: Uint8Array,
	v: VariavelVista,
	c: Pick<Cruzamento, 'linhaDe'>,
	linha: number,
	valor: number
): number[] {
	const col = cubo.t.cls[v.id];
	const saida: number[] = [];
	for (let i = 0; i < falhas.length; i += 1) {
		if (falhas[i] !== 0 || col[i] !== valor) continue;
		if (linha < 0 || c.linhaDe(i) === linha) saida.push(i);
	}
	return saida;
}

export interface Referencia {
	metrica: MetricaVariavel;
	participante: Participante;
}

/**
 * A concordância do modelo principal com um codificador, na variável: a de uma pessoa, se houver; senão, a de um
 * codificador de referência. Nas de múltipla escolha não há uma só (é uma métrica por categoria).
 */
export function referenciaDe(validacao: Validacao | null, variavel: string): Referencia | null {
	if (!validacao?.modelo_principal) return null;
	const tipos = new Map((validacao.codificadores ?? []).map((p) => [p.nome, p]));
	const candidatas = validacao.metricas
		.filter((m) => m.variavel === variavel && m.comparado === validacao.modelo_principal)
		.map((m) => ({ metrica: m, participante: tipos.get(m.referencia ?? '') }))
		.filter((x): x is Referencia => !!x.participante && x.participante.tipo !== 'modelo');
	candidatas.sort(
		(x, y) =>
			Number(y.participante.tipo === 'humano') - Number(x.participante.tipo === 'humano') || y.metrica.n - x.metrica.n
	);
	return candidatas[0] ?? null;
}

/** O kappa abaixo do qual o selo leva hachura: concordância só moderada, leia com cuidado. */
export const KAPPA_FRACO = 0.6;

/**
 * A cor de cada valor: a paleta categórica (a das revistas, com contraste testado nos dois temas), numa ordem que
 * alterna matizes para valores vizinhos não se confundirem; os valores "sem informação" ficam em cinza.
 */
const ORDEM_CORES = [7, 2, 0, 4, 9, 6, 1, 11, 8, 3, 5, 10];
export function coresDosValores(v: Pick<VariavelVista, 'valores' | 'semInformacao'>): string[] {
	let j = 0;
	return v.valores.map((_, x) =>
		v.semInformacao[x] ? 'var(--texto-fraco)' : PALETA_REVISTAS[ORDEM_CORES[j++ % ORDEM_CORES.length]]
	);
}
