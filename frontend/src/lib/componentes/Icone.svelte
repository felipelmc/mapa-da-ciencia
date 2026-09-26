<script lang="ts">
	import { ICONES, type NomeIcone } from './icones';

	interface Props {
		nome: NomeIcone;
		tamanho?: number;
		/** Texto para leitores de tela. Sem ele, o ícone é decorativo (aria-hidden). */
		rotulo?: string;
	}

	let { nome, tamanho = 20, rotulo }: Props = $props();
</script>

<svg
	class="icone"
	width={tamanho}
	height={tamanho}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.5"
	stroke-linecap="round"
	stroke-linejoin="round"
	role={rotulo ? 'img' : undefined}
	aria-label={rotulo}
	aria-hidden={rotulo ? undefined : 'true'}
	focusable="false"
>
	{#each ICONES[nome] as d (d)}
		<path {d} />
	{/each}
</svg>

<style>
	.icone {
		flex: none;
		display: block;
	}
</style>
