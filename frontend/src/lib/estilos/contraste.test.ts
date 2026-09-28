import { readFileSync } from 'node:fs';
import { join } from 'node:path';
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
	['texto-fraco', 'superficie', 3],
	// os números da matriz das citações, sobre cada tom da escala sequencial
	['sobre-seq-1', 'seq-1', 4.5],
	['sobre-seq-2', 'seq-2', 4.5],
	['sobre-seq-3', 'seq-3', 4.5],
	['sobre-seq-4', 'seq-4', 4.5],
	['sobre-seq-5', 'seq-5', 4.5],
	['sobre-seq-6', 'seq-6', 4.5],
	['texto-suave', 'seq-vazio', 4.5]
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
