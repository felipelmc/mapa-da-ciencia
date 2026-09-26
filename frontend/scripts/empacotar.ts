// Copia o build do frontend para dentro do pacote Python, de onde o `mapa painel` o serve.
//
// Uso: npm run empacotar            (faz o build e copia para ../src/mapa_da_ciencia/web/estatico/)
//      node scripts/empacotar.ts <destino>   (copia o build atual para outra pasta)
//
// O destino é apagado antes da cópia, para não sobrar arquivo de um build antigo. Ele fica
// fora do git (.gitignore da raiz): o wheel recebe o build no CI.
import { cpSync, existsSync, readdirSync, rmSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = fileURLToPath(new URL('..', import.meta.url));
const BUILD = join(RAIZ, 'build');
const PADRAO = resolve(RAIZ, '..', 'src', 'mapa_da_ciencia', 'web', 'estatico');
const destino = resolve(process.argv[2] ?? PADRAO);

if (!existsSync(join(BUILD, 'index.html'))) {
	console.error('build/index.html não existe. Rode `npm run build` antes (ou use `npm run empacotar`).');
	process.exit(1);
}
// Proteção contra um destino errado: nunca apagar a raiz do frontend nem uma pasta que o contém.
if (RAIZ.startsWith(destino + '/') || destino === RAIZ.replace(/\/$/, '') || destino === BUILD) {
	console.error(`destino recusado: ${destino}`);
	process.exit(1);
}

rmSync(destino, { recursive: true, force: true });
cpSync(BUILD, destino, { recursive: true });
const n = readdirSync(destino, { recursive: true }).length;
console.log(`build copiado para ${relative(process.cwd(), destino) || destino} (${n} entradas).`);
