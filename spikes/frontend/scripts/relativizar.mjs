// Contorno testado no spike M0d: copia um build e troca, no index.html, os caminhos
// absolutos "/_app/..." por relativos "./_app/...". Os chunks JS já se importam entre si
// por caminho relativo; só o index.html gerado pelo SvelteKit usa caminho absoluto.
//
// Uso: node scripts/relativizar.mjs <build-origem> <build-destino>
import { cpSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [origem, destino] = process.argv.slice(2);
if (!origem || !destino) {
	console.error('uso: node scripts/relativizar.mjs <build-origem> <build-destino>');
	process.exit(2);
}

rmSync(destino, { recursive: true, force: true });
cpSync(origem, destino, { recursive: true });

const arquivo = join(destino, 'index.html');
const html = readFileSync(arquivo, 'utf8');
const novo = html.replaceAll('"/_app/', '"./_app/');
const trocas = html.split('"/_app/').length - 1;
writeFileSync(arquivo, novo);
console.log(`${arquivo}: ${trocas} caminho(s) "/_app/" trocados por "./_app/"`);
