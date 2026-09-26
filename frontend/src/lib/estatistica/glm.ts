/**
 * Tendência de uma série no tempo (ADR 0009), espelho de `src/mapa_da_ciencia/topicos/tendencia.py`: regressão
 * logística da participação anual (sucessos = documentos do tópico no ano, ensaios = documentos do ano), com o
 * ano centrado, Newton com meio passo, erro-padrão corrigido pela dispersão de Pearson (quase-binomial) e
 * intervalo de Wald. O tamanho da mudança vem das participações ajustadas no primeiro e no último ano.
 *
 * Os casos de `contrato/casos/tendencia.json` (gerados pelo Python) garantem que as duas versões concordam.
 */
import type { MetodoTendencia } from '$lib/contrato/tipos';

export type Direcao = 'alta' | 'queda' | 'estavel' | 'insuficiente';
export type Motivo = 'poucos_anos' | 'poucos_documentos' | 'sem_variacao' | 'sem_convergencia';

export interface Tendencia {
	direcao: Direcao;
	inclinacao: number | null;
	erro_padrao: number | null;
	ic95: [number, number] | null;
	dispersao: number | null;
	prop_inicio: number | null;
	prop_fim: number | null;
	pp_periodo: number | null;
	pp_por_ano: number | null;
	anos: [number, number] | null;
	motivo: Motivo | null;
}

export const METODO_PADRAO: Required<MetodoTendencia> = {
	modelo: 'logistica_binomial',
	dispersao: 'quase',
	nivel: 0.95,
	z: 1.959963984540054,
	anos_minimos: 5,
	docs_minimos: 10
};

const INCLINACAO_MAXIMA = 10;
const ITERACOES_MAXIMAS = 100;
const TOLERANCIA = 1e-10;

const expit = (eta: number) => (eta >= 0 ? 1 / (1 + Math.exp(-eta)) : Math.exp(eta) / (1 + Math.exp(eta)));
const softplus = (eta: number) => (eta > 0 ? eta + Math.log1p(Math.exp(-eta)) : Math.log1p(Math.exp(eta)));

interface Ajuste {
	intercepto: number;
	inclinacao: number;
	erroPadrao: number;
	pearson: number;
	mediaAnos: number;
}

function verossimilhanca(b0: number, b1: number, x: number[], k: number[], n: number[]): number {
	let soma = 0;
	for (let i = 0; i < x.length; i += 1) {
		const eta = b0 + b1 * x[i];
		soma += k[i] * eta - n[i] * softplus(eta);
	}
	return soma;
}

function informacao(b0: number, b1: number, x: number[], n: number[]) {
	let i00 = 0;
	let i01 = 0;
	let i11 = 0;
	const p: number[] = [];
	const w: number[] = [];
	for (let i = 0; i < x.length; i += 1) {
		const pi = expit(b0 + b1 * x[i]);
		const wi = n[i] * pi * (1 - pi);
		p.push(pi);
		w.push(wi);
		i00 += wi;
		i01 += x[i] * wi;
		i11 += x[i] * x[i] * wi;
	}
	return { p, w, i00, i01, i11, det: i00 * i11 - i01 * i01 };
}

/** Máxima verossimilhança de logit(p) = b0 + b1·(ano − média). `null` se não convergir ou divergir. */
export function ajustarGlm(anos: number[], k: number[], n: number[]): Ajuste | null {
	const mediaAnos = anos.reduce((a, b) => a + b, 0) / anos.length;
	const x = anos.map((a) => a - mediaAnos);
	const totalK = k.reduce((a, b) => a + b, 0);
	const totalN = n.reduce((a, b) => a + b, 0);
	if (totalK <= 0 || totalK >= totalN) return null;
	let b0 = Math.log(totalK / (totalN - totalK));
	let b1 = 0;
	let atual = verossimilhanca(b0, b1, x, k, n);
	let convergiu = false;
	for (let iter = 0; iter < ITERACOES_MAXIMAS; iter += 1) {
		const { p, i00, i01, i11, det } = informacao(b0, b1, x, n);
		let g0 = 0;
		let g1 = 0;
		for (let i = 0; i < x.length; i += 1) {
			g0 += k[i] - n[i] * p[i];
			g1 += x[i] * (k[i] - n[i] * p[i]);
		}
		if (det <= 0) return null;
		const d0 = (i11 * g0 - i01 * g1) / det;
		const d1 = (i00 * g1 - i01 * g0) / det;
		let passo = 1;
		let nova = atual;
		for (let h = 0; h < 30; h += 1) {
			nova = verossimilhanca(b0 + passo * d0, b1 + passo * d1, x, k, n);
			if (nova >= atual - 1e-12) break;
			passo /= 2;
		}
		b0 += passo * d0;
		b1 += passo * d1;
		atual = nova;
		if (Math.abs(b1) > INCLINACAO_MAXIMA) return null;
		if (Math.max(Math.abs(passo * d0), Math.abs(passo * d1)) < TOLERANCIA) {
			convergiu = true;
			break;
		}
	}
	if (!convergiu) return null;
	const { p, w, i00, det } = informacao(b0, b1, x, n);
	if (det <= 0) return null;
	let pearson = 0;
	for (let i = 0; i < x.length; i += 1) if (w[i] > 0) pearson += (k[i] - n[i] * p[i]) ** 2 / w[i];
	return { intercepto: b0, inclinacao: b1, erroPadrao: Math.sqrt(i00 / det), pearson, mediaAnos };
}

const insuficiente = (motivo: Motivo, anos: [number, number] | null): Tendencia => ({
	direcao: 'insuficiente',
	inclinacao: null,
	erro_padrao: null,
	ic95: null,
	dispersao: null,
	prop_inicio: null,
	prop_fim: null,
	pp_periodo: null,
	pp_por_ano: null,
	anos,
	motivo
});

/** Tendência da série `n` (documentos do tópico por ano) sobre `total` (documentos de cada ano). */
export function tendencia(
	n: ArrayLike<number>,
	total: ArrayLike<number>,
	anos: number[],
	metodo: Partial<MetodoTendencia> = {}
): Tendencia {
	const m = { ...METODO_PADRAO, ...metodo };
	const usados: [number, number, number][] = [];
	for (let i = 0; i < anos.length; i += 1) if (total[i] > 0) usados.push([anos[i], n[i], total[i]]);
	const periodo: [number, number] | null = usados.length ? [usados[0][0], usados[usados.length - 1][0]] : null;
	if (usados.length < m.anos_minimos) return insuficiente('poucos_anos', periodo);
	const xs = usados.map((u) => u[0]);
	const ks = usados.map((u) => u[1]);
	const ns = usados.map((u) => u[2]);
	const somaK = ks.reduce((a, b) => a + b, 0);
	if (somaK < m.docs_minimos) return insuficiente('poucos_documentos', periodo);
	if (somaK >= ns.reduce((a, b) => a + b, 0)) return insuficiente('sem_variacao', periodo);
	const ajuste = ajustarGlm(xs, ks, ns);
	if (!ajuste) return insuficiente('sem_convergencia', periodo);
	const phi = m.dispersao === 'quase' ? Math.max(1, ajuste.pearson / (usados.length - 2)) : 1;
	const ep = ajuste.erroPadrao * Math.sqrt(phi);
	const ic: [number, number] = [ajuste.inclinacao - m.z * ep, ajuste.inclinacao + m.z * ep];
	const direcao: Direcao = ic[0] > 0 ? 'alta' : ic[1] < 0 ? 'queda' : 'estavel';
	const [primeiro, ultimo] = periodo!;
	const p0 = expit(ajuste.intercepto + ajuste.inclinacao * (primeiro - ajuste.mediaAnos));
	const p1 = expit(ajuste.intercepto + ajuste.inclinacao * (ultimo - ajuste.mediaAnos));
	const pp = 100 * (p1 - p0);
	return {
		direcao,
		inclinacao: ajuste.inclinacao,
		erro_padrao: ep,
		ic95: ic,
		dispersao: phi,
		prop_inicio: p0,
		prop_fim: p1,
		pp_periodo: pp,
		pp_por_ano: pp / (ultimo - primeiro),
		anos: periodo,
		motivo: null
	};
}

/** Participação ajustada em cada ano de `anos`, para a curva tracejada da sparkline. */
export function ajustados(t: Tendencia, anos: number[]): number[] | null {
	if (t.inclinacao === null || t.prop_inicio === null || !t.anos) return null;
	const [primeiro] = t.anos;
	const eta0 = Math.log(t.prop_inicio / (1 - t.prop_inicio));
	return anos.map((a) => expit(eta0 + t.inclinacao! * (a - primeiro)));
}
