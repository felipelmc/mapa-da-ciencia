<script lang="ts">
	/**
	 * Validação › Codificar: a codificação cega da amostra, só no painel local (precisa da API para gravar). O nome
	 * de quem codifica fica neste navegador; trocar de nome abre a fila de outra pessoa.
	 */
	import { usarProjeto } from '$lib/dados/contexto';
	import { rota } from '$lib/estado/url';
	import { ErroDaApi, lerFila, NOME_VALIDO, type Fila } from '$lib/validacao/api';
	import Codificar from '$lib/validacao/Codificar.svelte';

	const { manifesto } = usarProjeto();
	const CHAVE = 'mapa.codificador';
	const lembrado = (() => {
		try {
			return localStorage.getItem(CHAVE) ?? '';
		} catch {
			return '';
		}
	})();

	let nome = $state(lembrado);
	let fila = $state<Fila | null>(null);
	let erro = $state<string | null>(null);
	let carregando = $state(false);
	const valido = $derived(NOME_VALIDO.test(nome));

	async function comecar(evento?: SubmitEvent) {
		evento?.preventDefault();
		if (!valido) return;
		carregando = true;
		erro = null;
		try {
			fila = await lerFila(nome);
			try {
				localStorage.setItem(CHAVE, nome);
			} catch {
				/* sem localStorage: só não lembra o nome */
			}
		} catch (e) {
			erro =
				e instanceof ErroDaApi && e.status === 404
					? `${e.message} Depois, recarregue esta página.`
					: `Não foi possível abrir a fila: ${(e as Error).message}`;
		} finally {
			carregando = false;
		}
	}

	function trocar() {
		fila = null;
		nome = '';
		try {
			localStorage.removeItem(CHAVE);
		} catch {
			/* sem localStorage */
		}
	}

	if (manifesto.api && lembrado && NOME_VALIDO.test(lembrado)) void comecar();
</script>

<svelte:head>
	<title>Codificar · mapa da ciência</title>
</svelte:head>

{#if !manifesto.api}
	<div class="entrada">
		<h1>Codificar a amostra</h1>
		<p>
			A codificação grava as respostas no projeto, por isso só funciona no painel local{#if manifesto.publicacao}.{:else}: rode
				<code>mapa painel</code> na pasta do projeto.{/if} Neste site, veja a concordância na
			<a href={rota('/validacao')}>Validação</a>.
		</p>
	</div>
{:else if fila}
	{#key fila.codificador}
		<Codificar {fila} aoTrocar={trocar} />
	{/key}
{:else}
	<form class="entrada" onsubmit={comecar}>
		<h1>Codificar a amostra</h1>
		<p>
			Você vai ler os resumos da amostra de validação, um por vez, e responder às perguntas do codebook. A
			codificação é <strong>cega</strong>: a ficha não mostra o que o modelo respondeu. A ordem da fila é só sua, e
			tudo é gravado sozinho.
		</p>
		<label for="nome-codificador">Seu nome (sem acentos nem espaços, como <code>maria</code>)</label>
		<div class="linha">
			<input id="nome-codificador" bind:value={nome} autocomplete="off" spellcheck="false" maxlength="40" />
			<button type="submit" disabled={!valido || carregando}>{carregando ? 'Abrindo…' : 'Começar'}</button>
		</div>
		{#if nome && !valido}<p class="erro">Use letras sem acento, números, <code>-</code>, <code>_</code> ou <code>.</code>.</p>{/if}
		{#if erro}<p class="erro" role="alert">{erro}</p>{/if}
	</form>
{/if}

<style>
	.entrada {
		display: grid;
		gap: 0.8rem;
		max-width: 40rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(1.8rem, 3.5vw, 2.6rem);
		font-weight: 380;
	}

	p {
		margin: 0;
		color: var(--texto-suave);
	}

	.linha {
		display: flex;
		gap: 0.5rem;
	}

	input {
		flex: 1;
		padding: 0.45rem 0.6rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--superficie);
		color: var(--texto);
		font: inherit;
	}

	button {
		padding: 0.45rem 1rem;
		border: 1px solid var(--acento);
		border-radius: var(--raio-pequeno);
		background: var(--acento);
		color: var(--sobre-acento);
		font: inherit;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.erro {
		color: var(--acento);
	}
</style>
