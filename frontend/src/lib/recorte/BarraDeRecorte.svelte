<script lang="ts">
	/**
	 * A barra do recorte, comum às vistas de análise (Mapa, Tópicos, Geografia): a linha do tempo com o play,
	 * as revistas, os filtros ativos como chips removíveis, o contador de documentos e "Limpar recorte". Tudo lê e
	 * escreve a URL, então a barra e as vistas estão sempre de acordo, e o trilho leva o recorte adiante.
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { Tween, prefersReducedMotion } from 'svelte/motion';
	import type { Revistas } from '$lib/contrato/tipos';
	import { usarProjeto } from '$lib/dados/contexto';
	import { abrirCubo, aoReabrir, lacoVale, type Aberto } from '$lib/dados/corpus';
	import { D } from '$lib/dados/cubo';
	import { filtrosDaPagina, mudarFiltros } from '$lib/estado/filtros';
	import { lerHash, limparRecorte, temRecorte } from '$lib/estado/url';
	import { formatarInteiro } from '$lib/formato';
	import LinhaDoTempo from './LinhaDoTempo.svelte';

	const { fonte, manifesto } = usarProjeto();
	const filtros = $derived(filtrosDaPagina());
	const caminho = $derived(lerHash(page.url.hash).caminho);

	let aberto = $state<Aberto | null>(null);
	let revistas = $state<Revistas | null>(null);
	// se o corpus não abrir (rede), a vista mostra o erro e o "Tentar de novo"; a barra reabre junto com ela
	const abrir = () =>
		abrirCubo(fonte)
			.then((a) => (aberto = a))
			.catch(() => (aberto = null));
	abrir();
	onMount(() => aoReabrir(abrir));
	fonte
		.revistas()
		.then((r) => (revistas = r))
		.catch(() => (revistas = null)); // sem os títulos, a lista mostra os ids

	const falhas = $derived(aberto ? aberto.cubo.falhas(filtros) : null);
	const n = $derived(aberto && falhas ? aberto.cubo.contar(falhas) : 0);
	// o chip do laço conta o próprio laço (ignorando as outras dimensões), e não repete o contador do recorte
	const noLaco = $derived(aberto && falhas && filtros.laco ? aberto.cubo.contar(falhas, ~D.LACO & 0xff) : 0);
	const total = $derived(aberto?.tabela.n ?? 0);

	// contador animado; o anúncio para leitores de tela vem depois de uma pausa, com o valor final
	const contador = new Tween(0, { duration: 350 });
	let anuncio = $state('');
	let pausa: ReturnType<typeof setTimeout> | undefined;
	$effect(() => {
		const valor = n;
		contador.set(valor, { duration: prefersReducedMotion.current ? 0 : 350 });
		clearTimeout(pausa);
		pausa = setTimeout(() => (anuncio = `${formatarInteiro(valor)} de ${formatarInteiro(total)} documentos`), 400);
	});

	const mudar = (parcial: Parameters<typeof mudarFiltros>[0], substituir = false) =>
		mudarFiltros(parcial, { substituir, em: caminho });

	// ---- chips
	interface Chip {
		id: string;
		texto: string;
		tirar: () => void;
	}
	const chips = $derived.by((): Chip[] => {
		if (!aberto) return [];
		const saida: Chip[] = [];
		const { topicos, afiliacoes } = aberto;
		const rotulo = new Map(topicos.topicos.map((t) => [t.id, t.rotulo]));
		let resto = [...filtros.topicos];
		for (const m of topicos.macrotemas) {
			if (m.topicos.length && m.topicos.every((t) => resto.includes(t))) {
				resto = resto.filter((t) => !m.topicos.includes(t));
				saida.push({ id: `m${m.id}`, texto: m.rotulo, tirar: () => mudar({ topicos: filtros.topicos.filter((t) => !m.topicos.includes(t)) }) });
			}
		}
		for (const t of resto) {
			saida.push({
				id: `t${t}`,
				texto: t === -1 ? 'Sem tópico' : (rotulo.get(t) ?? `Tópico ${t}`),
				tirar: () => mudar({ topicos: filtros.topicos.filter((x) => x !== t) })
			});
		}
		if (filtros.busca) saida.push({ id: 'busca', texto: `Busca: “${filtros.busca}”`, tirar: () => mudar({ busca: '' }) });
		for (const uf of filtros.uf) saida.push({ id: `uf${uf}`, texto: uf, tirar: () => mudar({ uf: filtros.uf.filter((x) => x !== uf) }) });
		const nomePais = typeof Intl.DisplayNames === 'function' ? new Intl.DisplayNames(['pt-BR'], { type: 'region' }) : null;
		for (const p of filtros.pais) {
			saida.push({ id: `pais${p}`, texto: nomePais?.of(p) ?? p, tirar: () => mudar({ pais: filtros.pais.filter((x) => x !== p) }) });
		}
		for (const id of filtros.inst) {
			const i = afiliacoes?.indiceInst.get(id);
			const inst = i !== undefined ? afiliacoes!.instituicoes[i] : null;
			saida.push({ id: `inst${id}`, texto: inst ? (inst.sigla ?? inst.nome) : id, tirar: () => mudar({ inst: filtros.inst.filter((x) => x !== id) }) });
		}
		return saida;
	});

	const lugaresSemDados = $derived(!!aberto && !aberto.afiliacoes && (filtros.uf.length + filtros.pais.length + filtros.inst.length > 0));
	const lacoAntigo = $derived(!!aberto && !!filtros.laco && !lacoVale(filtros.laco.versao, aberto.tabela, manifesto));
	const nFiltros = $derived(chips.length + (filtros.laco ? 1 : 0) + (filtros.anos ? 1 : 0) + filtros.revistas.length);
	let expandida = $state(false);

	// o menu das revistas fecha com Esc e com um clique fora; o clique que fecha não chega ao que está embaixo
	// (no mapa, ele abriria um documento ou filtraria um macrotema sem a pessoa perceber)
	// `revistasAberto` só acompanha o <details> (já no clique do summary, antes de o navegador abrir o menu, e pelo
	// evento toggle, que chega um instante depois); quem fecha o menu escreve direto nele
	let revistasAberto = $state(false);
	let menuRevistas = $state<HTMLDetailsElement>();
	function fecharRevistas() {
		if (menuRevistas) menuRevistas.open = false;
		revistasAberto = false;
	}
	// a lista nasce alinhada à esquerda do botão; perto da borda direita da tela, ela recua para caber
	let listaRevistas = $state<HTMLUListElement>();
	let recuo = $state(0);
	function aoAlternarRevistas() {
		revistasAberto = !!menuRevistas?.open;
		if (!revistasAberto || !menuRevistas || !listaRevistas) return;
		const inicio = menuRevistas.getBoundingClientRect().left;
		const limite = document.documentElement.clientWidth - 8;
		recuo = Math.max(Math.min(0, limite - (inicio + listaRevistas.offsetWidth)), 8 - inicio);
	}
	function teclaRevistas(e: KeyboardEvent) {
		if (e.key !== 'Escape' || !menuRevistas?.open) return;
		fecharRevistas();
		menuRevistas.querySelector('summary')?.focus();
	}

	function alternarRevista(id: string) {
		mudar({ revistas: filtros.revistas.includes(id) ? filtros.revistas.filter((r) => r !== id) : [...filtros.revistas, id] });
	}
</script>

<svelte:window onkeydown={teclaRevistas} />

{#if aberto}
	{#if revistasAberto}
		<!-- quem usa o teclado fecha com Esc; o clique fora só precisa fechar -->
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="fora-do-menu" data-testid="fora-do-menu" onclick={fecharRevistas}></div>
	{/if}
	<section class="recorte" class:expandida aria-label="Recorte" data-testid="barra-recorte">
		<button
			type="button"
			class="resumo"
			aria-expanded={expandida}
			onclick={() => {
				expandida = !expandida;
				if (!expandida) fecharRevistas(); // recolhida, a barra esconde o menu: a camada que o fecharia sai junto
			}}
		>
			Recorte{nFiltros ? ` (${nFiltros})` : ''} · {formatarInteiro(n)} docs
		</button>
		<div class="corpo">
			<LinhaDoTempo
				limites={aberto.tabela.anos}
				anos={filtros.anos}
				aoMudar={(anos, substituir) => mudar({ anos }, !!substituir)}
			/>
			<details class="revistas" bind:this={menuRevistas} ontoggle={aoAlternarRevistas}>
				<summary onclick={() => (revistasAberto = !menuRevistas?.open)}>
					Revistas{filtros.revistas.length ? ` (${filtros.revistas.length})` : ''}
				</summary>
				<ul bind:this={listaRevistas} style:left="{recuo}px">
					{#each aberto.tabela.revistas as id (id)}
						<li>
							<label>
								<input type="checkbox" checked={filtros.revistas.includes(id)} onchange={() => alternarRevista(id)} />
								{revistas?.revistas.find((r) => r.id === id)?.titulo ?? id}
							</label>
						</li>
					{/each}
				</ul>
			</details>
			<ul class="chips" aria-label="Filtros ativos">
				{#if filtros.laco}
					<li class="chip laco" data-testid="chip-laco">
						Laço: {formatarInteiro(noLaco)} documentos
						<button type="button" aria-label="Tirar o laço" onclick={() => mudar({ laco: null })}>×</button>
					</li>
				{/if}
				{#each chips as c (c.id)}
					<li class="chip">
						{c.texto}
						<button type="button" aria-label="Tirar {c.texto}" onclick={c.tirar}>×</button>
					</li>
				{/each}
			</ul>
			{#if lacoAntigo}
				<p class="aviso" data-testid="aviso-laco">Este laço foi desenhado numa versão anterior do mapa: a seleção pode não corresponder.</p>
			{/if}
			{#if lugaresSemDados}
				<p class="aviso">Este projeto ainda não tem geografia: os filtros de lugar ficam sem efeito.</p>
			{/if}
			<div class="fim">
				{#if temRecorte(filtros)}
					<button type="button" class="botao limpar" onclick={() => mudar(limparRecorte())}>Limpar recorte</button>
				{/if}
				<p class="contador numero" data-testid="contador-recorte">
					{formatarInteiro(Math.round(contador.current))}
					<span>de {formatarInteiro(total)} documentos</span>
				</p>
			</div>
			<p class="visualmente-oculto" aria-live="polite">{anuncio}</p>
		</div>
	</section>
{/if}

<style>
	.recorte {
		position: sticky;
		top: 0;
		z-index: 20;
		grid-area: recorte;
		border-bottom: 1px solid var(--linha);
		background: color-mix(in oklab, var(--fundo) 92%, transparent);
		backdrop-filter: blur(6px);
	}

	.corpo {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.9rem;
		padding: 0.45rem clamp(1rem, 3vw, 2rem);
	}

	.resumo {
		display: none;
	}

	.revistas {
		position: relative;
	}

	/* por cima de tudo menos da barra do recorte (z-index 20), enquanto o menu das revistas está aberto */
	.fora-do-menu {
		position: fixed;
		inset: 0;
		z-index: 19;
	}

	.revistas summary {
		cursor: pointer;
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--linha-forte);
		border-radius: 999px;
		font-size: 0.85rem;
		list-style: none;
	}

	.revistas ul {
		position: absolute;
		top: calc(100% + 0.35rem);
		left: 0;
		z-index: 30;
		min-width: min(18rem, calc(100vw - 16px));
		max-width: calc(100vw - 16px);
		max-height: 60vh;
		overflow: auto;
		margin: 0;
		padding: 0.5rem 0.75rem;
		list-style: none;
		background: var(--superficie);
		border: 1px solid var(--linha);
		border-radius: 0.6rem;
		box-shadow: 0 10px 30px rgb(0 0 0 / 0.3);
	}

	.revistas li label {
		display: flex;
		gap: 0.5rem;
		padding: 0.2rem 0;
		font-size: 0.85rem;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		max-width: 22rem;
		padding: 0.2rem 0.3rem 0.2rem 0.7rem;
		border: 1px solid var(--linha-forte);
		border-radius: 999px;
		font-size: 0.82rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.chip.laco {
		border-color: var(--acento);
	}

	.chip button {
		border: none;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		cursor: pointer;
		padding: 0 0.3rem;
	}

	.fim {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		margin-left: auto;
	}

	.contador {
		margin: 0;
		font-size: 1rem;
		white-space: nowrap;
	}

	.contador span {
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.aviso {
		margin: 0;
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.limpar {
		font-size: 0.82rem;
	}

	@media (max-width: 820px) {
		.resumo {
			display: block;
			width: 100%;
			padding: 0.5rem 1rem;
			border: none;
			background: none;
			color: var(--texto);
			font: inherit;
			text-align: left;
		}

		.corpo {
			display: none;
		}

		.expandida .corpo {
			display: flex;
		}
	}
</style>
