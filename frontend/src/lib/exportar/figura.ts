/**
 * Exportar uma figura do painel como SVG, PNG ou CSV, para artigos, slides e telões.
 *
 * - **SVG:** o gráfico da figura é clonado com os estilos já resolvidos (as variáveis CSS viram cores do tema
 *   escolhido, que pode não ser o da tela), ganha um cabeçalho (título, recorte) e um rodapé (fonte, n, modelo,
 *   data), e leva as fontes embutidas (`@font-face` com `data:`), para abrir igual em qualquer programa.
 * - **PNG:** o mesmo SVG rasterizado num `canvas`, na resolução do preset.
 * - **CSV:** os dados da figura em números crus (ponto decimal, sem separador de milhar, proporções como fração,
 *   intervalos em duas colunas, vazio onde não há valor), para o R, o pandas ou uma planilha refazerem as contas;
 *   em UTF-8 com BOM. Sem esses dados, sai a tabela da figura ("Ver como tabela") como está na tela.
 *
 * Presets: **Artigo** (85 ou 174 mm, 300 ou 600 dpi, tema Prancha), **Slide** (1920 px de largura) e **Telão**
 * (3840 px, tema Observatório).
 */
import type { Tema } from '$lib/estado/tema.svelte';

export type Formato = 'svg' | 'png' | 'csv';

export interface Preset {
	id: string;
	nome: string;
	/** Largura final: em milímetros (artigo) ou em pixels (tela). */
	largura: { mm: number; dpi: number } | { px: number };
	tema: Tema | null; // null = o tema da tela
	/** Tamanho da letra do cabeçalho e do rodapé, relativo à largura. */
	escalaTexto: number;
}

export const PRESETS: Preset[] = [
	{
		id: 'artigo-1',
		nome: 'Artigo, 1 coluna (85 mm, 300 dpi)',
		largura: { mm: 85, dpi: 300 },
		tema: 'prancha',
		escalaTexto: 1.25
	},
	{
		id: 'artigo-2',
		nome: 'Artigo, 2 colunas (174 mm, 300 dpi)',
		largura: { mm: 174, dpi: 300 },
		tema: 'prancha',
		escalaTexto: 1
	},
	{
		id: 'artigo-2-600',
		nome: 'Artigo, 2 colunas (174 mm, 600 dpi)',
		largura: { mm: 174, dpi: 600 },
		tema: 'prancha',
		escalaTexto: 1
	},
	{ id: 'slide', nome: 'Slide (1920 px)', largura: { px: 1920 }, tema: null, escalaTexto: 1.2 },
	{ id: 'telao', nome: 'Telão (3840 px, Observatório)', largura: { px: 3840 }, tema: 'observatorio', escalaTexto: 1.4 }
];

export interface Metadados {
	titulo: string;
	/** O recorte, em palavras ("2015–2020 · Dados, Opinião Pública"). */
	recorte: string;
	/** A fonte e o modelo ("SciELO Brasil e OpenAlex · qwen3.5:9b"). */
	fonte: string;
	/** Documentos no recorte. */
	n: number | null;
}

/** Largura final em pixels de um preset. */
export function larguraPx(p: Preset): number {
	return 'px' in p.largura ? p.largura.px : Math.round((p.largura.mm / 25.4) * p.largura.dpi);
}

// ---------------------------------------------------------------- CSV
/** Uma célula do CSV: texto, número cru ou vazio (`null`, sem valor). */
export type Celula = string | number | null;

/** As colunas e as linhas que vão para o CSV de uma figura. */
export interface DadosCsv {
	colunas: string[];
	linhas: Celula[][];
}

/** Número para o CSV: sem o ruído do ponto flutuante (929.5912000000001 → 929.5912). */
export const numeroCru = (v: number, casas = 4): number => Number(v.toFixed(casas));

function campo(v: Celula): string {
	const texto = v === null ? '' : String(v);
	return /[",;\n]/.test(texto) ? `"${texto.replaceAll('"', '""')}"` : texto;
}

export function paraCsv(colunas: string[], linhas: Celula[][]): string {
	return '﻿' + [colunas, ...linhas].map((l) => l.map(campo).join(',')).join('\r\n') + '\r\n';
}

// ---------------------------------------------------------------- estilos
const PROPRIEDADES = [
	'fill',
	'fill-opacity',
	'stroke',
	'stroke-width',
	'stroke-opacity',
	'stroke-dasharray',
	'stroke-linecap',
	'stroke-linejoin',
	'opacity',
	'font-family',
	'font-size',
	'font-weight',
	'font-style',
	'letter-spacing',
	'text-anchor',
	'dominant-baseline',
	'paint-order',
	'visibility',
	'display'
];

/** Lê as cores do tema `tema` sem mudar a tela: troca o `data-tema`, lê e devolve, na mesma tarefa. */
export function comTema<T>(tema: Tema | null, ler: () => T): T {
	const raiz = document.documentElement;
	const antes = raiz.dataset.tema;
	if (tema && tema !== antes) raiz.dataset.tema = tema;
	try {
		return ler();
	} finally {
		if (antes === undefined) delete raiz.dataset.tema;
		else raiz.dataset.tema = antes;
	}
}

/** Copia para o clone os estilos calculados de cada elemento do original (mesma ordem na árvore). */
function fixarEstilos(original: Element, clone: Element) {
	const a = [original, ...original.querySelectorAll('*')];
	const b = [clone, ...clone.querySelectorAll('*')];
	a.forEach((el, i) => {
		const c = b[i] as SVGElement | undefined;
		if (!c || !('style' in c)) return;
		// atributos com variáveis CSS (fill="var(--seq-3)") não valem fora da página: o estilo calculado os substitui
		for (const attr of Array.from(c.attributes)) if (attr.value.includes('var(')) c.removeAttribute(attr.name);
		const s = getComputedStyle(el);
		const partes = PROPRIEDADES.map((p) => [p, s.getPropertyValue(p)] as const).filter(([, v]) => v && v !== 'normal');
		c.removeAttribute('class');
		c.setAttribute('style', partes.map(([p, v]) => `${p}:${v}`).join(';'));
	});
}

// ---------------------------------------------------------------- fontes
const cacheFontes = new Map<string, Promise<string>>();

async function dataUri(url: string): Promise<string> {
	const blob = await (await fetch(url)).blob();
	return new Promise((resolver) => {
		const leitor = new FileReader();
		leitor.onload = () => resolver(String(leitor.result));
		leitor.readAsDataURL(blob);
	});
}

/** As regras `@font-face` das famílias usadas, com os arquivos embutidos (só os subconjuntos latinos). */
async function fontesEmbutidas(familias: Set<string>): Promise<string> {
	const regras: string[] = [];
	for (const folha of Array.from(document.styleSheets)) {
		let lista: CSSRuleList;
		try {
			lista = folha.cssRules;
		} catch {
			continue; // folha de outro domínio
		}
		for (const r of Array.from(lista)) {
			if (!(r instanceof CSSFontFaceRule)) continue;
			const familia = r.style.getPropertyValue('font-family').replaceAll(/['"]/g, '').trim();
			const faixa = r.style.getPropertyValue('unicode-range');
			if (!familias.has(familia) || (faixa && !/U\+0-FF|U\+0000-00FF/i.test(faixa))) continue;
			const url = r.style.getPropertyValue('src').match(/url\(["']?([^"')]+)["']?\)/)?.[1];
			if (!url) continue;
			const absoluta = new URL(url, folha.href ?? document.baseURI).toString();
			if (!cacheFontes.has(absoluta)) cacheFontes.set(absoluta, dataUri(absoluta));
			const dados = await cacheFontes.get(absoluta)!;
			const peso = r.style.getPropertyValue('font-weight') || 'normal';
			const estilo = r.style.getPropertyValue('font-style') || 'normal';
			regras.push(
				`@font-face{font-family:'${familia}';src:url(${dados}) format('woff2');font-weight:${peso};font-style:${estilo};}`
			);
		}
	}
	return regras.join('\n');
}

// ---------------------------------------------------------------- SVG
const NS = 'http://www.w3.org/2000/svg';
const escapar = (t: string) =>
	t.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

/** O gráfico da figura (o que vale exportar): os pequenos múltiplos inteiros (`[data-multiplos]`, cada filho um painel
 * com um SVG e o título), ou o primeiro gráfico SVG, ignorando ícones e sparklines pequenas. */
export function graficoDe(figura: HTMLElement): SVGSVGElement | HTMLElement | null {
	const multiplos = figura.querySelector<HTMLElement>('.grafico [data-multiplos]');
	if (multiplos?.querySelector('svg')) return multiplos;
	const svgs = Array.from(figura.querySelectorAll<SVGSVGElement>('.grafico svg'));
	return svgs.find((s) => s.getBoundingClientRect().width >= 200) ?? null;
}

/** Os pequenos múltiplos num SVG só: cada painel na posição da tela, com o título em `<text>` e a opacidade dele
 * (um painel apagado pelo recorte continua apagado). */
function clonarMultiplos(container: HTMLElement): SVGSVGElement {
	const base = container.getBoundingClientRect();
	const saida = document.createElementNS(NS, 'svg') as SVGSVGElement;
	saida.setAttribute('viewBox', `0 0 ${base.width} ${base.height}`);
	for (const painel of Array.from(container.children) as HTMLElement[]) {
		const svg = painel.querySelector<SVGSVGElement>('svg');
		if (!svg) continue;
		const grupo = document.createElementNS(NS, 'g');
		const opacidade = getComputedStyle(painel).opacity;
		if (opacidade && opacidade !== '1') grupo.setAttribute('opacity', opacidade);
		const r = svg.getBoundingClientRect();
		const clone = svg.cloneNode(true) as SVGSVGElement;
		fixarEstilos(svg, clone);
		for (const [nome, valor] of [['x', r.left - base.left], ['y', r.top - base.top], ['width', r.width], ['height', r.height]] as const)
			clone.setAttribute(nome, String(valor));
		clone.removeAttribute('style');
		const titulo = painel.querySelector<HTMLElement>('[data-titulo-painel], h3, .titulo-multiplo');
		if (titulo) {
			const t = titulo.getBoundingClientRect();
			const e = getComputedStyle(titulo);
			const texto = document.createElementNS(NS, 'text');
			texto.textContent = (titulo.textContent ?? '').replace(/\s+/g, ' ').trim();
			texto.setAttribute('x', String(t.left - base.left));
			texto.setAttribute('y', String(t.top - base.top + parseFloat(e.fontSize)));
			texto.setAttribute('style', `font-family:${e.fontFamily};font-size:${e.fontSize};font-weight:${e.fontWeight};fill:${e.color}`);
			grupo.append(texto);
		}
		grupo.append(clone);
		saida.append(grupo);
	}
	return saida;
}

/**
 * Um gráfico em canvas (a rede) com um SVG por cima (os rótulos): o componente pendura no canvas uma função que o
 * redesenha nas cores do tema aplicado e devolve o PNG, que entra embaixo do SVG na figura exportada.
 */
type Rasterizavel = HTMLElement & { rasterizar?: () => string };

/** A amostra de um item de legenda: um círculo, um quadrado, um traço ou uma hachura, com a cor resolvida no tema. */
export interface AmostraLegenda {
	forma: 'circulo' | 'quadrado' | 'linha' | 'hachura';
	cor: string;
	opacidade: number;
	/** A espessura do traço (`linha`). */
	largura?: number;
	/** O fundo da hachura. */
	fundo?: string;
}

/** Um item de legenda da figura (`[data-legenda] li`): o texto e a amostra. */
export interface ItemLegenda {
	texto: string;
	/** Um título ("Peso da parceria:"), que começa uma linha nova. */
	titulo: boolean;
	amostra: AmostraLegenda | null;
}

const transparente = (cor: string) => !cor || cor === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(cor);

/** A amostra de um item: a hachura (um `rect` com `fill="url(#…)"`), o traço (`svg line`) ou a cor de fundo de um
 * `span` (`.bolinha`/`.cor`, um círculo; `.caixa`/`.amostra`, um quadrado). */
function amostraDe(li: HTMLElement, figura: HTMLElement): AmostraLegenda | null {
	const hachura = li.querySelector<SVGRectElement>('svg rect[fill^="url("]');
	if (hachura) {
		const id = hachura.getAttribute('fill')!.match(/url\(#([^)]+)\)/)?.[1];
		const padrao = id ? figura.querySelector(`[id="${CSS.escape(id)}"]`) : null;
		const traco = padrao?.querySelector('line, path');
		const fundo = padrao?.querySelector('rect');
		return {
			forma: 'hachura',
			cor: traco ? getComputedStyle(traco).stroke : getComputedStyle(li).color,
			fundo: fundo ? getComputedStyle(fundo).fill : 'none',
			opacidade: 1
		};
	}
	const linha = li.querySelector<SVGLineElement>('svg line');
	if (linha) {
		const t = getComputedStyle(linha);
		return { forma: 'linha', cor: t.stroke, largura: parseFloat(t.strokeWidth) || 1, opacidade: Number(t.opacity) || 1 };
	}
	const span = li.querySelector<HTMLElement>('.bolinha, .cor, .caixa, .amostra');
	if (!span) return null;
	const s = getComputedStyle(span);
	if (transparente(s.backgroundColor)) return null;
	const forma = span.matches('.caixa, .amostra') ? 'quadrado' : 'circulo';
	return { forma, cor: s.backgroundColor, opacidade: Number(s.opacity) || 1 };
}

/** As legendas em HTML da figura (listas com `data-legenda`; o valor do atributo, se houver, é o título), com as cores
 * do tema aplicado no momento. */
export function legendaDe(figura: HTMLElement): ItemLegenda[] {
	const itens: ItemLegenda[] = [];
	for (const lista of figura.querySelectorAll<HTMLElement>('.grafico [data-legenda]')) {
		const titulo = lista.dataset.legenda?.trim();
		if (titulo) itens.push({ texto: titulo, titulo: true, amostra: null });
		for (const li of lista.querySelectorAll<HTMLElement>(':scope > li')) {
			const texto = (li.textContent ?? '').replace(/\s+/g, ' ').trim();
			if (!texto) continue;
			itens.push({ texto, titulo: li.classList.contains('titulo-legenda'), amostra: amostraDe(li, figura) });
		}
	}
	return itens;
}

export interface OpcoesLegenda {
	x: number;
	y: number;
	/** A largura disponível: nada passa dela. */
	largura: number;
	/** A escala do texto da figura. */
	k: number;
	fonte: string;
	cor: string;
	/** A largura de um texto no tamanho dado (o `measureText` do canvas, com a fonte da figura). */
	medir: (texto: string, tamanho: number) => number;
}

/** Quebra o texto por palavras em linhas de até `largura`. */
function quebrar(texto: string, largura: number, tamanho: number, medir: OpcoesLegenda['medir']): string[] {
	const linhas: string[] = [];
	let atual = '';
	for (const palavra of texto.split(' ')) {
		const tentativa = atual ? `${atual} ${palavra}` : palavra;
		if (atual && medir(tentativa, tamanho) > largura) {
			linhas.push(atual);
			atual = palavra;
		} else atual = tentativa;
	}
	return atual ? [...linhas, atual] : linhas;
}

/** A legenda em SVG nativo (sem `foreignObject`, que o PNG não desenha em todo navegador): os itens lado a lado, em
 * linhas que quebram na largura, e o texto de um item longo em mais de uma linha. Devolve o SVG, as definições
 * (as hachuras) e a altura ocupada. */
export function legendaEmSvg(itens: ItemLegenda[], o: OpcoesLegenda): { svg: string; defs: string; altura: number } {
	if (!itens.length) return { svg: '', defs: '', altura: 0 };
	const { x: x0, largura: w, k, medir } = o;
	const tamanho = 11 * k;
	const passo = 15 * k;
	const separacao = 14 * k;
	const partes: string[] = [];
	const defs: string[] = [];
	let x = x0;
	let y = o.y + tamanho;
	itens.forEach((it, n) => {
		const amostra = it.amostra ? 16 * k : 0;
		const linhas = quebrar(it.texto, w - amostra, tamanho, medir);
		const largura = amostra + Math.max(...linhas.map((l) => medir(l, tamanho)));
		if (x > x0 && (it.titulo || linhas.length > 1 || x + largura > x0 + w)) [x, y] = [x0, y + passo + 2 * k];
		const meio = y - tamanho * 0.35;
		const a = it.amostra;
		if (a?.forma === 'circulo') {
			partes.push(`<circle cx="${x + 5 * k}" cy="${meio}" r="${4.5 * k}" fill="${a.cor}" fill-opacity="${a.opacidade}"/>`);
		} else if (a?.forma === 'quadrado') {
			partes.push(`<rect x="${x}" y="${meio - 5 * k}" width="${10 * k}" height="${10 * k}" fill="${a.cor}" fill-opacity="${a.opacidade}"/>`);
		} else if (a?.forma === 'linha') {
			partes.push(
				`<line x1="${x}" x2="${x + 12 * k}" y1="${meio}" y2="${meio}" stroke="${a.cor}" stroke-width="${(a.largura ?? 1) * k}" stroke-opacity="${a.opacidade}" stroke-linecap="round"/>`
			);
		} else if (a?.forma === 'hachura') {
			const id = `leg-hachura-${n}`;
			defs.push(
				`<pattern id="${id}" width="${4 * k}" height="${4 * k}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="${4 * k}" height="${4 * k}" fill="${a.fundo ?? 'none'}"/><line x1="0" y1="0" x2="0" y2="${4 * k}" stroke="${a.cor}" stroke-width="${1.5 * k}"/></pattern>`
			);
			partes.push(`<rect x="${x}" y="${meio - 5 * k}" width="${10 * k}" height="${10 * k}" fill="url(#${id})" stroke="${a.cor}" stroke-width="${0.5 * k}"/>`);
		}
		linhas.forEach((linha, j) => {
			const peso = it.titulo ? ' font-weight="600"' : '';
			partes.push(
				`<text x="${x + amostra}" y="${y + j * passo}" font-family="${escapar(o.fonte)}" font-size="${tamanho}" fill="${o.cor}"${peso}>${escapar(linha)}</text>`
			);
		});
		y += (linhas.length - 1) * passo;
		if (linhas.length > 1) [x, y] = [x0 + w + 1, y]; // depois de um item longo, o próximo começa outra linha
		else x += largura + separacao;
	});
	return { svg: partes.join('\n'), defs: defs.join(''), altura: y - o.y + passo * 0.6 };
}

/** Mede um texto com o `measureText` do canvas, na família dada (depois de as fontes carregarem). */
function medidor(fonte: string): OpcoesLegenda['medir'] {
	const ctx = document.createElement('canvas').getContext('2d');
	return (texto, tamanho) => {
		if (!ctx) return texto.length * tamanho * 0.55;
		ctx.font = `${tamanho}px ${fonte}`;
		return ctx.measureText(texto).width;
	};
}

export async function montarSvg(figura: HTMLElement, meta: Metadados, preset: Preset): Promise<string | null> {
	const grafico = graficoDe(figura);
	if (!grafico) return null;
	const multiplos = !(grafico instanceof SVGSVGElement);
	const caixa = grafico.getBoundingClientRect();
	const w = caixa.width;
	const h = caixa.height;
	const tema = preset.tema;
	const raster = figura.querySelector<Rasterizavel>('.grafico [data-rasterizavel]');
	const { clone, fundo, texto, suave, familias, imagem, legenda } = comTema(tema, () => {
		const imagem = raster?.rasterizar?.() ?? null;
		const legenda = legendaDe(figura);
		let clone: SVGSVGElement;
		if (multiplos) clone = clonarMultiplos(grafico);
		else {
			clone = grafico.cloneNode(true) as SVGSVGElement;
			fixarEstilos(grafico, clone);
		}
		const s = getComputedStyle(document.body);
		const familias = new Set<string>();
		for (const el of [grafico, ...grafico.querySelectorAll('text, h3, .titulo-multiplo, [data-titulo-painel]')]) {
			getComputedStyle(el)
				.fontFamily.split(',')
				.forEach((f) => familias.add(f.replaceAll(/['"]/g, '').trim()));
		}
		const raiz = getComputedStyle(document.documentElement);
		familias.add(raiz.getPropertyValue('--fonte-titulo').split(',')[0].replaceAll(/['"]/g, '').trim());
		familias.add(raiz.getPropertyValue('--fonte-interface').split(',')[0].replaceAll(/['"]/g, '').trim());
		return {
			clone,
			imagem,
			legenda,
			// o fundo do tema fica no <html> (o <body> é transparente): sem ele, o PNG saía transparente, e o título
			// quase branco do Observatório sumia num slide claro
			fundo: raiz.getPropertyValue('--fundo').trim() || raiz.backgroundColor,
			texto: raiz.getPropertyValue('--texto').trim() || s.color,
			suave: raiz.getPropertyValue('--texto-suave').trim() || s.color,
			familias
		};
	});
	const raiz = getComputedStyle(document.documentElement);
	const fonteTitulo = raiz.getPropertyValue('--fonte-titulo').trim();
	const fonteTexto = raiz.getPropertyValue('--fonte-interface').trim();
	const k = preset.escalaTexto * Math.max(0.8, w / 900);
	const margem = 24 * k;
	const topo = margem + 30 * k + (meta.recorte ? 22 * k : 0) + 12 * k;
	const rodape = 22 * k + margem;
	const W = w + 2 * margem;
	await document.fonts?.ready; // o measureText precisa das fontes carregadas
	const leg = legendaEmSvg(legenda, { x: margem, y: topo + h + 12 * k, largura: w, k, fonte: fonteTexto, cor: suave, medir: medidor(fonteTexto) });
	const H = topo + h + (leg.altura ? leg.altura + 12 * k : 0) + rodape;
	const fontes = await fontesEmbutidas(familias);
	const data = new Date().toLocaleDateString('pt-BR');
	const linhaRodape = [
		meta.fonte,
		meta.n !== null ? `n = ${meta.n.toLocaleString('pt-BR')}` : '',
		`mapa-da-ciencia, ${data}`
	]
		.filter(Boolean)
		.join(' · ');
	clone.setAttribute('x', String(margem));
	clone.setAttribute('y', String(topo));
	clone.setAttribute('width', String(w));
	clone.setAttribute('height', String(h));
	clone.removeAttribute('style');
	const final = preset.largura;
	const tamanho =
		'mm' in final
			? `width="${final.mm}mm" height="${((final.mm * H) / W).toFixed(2)}mm"`
			: `width="${W}" height="${H}"`;
	return [
		`<svg xmlns="${NS}" ${tamanho} viewBox="0 0 ${W} ${H}">`,
		`<defs><style>${fontes}</style>${leg.defs}</defs>`,
		`<rect width="${W}" height="${H}" fill="${fundo}"/>`,
		`<text x="${margem}" y="${margem + 24 * k}" font-family="${escapar(fonteTitulo)}" font-size="${24 * k}" fill="${texto}">${escapar(meta.titulo)}</text>`,
		meta.recorte
			? `<text x="${margem}" y="${margem + 50 * k}" font-family="${escapar(fonteTexto)}" font-size="${13 * k}" fill="${suave}">${escapar(meta.recorte)}</text>`
			: '',
		imagem ? `<image href="${imagem}" x="${margem}" y="${topo}" width="${w}" height="${h}"/>` : '',
		new XMLSerializer().serializeToString(clone),
		leg.svg,
		`<text x="${margem}" y="${H - margem}" font-family="${escapar(fonteTexto)}" font-size="${11 * k}" fill="${suave}">${escapar(linhaRodape)}</text>`,
		'</svg>'
	].join('\n');
}

/** O SVG rasterizado na largura do preset. */
export async function paraPng(svg: string, largura: number): Promise<Blob> {
	const erroXml = new DOMParser().parseFromString(svg, 'image/svg+xml').querySelector('parsererror');
	if (erroXml) throw new Error(`o SVG ficou inválido (${erroXml.textContent?.slice(0, 160)})`);
	const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
	try {
		const img = new Image();
		img.decoding = 'sync';
		await new Promise<void>((resolver, rejeitar) => {
			img.onload = () => resolver();
			img.onerror = () => rejeitar(new Error('não foi possível desenhar o SVG'));
			img.src = url;
		});
		const vb = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/)!;
		const escala = largura / Number(vb[1]);
		const canvas = document.createElement('canvas');
		canvas.width = Math.round(largura);
		canvas.height = Math.round(Number(vb[2]) * escala);
		const ctx = canvas.getContext('2d')!;
		ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
		return await new Promise<Blob>((resolver, rejeitar) =>
			canvas.toBlob((b) => (b ? resolver(b) : rejeitar(new Error('PNG vazio'))), 'image/png')
		);
	} finally {
		URL.revokeObjectURL(url);
	}
}

export function baixar(conteudo: Blob | string, nome: string, tipo = 'text/plain') {
	const blob = typeof conteudo === 'string' ? new Blob([conteudo], { type: tipo }) : conteudo;
	const url = URL.createObjectURL(blob);
	const a = Object.assign(document.createElement('a'), { href: url, download: nome });
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** `Por ano` → `por-ano`, para o nome do arquivo. */
export const nomeDeArquivo = (titulo: string) =>
	titulo
		.normalize('NFKD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '') || 'figura';
