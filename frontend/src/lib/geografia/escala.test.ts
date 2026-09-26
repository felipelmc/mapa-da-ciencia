import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { classe, corDaClasse, quebras, redondo } from './escala';

describe('escala dos mapas', () => {
	it('números redondos', () => {
		expect([0.8, 1.4, 3, 4, 7, 13, 30, 380].map(redondo)).toEqual([1, 1, 2, 5, 5, 10, 20, 500]);
	});

	it('quebras em escala logarítmica, sem repetir', () => {
		const q = quebras([2.5, 5.8, 40, 107, 340, 924]);
		expect(q).toEqual([5, 20, 50, 100, 500]);
		expect(quebras([3, 3.5])).toEqual([]); // valores parecidos: uma classe só
		expect(quebras([0, 0, 7])).toEqual([]);
	});

	it('classes e cores', () => {
		const q = [5, 20, 50];
		expect([0, 2, 5, 19, 20, 60].map((v) => classe(v, q))).toEqual([0, 1, 2, 2, 3, 4]);
		expect(corDaClasse(0, 4)).toBe('var(--seq-vazio)');
		expect([1, 2, 3, 4].map((c) => corDaClasse(c, 4))).toEqual(['var(--seq-1)', 'var(--seq-3)', 'var(--seq-4)', 'var(--seq-6)']);
		expect(corDaClasse(1, 1)).toBe('var(--seq-6)');
	});
});

// ---- contraste dos tokens (WCAG 2: luminância relativa)
const css = readFileSync(join(import.meta.dirname, '../estilos/tokens.css'), 'utf8');

function bloco(seletor: string): Record<string, string> {
	const inicio = css.indexOf(seletor);
	const corpo = css.slice(css.indexOf('{', inicio) + 1, css.indexOf('}', inicio));
	return Object.fromEntries([...corpo.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}

function luminancia(hex: string): number {
	const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
	const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
	return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contraste(a: string, b: string): number {
	const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
}

describe.each([
	['observatorio', ":root[data-tema='observatorio']", 1],
	['prancha', ":root[data-tema='prancha']", -1]
])('tokens sequenciais do tema %s', (_, seletor, sentido) => {
	const t = bloco(seletor);
	const tons = [1, 2, 3, 4, 5, 6].map((i) => t[`seq-${i}`]);

	it('existem e mudam de claridade sempre no mesmo sentido', () => {
		expect(tons.every(Boolean) && t['seq-vazio']).toBeTruthy();
		for (let i = 1; i < tons.length; i += 1) {
			expect(Math.sign(luminancia(tons[i]) - luminancia(tons[i - 1]))).toBe(sentido);
			expect(contraste(tons[i], tons[i - 1])).toBeGreaterThan(1.2); // tons vizinhos distinguíveis
		}
	});

	it('o tom mais forte se destaca do fundo, e o vazio não some nele', () => {
		expect(contraste(tons[5], t.fundo)).toBeGreaterThanOrEqual(3); // WCAG 1.4.11, contraste de gráficos
		expect(contraste(t['seq-vazio'], t.fundo)).toBeGreaterThan(1.05);
		expect(contraste(t['seq-vazio'], tons[0])).toBeGreaterThan(1.1);
	});
});
