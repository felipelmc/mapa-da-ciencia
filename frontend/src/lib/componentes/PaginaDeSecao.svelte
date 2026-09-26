<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Contagens } from '$lib/contrato/tipos';
	import { usarProjeto } from '$lib/dados/contexto';
	import type { NomeArquivo } from '$lib/dados';
	import { contar } from '$lib/formato';
	import type { Secao } from '$lib/secoes';
	import EstadoVazio from './EstadoVazio.svelte';
	import Icone from './Icone.svelte';

	/**
	 * Página de uma seção sem conteúdo para mostrar: cabeçalho com o que ela mostra e um estado vazio com os
	 * arquivos de dados que o projeto já tem. Sem `vazio`, diz em que marco a vista chega; com `vazio`, é a vista
	 * pronta num projeto que ainda não rodou a etapa (o texto diz o que rodar).
	 */
	let {
		secao,
		vazio,
		children
	}: { secao: Secao; vazio?: { titulo: string; sobretitulo: string }; children?: Snippet } = $props();

	const { manifesto } = usarProjeto();

	// Contagem do manifesto que acompanha cada arquivo, quando houver.
	const CONTAGEM: Partial<Record<NomeArquivo, [keyof Contagens, string, string?]>> = {
		documentos: ['documentos', 'documento'],
		topicos: ['topicos', 'tópico'],
		afiliacoes: ['com_afiliacao', 'com afiliação', 'com afiliação'],
		classificacoes: ['classificados', 'classificado'],
		validacao: ['validados', 'validado']
	};

	const arquivos = $derived(
		secao.arquivos.map((nome) => {
			const presente = manifesto.arquivos.includes(nome);
			const c = CONTAGEM[nome];
			const n = c ? (manifesto.contagens[c[0]] ?? 0) : 0;
			const detalhe = presente && c && n > 0 ? contar(n, c[1], c[2]) : null;
			return { nome, presente, detalhe };
		})
	);
</script>

<svelte:head>
	<title>{secao.rotulo} · mapa da ciência</title>
</svelte:head>

<div class="pagina surgir">
	<header class="cabecalho">
		<p class="rotulo-miudo sobre">
			<Icone nome={secao.icone} tamanho={16} />
			<span>Seção</span>
		</p>
		<h1>{secao.rotulo}</h1>
		<p class="resumo">{secao.resumo}</p>
	</header>

	<EstadoVazio
		titulo={vazio?.titulo ?? `Chega ${secao.chegada}`}
		sobretitulo={vazio?.sobretitulo ?? 'Vista em construção'}
	>
		{#if !vazio}
			<p>
				A casca do app já está no ar. Esta vista entra {secao.chegada}, e o endereço
				<code>#{secao.caminho}</code> continua o mesmo.
			</p>
		{/if}
		{@render children?.()}
		{#if arquivos.length}
			<div class="dados">
				<p class="rotulo-miudo">Dados deste projeto</p>
				<ul>
					{#each arquivos as a (a.nome)}
						<li class:presente={a.presente}>
							<span class="marcador" aria-hidden="true"></span>
							<code>{a.nome}.json</code>
							<span class="estado">
								{#if a.presente}
									{a.detalhe ?? 'disponível'}
								{:else}
									ainda não gerado
								{/if}
							</span>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</EstadoVazio>
</div>

<style>
	.pagina {
		display: grid;
		gap: 2rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.75rem;
		max-width: 52rem;
	}

	.sobre {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--acento);
	}

	h1 {
		font-size: clamp(2.4rem, 5vw, 3.6rem);
		font-weight: 380;
	}

	.resumo {
		font-size: 1.1rem;
		color: var(--texto-suave);
		max-width: 46rem;
	}

	.dados {
		display: grid;
		gap: 0.5rem;
		margin-top: 0.5rem;
		padding-top: 1rem;
		border-top: 1px dashed var(--linha);
	}

	.dados ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.35rem;
	}

	.dados li {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.6rem;
		font-size: 0.9rem;
	}

	.marcador {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 50%;
		border: 1px solid var(--texto-suave);
	}

	.presente .marcador {
		background: var(--acento);
		border-color: var(--acento);
	}

	.estado {
		font-size: 0.85rem;
	}

	.presente .estado {
		color: var(--texto);
	}
</style>
