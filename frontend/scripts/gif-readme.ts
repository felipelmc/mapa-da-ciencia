// Gera o GIF do README (docs/imagens/painel.gif) a partir dos dados de um projeto: o Mapa ano a ano, o mapa
// inteiro, os Tópicos no tempo, a Geografia e a Classificação.
//
// Uso (da pasta frontend/, depois de `npm run build`):
//   node scripts/gif-readme.ts ../projetos/cp-scielo
//
// Como as capturas (scripts/capturas.ts), roda só localmente: o piloto não está no repositório. Os quadros são
// capturas do Playwright; a codificação em GIF (gifenc, paleta de 128 cores por quadro) roda dentro do próprio
// navegador, que já sabe ler PNG, e o arquivo volta pronto. Nenhum cartão de documento é aberto: os resumos sem
// licença aberta não podem ir para o README.
import { chromium, type Page } from '@playwright/test';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { servir } from '../tests/e2e/servidor.ts';

const FRONTEND = fileURLToPath(new URL('..', import.meta.url));
const DESTINO = join(FRONTEND, '..', 'docs', 'imagens', 'painel.gif');
const LARGURA = 1280;
const ALTURA = 800;
const LARGURA_GIF = 880;

const projeto = resolve(process.argv[2] ?? join(FRONTEND, '..', 'projetos', 'cp-scielo'));
const dados = join(projeto, 'saida', 'dados');
if (!existsSync(join(dados, 'documentos.json'))) {
	console.error(`Falta ${join(dados, 'documentos.json')}: rode as etapas do projeto antes.`);
	process.exit(1);
}
if (!existsSync(join(FRONTEND, 'build', 'index.html'))) {
	console.error('Falta o build da interface: rode `npm run build` antes.');
	process.exit(1);
}

/** O gifenc em ESM, transformado num script comum que o põe em `window.gifenc`. */
function gifencParaPagina(): string {
	const fonte = readFileSync(join(FRONTEND, 'node_modules', 'gifenc', 'dist', 'gifenc.esm.js'), 'utf8').replace(/\/\/# sourceMappingURL=.*$/m, '');
	return fonte.replace(/export\s*\{([^}]*)\};?\s*$/, (_, lista: string) => {
		const pares = lista.split(',').map((p) => p.trim().split(/\s+as\s+/));
		return `window.gifenc = {${pares.map(([local, nome]) => `${nome}: ${local}`).join(', ')}};`;
	});
}

interface Quadro {
	png: Buffer;
	espera: number; // ms
}

async function esperarMapa(page: Page) {
	await page.waitForFunction(() => window.__mapaDebug?.desenhado || window.__mapaDebug?.erro, null, { timeout: 30_000 });
	await page.waitForTimeout(700);
}

/** Recolhe o painel lateral do Mapa: mais céu na imagem (depois da troca de rota, que o reabre). */
async function recolher(page: Page) {
	const botao = page.getByRole('button', { name: 'Recolher' });
	if (await botao.isVisible()) await botao.click();
}

const site = mkdtempSync(join(tmpdir(), 'mapa-gif-'));
cpSync(join(FRONTEND, 'build'), site, { recursive: true });
mkdirSync(join(site, 'dados'));
cpSync(dados, join(site, 'dados'), { recursive: true });
const manifesto = JSON.parse(readFileSync(join(site, 'dados', 'manifesto.json'), 'utf8'));
// a versão no rodapé é a da interface (a do pacote na release), não a do código que gerou os dados
const versao: string = JSON.parse(readFileSync(join(FRONTEND, 'package.json'), 'utf8')).version;
writeFileSync(
	join(site, 'dados', 'manifesto.json'),
	JSON.stringify({ ...manifesto, api: false, execucao: { ...manifesto.execucao, versao_pacote: versao } })
);
const anos: [number, number] = manifesto.recorte.anos;

const servidor = await servir(site);
const navegador = await chromium.launch();
try {
	const contexto = await navegador.newContext({ viewport: { width: LARGURA, height: ALTURA }, colorScheme: 'dark' });
	const page = await contexto.newPage();
	const quadros: Quadro[] = [];
	const capturar = async (espera: number) => quadros.push({ png: await page.screenshot(), espera });

	// o mapa, ano a ano: os pontos de cada ano acendem no lugar deles
	await page.goto(`${servidor.origem}/#/mapa?cor=macrotema`);
	await esperarMapa(page);
	const passo = Math.max(1, Math.round((anos[1] - anos[0]) / 7));
	for (let ano = anos[0]; ano <= anos[1]; ano += passo) {
		await page.goto(`${servidor.origem}/#/mapa?cor=macrotema&anos=${ano}-${ano}`);
		await page.waitForTimeout(700);
		await recolher(page);
		await page.waitForTimeout(400);
		await capturar(650);
	}
	await page.goto(`${servidor.origem}/#/mapa?cor=macrotema`);
	await page.waitForTimeout(900);
	await recolher(page);
	await page.waitForTimeout(600);
	await capturar(2200);

	for (const rota of ['/topicos', '/geografia', '/classificacao?variavel=abordagem']) {
		await page.goto(`${servidor.origem}/#${rota}`);
		await page.waitForTimeout(2500);
		await capturar(2600);
	}

	// a codificação em GIF, no navegador
	const codificador = await contexto.newPage();
	await codificador.goto(`${servidor.origem}/dados/manifesto.json`);
	await codificador.addScriptTag({ content: gifencParaPagina() });
	const base64 = await codificador.evaluate(
		async ({ quadros, largura }) => {
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			const { GIFEncoder, quantize, applyPalette } = (window as any).gifenc;
			const gif = GIFEncoder();
			for (const q of quadros) {
				const imagem = await createImageBitmap(await (await fetch(`data:image/png;base64,${q.png}`)).blob());
				const altura = Math.round((imagem.height * largura) / imagem.width);
				const tela = new OffscreenCanvas(largura, altura);
				const ctx = tela.getContext('2d')!;
				ctx.imageSmoothingQuality = 'high';
				ctx.drawImage(imagem, 0, 0, largura, altura);
				const { data } = ctx.getImageData(0, 0, largura, altura);
				const paleta = quantize(data, 128);
				gif.writeFrame(applyPalette(data, paleta), largura, altura, { palette: paleta, delay: q.espera });
			}
			gif.finish();
			const bytes: Uint8Array = gif.bytes();
			let binario = '';
			for (let i = 0; i < bytes.length; i += 0x8000) binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
			return btoa(binario);
		},
		{ quadros: quadros.map((q) => ({ png: q.png.toString('base64'), espera: q.espera })), largura: LARGURA_GIF }
	);
	writeFileSync(DESTINO, Buffer.from(base64, 'base64'));
	console.log(`${DESTINO} (${quadros.length} quadros, ${Math.round(statSync(DESTINO).size / 1024)} KB)`);
} finally {
	await navegador.close();
	await servidor.fechar();
	rmSync(site, { recursive: true, force: true });
}
