// Pós-build (ADR 0002): troca os caminhos absolutos "/_app/..." do index.html por
// relativos "./_app/...", para que o mesmo build funcione na raiz e num subcaminho
// (por exemplo, /mapa-da-ciencia/demo/ no GitHub Pages).
//
// Com o router por hash, o SvelteKit gera o index.html pela rotina da página de fallback,
// que ignora `paths.relative` e escreve "/_app/..." nos <link> e nos import(). Os chunks JS
// já se importam entre si por caminho relativo; só o index.html precisa do ajuste.
//
// Uso: node scripts/relativizar-index.ts <pasta-do-build>
//
// Falha (código 1) se não achar nenhum "/_app/" para trocar ou se sobrar algum depois:
// os dois casos indicam que o formato do HTML do SvelteKit mudou e o contorno precisa ser
// revisto. A alternativa registrada no ADR é `output.bundleStrategy: 'inline'`.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const pasta = process.argv[2];
if (!pasta) {
	console.error('uso: node scripts/relativizar-index.ts <pasta-do-build>');
	process.exit(2);
}

const arquivo = join(pasta, 'index.html');
if (!existsSync(arquivo)) {
	console.error(`${arquivo} não existe; o build rodou?`);
	process.exit(1);
}

const html = readFileSync(arquivo, 'utf8');
const trocas = html.split('"/_app/').length - 1;
const novo = html.replaceAll('"/_app/', '"./_app/');

if (trocas === 0) {
	console.error(`${arquivo}: nenhum "/_app/" encontrado. O formato do index.html mudou? Ver ADR 0002.`);
	process.exit(1);
}
if (/["'(]\/_app\//.test(novo)) {
	console.error(`${arquivo}: ainda há caminhos absolutos "/_app/" depois da troca. Ver ADR 0002.`);
	process.exit(1);
}

writeFileSync(arquivo, novo);
console.log(`${arquivo}: ${trocas} caminho(s) "/_app/" trocados por "./_app/".`);
