<script lang="ts">
	// Fontes locais (sem requisição a serviços externos): Fraunces com eixo óptico para
	// títulos e números grandes, Instrument Sans para a interface, JetBrains Mono para números.
	import '@fontsource-variable/fraunces/opsz.css';
	import '@fontsource-variable/fraunces/opsz-italic.css';
	import '@fontsource-variable/instrument-sans';
	import '@fontsource-variable/jetbrains-mono';
	import '$lib/estilos/tokens.css';
	import '$lib/estilos/base.css';

	import { onMount, type Snippet } from 'svelte';
	import Abrindo from '$lib/componentes/Abrindo.svelte';
	import Casca from '$lib/componentes/Casca.svelte';
	import FalhaAoAbrir from '$lib/componentes/FalhaAoAbrir.svelte';
	import { abrirProjeto } from '$lib/dados/contexto';
	import { tema } from '$lib/estado/tema.svelte';

	let { children }: { children: Snippet } = $props();

	// O manifesto (e as revistas, para a barra superior) vêm antes de qualquer página.
	// Os dados ficam fora das funções `load` do SvelteKit de propósito: a camada de dados
	// não depende do framework e é testada sozinha (src/lib/dados/*.test.ts).
	const carga = abrirProjeto();

	onMount(() => tema.iniciar());
</script>

{#await carga}
	<Abrindo />
{:then projeto}
	<Casca {projeto}>
		{@render children()}
	</Casca>
{:catch erro}
	<FalhaAoAbrir {erro} />
{/await}
