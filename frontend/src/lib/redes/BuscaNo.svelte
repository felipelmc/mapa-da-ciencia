<script lang="ts" module>
	export interface ItemBusca {
		id: string;
		nome: string;
		/** Uma linha a mais na lista (documentos, lugar). */
		detalhe: string;
		/** O texto em que se busca, já sem acentos e em minúsculas (`dobrar`). */
		chave: string;
	}
</script>

<script lang="ts">
	/**
	 * Busca de uma pessoa ou instituição pelo teclado: um combobox (padrão da ARIA 1.2), com a lista embaixo. As setas
	 * andam na lista, Enter abre o cartão, Esc limpa. Sem diferença de acentos nem de maiúsculas; os itens chegam em
	 * ordem de relevância (mais documentos primeiro) e a lista mostra os primeiros.
	 */
	import { dobrar } from '$lib/dados/busca';

	let {
		itens,
		rotulo,
		dica,
		aoEscolher
	}: { itens: ItemBusca[]; rotulo: string; dica: string; aoEscolher: (id: string) => void } = $props();

	const MAXIMO = 8;
	const uid = $props.id();
	let texto = $state('');
	let aberta = $state(false);
	let ativo = $state(0);

	const achados = $derived.by(() => {
		const termos = dobrar(texto).split(/\s+/).filter(Boolean);
		if (!termos.length) return [];
		const saida: ItemBusca[] = [];
		for (const item of itens) {
			if (termos.every((t) => item.chave.includes(t))) saida.push(item);
			if (saida.length === MAXIMO) break;
		}
		return saida;
	});
	const expandida = $derived(aberta && achados.length > 0);
	const idOpcao = (k: number) => `${uid}-opcao-${k}`;

	function escolher(item: ItemBusca) {
		aoEscolher(item.id);
		texto = '';
		aberta = false;
	}

	function teclar(e: KeyboardEvent) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			e.preventDefault();
			aberta = true;
			if (!achados.length) return;
			ativo = (ativo + (e.key === 'ArrowDown' ? 1 : -1) + achados.length) % achados.length;
		} else if (e.key === 'Enter') {
			if (!achados.length) return;
			e.preventDefault();
			escolher(achados[Math.min(ativo, achados.length - 1)]);
		} else if (e.key === 'Escape') {
			if (aberta && texto) e.preventDefault();
			texto = '';
			aberta = false;
		}
	}
</script>

<div class="busca">
	<label for="{uid}-campo">{rotulo}</label>
	<input
		id="{uid}-campo"
		type="search"
		role="combobox"
		data-busca-no
		autocomplete="off"
		spellcheck="false"
		placeholder={dica}
		aria-autocomplete="list"
		aria-expanded={expandida}
		aria-controls="{uid}-lista"
		aria-activedescendant={expandida ? idOpcao(Math.min(ativo, achados.length - 1)) : undefined}
		data-testid="busca-no"
		bind:value={texto}
		oninput={() => ((aberta = true), (ativo = 0))}
		onkeydown={teclar}
		onblur={() => (aberta = false)}
	/>
	<ul id="{uid}-lista" role="listbox" aria-label={rotulo} class:aberta={expandida}>
		{#if expandida}
			{#each achados as item, k (item.id)}
				<!-- o mousedown escolhe antes do blur do campo fechar a lista -->
				<li
					id={idOpcao(k)}
					role="option"
					aria-selected={k === ativo}
					data-testid="opcao-no"
					onmousedown={(e) => (e.preventDefault(), escolher(item))}
					onmousemove={() => (ativo = k)}
				>
					<span class="nome">{item.nome}</span>
					<span class="detalhe">{item.detalhe}</span>
				</li>
			{/each}
		{/if}
	</ul>
	{#if aberta && texto.trim() && !achados.length}
		<p class="nada" role="status">Nada encontrado.</p>
	{/if}
</div>

<style>
	.busca {
		position: relative;
		display: grid;
		gap: 0.25rem;
		width: min(100%, 24rem);
	}

	label {
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	input {
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--superficie);
		color: var(--texto);
		font: inherit;
		font-size: 0.9rem;
	}

	ul {
		display: none;
		position: absolute;
		z-index: 30;
		top: 100%;
		left: 0;
		right: 0;
		margin: 0.2rem 0 0;
		padding: 0.25rem;
		list-style: none;
		background: var(--superficie-alta);
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio);
		box-shadow: var(--sombra);
	}

	ul.aberta {
		display: block;
	}

	li {
		display: grid;
		padding: 0.3rem 0.5rem;
		border-radius: var(--raio-pequeno);
		cursor: pointer;
	}

	li[aria-selected='true'] {
		background: var(--acento-suave);
		outline: 1px solid var(--acento);
	}

	.nome {
		font-size: 0.9rem;
	}

	.detalhe,
	.nada {
		font-size: 0.75rem;
		color: var(--texto-suave);
	}

	.nada {
		margin: 0;
	}
</style>
