<script lang="ts">
	/**
	 * Linha do tempo do mapa: o intervalo de anos (dois controles) e um play que passa ano a ano. Cada passo
	 * troca a entrada do histórico em vez de criar outra (voltar no navegador não refaz o play). Com
	 * `prefers-reduced-motion`, o play anda mais devagar.
	 */
	import { onDestroy } from 'svelte';

	let {
		limites,
		anos,
		aoMudar
	}: {
		limites: [number, number];
		anos: [number, number] | null;
		aoMudar: (anos: [number, number] | null, passo?: boolean) => void;
	} = $props();

	const de = $derived(anos?.[0] ?? limites[0]);
	const ate = $derived(anos?.[1] ?? limites[1]);
	let tocando = $state(false);
	let relogio: ReturnType<typeof setInterval> | undefined;

	function mudar(novoDe: number, novoAte: number) {
		const [a, b] = novoDe <= novoAte ? [novoDe, novoAte] : [novoAte, novoDe];
		aoMudar(a === limites[0] && b === limites[1] ? null : [a, b]);
	}

	function parar() {
		clearInterval(relogio);
		tocando = false;
	}

	function tocar() {
		if (tocando) return parar();
		tocando = true;
		let ano = anos && anos[0] === anos[1] && anos[0] < limites[1] ? anos[0] + 1 : limites[0];
		aoMudar([ano, ano], true);
		const lento = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
		relogio = setInterval(
			() => {
				ano += 1;
				if (ano > limites[1]) return parar();
				aoMudar([ano, ano], true);
			},
			lento ? 1600 : 800
		);
	}

	onDestroy(parar);
</script>

<div class="linha" data-testid="linha-do-tempo">
	<button type="button" class="play" onclick={tocar} aria-pressed={tocando} data-testid="play">
		{tocando ? 'Pausar' : 'Play'}
	</button>
	<label>
		<span class="visualmente-oculto">Primeiro ano</span>
		<input type="range" min={limites[0]} max={limites[1]} value={de} oninput={(e) => mudar(+e.currentTarget.value, ate)} />
	</label>
	<span class="anos numero" aria-live="polite">{de === ate ? de : `${de}–${ate}`}</span>
	<label>
		<span class="visualmente-oculto">Último ano</span>
		<input type="range" min={limites[0]} max={limites[1]} value={ate} oninput={(e) => mudar(de, +e.currentTarget.value)} />
	</label>
</div>

<style>
	.linha {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.5rem 0.75rem;
		background: color-mix(in oklab, var(--superficie) 88%, transparent);
		border: 1px solid var(--linha);
		border-radius: 999px;
		backdrop-filter: blur(6px);
	}

	label {
		display: flex;
	}

	input[type='range'] {
		width: 8rem;
		accent-color: var(--acento);
	}

	.anos {
		min-width: 6.5rem;
		text-align: center;
		font-size: 0.9rem;
	}

	.play {
		padding: 0.2rem 0.7rem;
		font: inherit;
		font-size: 0.85rem;
		color: var(--fundo);
		background: var(--acento);
		border: 0;
		border-radius: 999px;
		cursor: pointer;
	}
</style>
