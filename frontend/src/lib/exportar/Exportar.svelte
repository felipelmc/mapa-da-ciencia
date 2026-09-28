<script lang="ts">
	/**
	 * O botão "Exportar" de uma figura: escolhe o formato (SVG, PNG, CSV) e o preset (artigo, slide, telão) e baixa
	 * o arquivo. O cabeçalho do SVG e do PNG leva o título e o recorte; o rodapé, a fonte, o n e a data.
	 */
	import { usarProjeto } from '$lib/dados/contexto';
	import { filtrosDaPagina } from '$lib/estado/filtros';
	import { formatarPeriodo, nomeDaFonte } from '$lib/formato';
	import {
		baixar,
		graficoDe,
		larguraPx,
		montarSvg,
		nomeDeArquivo,
		paraCsv,
		paraPng,
		PRESETS,
		type DadosCsv,
		type Formato
	} from './figura';

	let {
		figura,
		titulo,
		colunas,
		linhas,
		dados = null,
		n = null
	}: {
		figura: HTMLElement | null;
		titulo: string;
		colunas: string[];
		linhas: (string | number)[][];
		/** Os números crus do CSV; sem eles, o CSV repete a tabela da tela (com os números já formatados). */
		dados?: DadosCsv | null;
		n?: number | null;
	} = $props();

	const { manifesto } = usarProjeto();
	let aberto = $state(false);
	let formato = $state<Formato>('svg');
	let preset = $state(PRESETS[1].id);
	let erro = $state<string | null>(null);
	let trabalhando = $state(false);
	// O mesmo critério da exportação (`graficoDe`: um SVG de 200 px ou mais, não as sparklines), medido ao abrir,
	// porque o tamanho na tela não é reativo. Sem gráfico, o CSV já vem escolhido.
	let temGrafico = $state(false);
	function alternar() {
		aberto = !aberto;
		if (!aberto) return;
		temGrafico = !!figura && graficoDe(figura) !== null;
		if (!temGrafico) formato = 'csv';
	}

	function recorteEmPalavras(): string {
		const f = filtrosDaPagina();
		// sem filtro de anos, o período só entra se o título do projeto já não o disser ("…, 2010–2025 · 2010–2025")
		const periodo = formatarPeriodo(f.anos ?? manifesto.recorte.anos);
		const partes = f.anos || !manifesto.projeto.titulo.includes(periodo) ? [periodo] : [];
		if (f.revistas.length) partes.push(`revistas: ${f.revistas.join(', ')}`);
		if (f.topicos.length) partes.push(`${f.topicos.length} tópico(s)`);
		if (f.busca) partes.push(`busca: "${f.busca}"`);
		if (f.laco) partes.push('seleção no mapa');
		if (f.uf.length) partes.push(`UF: ${f.uf.join(', ')}`);
		if (f.pais.length) partes.push(`país: ${f.pais.join(', ')}`);
		if (f.inst.length) partes.push(`${f.inst.length} instituição(ões)`);
		return [manifesto.projeto.titulo, ...partes].join(' · ');
	}

	async function exportar() {
		erro = null;
		trabalhando = true;
		const nome = nomeDeArquivo(titulo);
		try {
			if (formato === 'csv') {
				const csv = dados ?? { colunas, linhas };
				baixar(paraCsv(csv.colunas, csv.linhas), `${nome}.csv`, 'text/csv;charset=utf-8');
				return;
			}
			const p = PRESETS.find((x) => x.id === preset)!;
			const fontes = manifesto.recorte.fontes.map(nomeDaFonte).join(' e ');
			const svg = await montarSvg(figura!, { titulo, recorte: recorteEmPalavras(), fonte: `Fonte: ${fontes}`, n }, p);
			if (!svg) throw new Error('esta figura não tem um gráfico em SVG; exporte como CSV');
			if (formato === 'svg') baixar(svg, `${nome}.svg`, 'image/svg+xml');
			else baixar(await paraPng(svg, larguraPx(p)), `${nome}.png`);
			aberto = false;
		} catch (e) {
			erro = `Não foi possível exportar: ${(e as Error).message}.`;
		} finally {
			trabalhando = false;
		}
	}
</script>

<div class="exportar">
	<button type="button" class="abrir" aria-expanded={aberto} onclick={alternar} data-testid="abrir-exportar">
		Exportar
	</button>
	{#if aberto}
		<div class="painel" role="group" aria-label="Exportar a figura">
			<fieldset>
				<legend>Formato</legend>
				{#each [['svg', 'SVG'], ['png', 'PNG'], ['csv', 'CSV (dados)']] as [valor, rotulo] (valor)}
					<label>
						<input type="radio" bind:group={formato} value={valor} disabled={valor !== 'csv' && !temGrafico} />
						{rotulo}
					</label>
				{/each}
			</fieldset>
			{#if formato !== 'csv'}
				<label class="preset">
					Tamanho
					<select bind:value={preset} data-testid="preset-exportar">
						{#each PRESETS as p (p.id)}<option value={p.id}>{p.nome}</option>{/each}
					</select>
				</label>
			{/if}
			<button type="button" class="baixar" disabled={trabalhando} onclick={exportar} data-testid="baixar-figura">
				{trabalhando ? 'Preparando…' : 'Baixar'}
			</button>
			{#if erro}<p class="erro" role="alert">{erro}</p>{/if}
		</div>
	{/if}
</div>

<style>
	.exportar {
		position: relative;
		display: inline-block;
	}

	.abrir,
	.baixar {
		padding: 0;
		border: none;
		background: none;
		color: var(--acento);
		font: inherit;
		font-size: 0.85rem;
		text-decoration: underline;
		text-underline-offset: 0.2em;
		cursor: pointer;
	}

	.painel {
		position: absolute;
		z-index: 20;
		left: 0;
		top: 1.6rem;
		display: grid;
		gap: 0.6rem;
		min-width: 17rem;
		padding: 0.8rem 0.9rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio);
		background: var(--superficie-alta);
		box-shadow: var(--sombra);
		font-size: 0.85rem;
	}

	fieldset {
		display: flex;
		gap: 0.8rem;
		margin: 0;
		padding: 0;
		border: 0;
	}

	legend {
		margin-bottom: 0.3rem;
		color: var(--texto-suave);
	}

	.preset {
		display: grid;
		gap: 0.25rem;
		color: var(--texto-suave);
	}

	select {
		padding: 0.3rem 0.4rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
	}

	.baixar {
		justify-self: start;
		padding: 0.3rem 0.8rem;
		border: 1px solid var(--acento);
		border-radius: var(--raio-pequeno);
		background: var(--acento);
		color: var(--sobre-acento);
		text-decoration: none;
	}

	.erro {
		margin: 0;
		color: var(--acento);
	}
</style>
