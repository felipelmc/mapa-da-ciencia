import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

// Confere o contraste (WCAG 2.x) dos pares de cor usados como texto, nos dois temas.
// Os valores são lidos de tokens.css, então uma mudança de cor que quebre o AA falha aqui.

const css = readFileSync(join(import.meta.dirname, 'tokens.css'), 'utf8');

function tokensDo(seletor: string): Record<string, string> {
	const i = css.indexOf(seletor);
	if (i < 0) throw new Error(`bloco ${seletor} não encontrado em tokens.css`);
	const bloco = css.slice(css.indexOf('{', i) + 1, css.indexOf('}', i));
	return Object.fromEntries([...bloco.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((m) => [m[1], m[2]]));
}

function luminancia(hex: string): number {
	const [r, g, b] = [1, 3, 5].map((i) => {
		const c = parseInt(hex.slice(i, i + 2), 16) / 255;
		return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contraste(a: string, b: string): number {
	const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
	return (claro + 0.05) / (escuro + 0.05);
}

const TEMAS = {
	observatorio: tokensDo(":root[data-tema='observatorio']"),
	prancha: tokensDo(":root[data-tema='prancha']")
};

/** [texto, fundo, mínimo]. 4,5 = AA para texto normal; 3 = componentes e itens desativados. */
const PARES: [string, string, number][] = [
	['texto', 'fundo', 4.5],
	['texto', 'superficie', 4.5],
	['texto', 'superficie-alta', 4.5],
	['texto-suave', 'fundo', 4.5],
	['texto-suave', 'superficie', 4.5],
	['texto-suave', 'superficie-alta', 4.5],
	['acento', 'fundo', 4.5],
	['acento', 'superficie', 4.5],
	['sobre-acento', 'acento', 4.5],
	['foco', 'fundo', 3],
	['foco', 'superficie', 3],
	['texto-fraco', 'fundo', 3],
	['texto-fraco', 'superficie', 3]
];

describe.each(Object.entries(TEMAS))('contraste no tema %s', (_, tokens) => {
	it.each(PARES)('%s sobre %s ≥ %s:1', (frente, fundo, minimo) => {
		expect(tokens[frente], `--${frente}`).toBeDefined();
		expect(tokens[fundo], `--${fundo}`).toBeDefined();
		expect(contraste(tokens[frente], tokens[fundo])).toBeGreaterThanOrEqual(minimo);
	});
});

it('usa as cores de base pedidas para cada tema', () => {
	expect(TEMAS.observatorio).toMatchObject({
		fundo: '#0a0e1f',
		superficie: '#111733',
		texto: '#eceaf4',
		acento: '#ffb547'
	});
	expect(TEMAS.prancha).toMatchObject({
		fundo: '#f6f2e9',
		texto: '#161a2b',
		linha: '#dcd3c2',
		acento: '#c2410c'
	});
});

// ---- o uso dos tokens nos componentes

const SRC = join(import.meta.dirname, '..', '..');

function arquivosSvelte(pasta: string): string[] {
	return readdirSync(pasta, { withFileTypes: true }).flatMap((e) =>
		e.isDirectory() ? arquivosSvelte(join(pasta, e.name)) : e.name.endsWith('.svelte') ? [join(pasta, e.name)] : []
	);
}

/** `a` sobre `b` com opacidade `p` (como `color-mix(in oklab, a p%, transparent)` sobre o fundo `b`). */
function misturar(a: string, b: string, p: number): string {
	const canal = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
	return `#${[1, 3, 5]
		.map((i) => Math.round(p * canal(a, i) + (1 - p) * canal(b, i)).toString(16).padStart(2, '0'))
		.join('')}`;
}

it('--texto-fraco só pinta o texto de itens desativados', () => {
	// a regra do tokens.css, conferida onde o token é usado: texto que informa (créditos, notas, intervalos) usa
	// --texto-suave, que passa no AA
	const fora: string[] = [];
	for (const arquivo of arquivosSvelte(SRC)) {
		const texto = readFileSync(arquivo, 'utf8');
		if (!texto.includes('<style')) continue;
		for (const [, seletor, corpo] of texto.slice(texto.indexOf('<style')).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
			if (!/(^|[\s;])color:\s*var\(--texto-fraco\)/.test(corpo)) continue;
			const partes = seletor.split(',').map((x) => x.trim());
			if (partes.every((x) => /:disabled|\.desativado/.test(x))) continue;
			fora.push(`${relative(SRC, arquivo)}: ${partes.join(', ')}`);
		}
	}
	expect(fora).toEqual([]);
});

it('a diagonal da matriz de confusão deixa o texto com contraste AA, até na célula mais forte', () => {
	const matriz = readFileSync(join(SRC, 'lib', 'validacao', 'MatrizConfusao.svelte'), 'utf8');
	const p = Number(matriz.match(/td\.diagonal\s*\{[^}]*var\(--acento\) calc\(var\(--intensidade\) \* (\d+)%\)/)![1]) / 100;
	for (const t of Object.values(TEMAS)) {
		expect(contraste(t.texto, misturar(t.acento, t.superficie, p))).toBeGreaterThanOrEqual(4.5);
	}
});
