import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { expect, it } from 'vitest';

// A "regra de lint" do ADR 0002, como teste: links internos passam por `rota()`.
// - `resolve()` de `$app/paths` gera `/sub#/rota` num subcaminho e força recarga completa;
// - `href="/..."` e `goto('/...')` absolutos quebram quando o app é servido num subcaminho.

const SRC = join(import.meta.dirname, '..', '..');

function arquivos(pasta: string): string[] {
	return readdirSync(pasta, { withFileTypes: true }).flatMap((e) => {
		const caminho = join(pasta, e.name);
		if (e.isDirectory()) return arquivos(caminho);
		return /\.(svelte|ts|js)$/.test(e.name) && !/\.test\.ts$/.test(e.name) ? [caminho] : [];
	});
}

const REGRAS: [RegExp, string][] = [
	[/import\s*\{[^}]*\bresolve\b[^}]*\}\s*from\s*['"]\$app\/paths['"]/, 'resolve() de $app/paths'],
	[/\bhref=["'{`]*\/(?!\/)/, 'href absoluto ("/..."); use rota()'],
	[/\bgoto\(\s*["'`]\//, 'goto() com caminho absoluto; use rota()']
];

it('nenhum arquivo de src/ usa resolve() nem links absolutos', () => {
	const problemas: string[] = [];
	for (const arquivo of arquivos(SRC)) {
		const texto = readFileSync(arquivo, 'utf8');
		for (const [regra, motivo] of REGRAS) {
			if (regra.test(texto)) problemas.push(`${relative(SRC, arquivo)}: ${motivo}`);
		}
	}
	expect(problemas).toEqual([]);
});
