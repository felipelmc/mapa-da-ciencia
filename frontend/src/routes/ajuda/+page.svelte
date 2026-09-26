<script lang="ts">
	import Icone from '$lib/componentes/Icone.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { rota } from '$lib/estado/url';
	import { NOMES_TEMA } from '$lib/estado/tema.svelte';
	import { secoesDoTrilho } from '$lib/secoes';

	const { manifesto } = usarProjeto();
	const secoes = secoesDoTrilho(manifesto).filter((s) => s.id !== 'inicio');
</script>

<svelte:head>
	<title>Ajuda · mapa da ciência</title>
</svelte:head>

<div class="pagina surgir">
	<header class="cabecalho">
		<p class="rotulo-miudo sobre"><Icone nome="ajuda" tamanho={16} /> <span>Ajuda</span></p>
		<h1>Como ler este observatório</h1>
		<p class="resumo">
			O mapa da ciência mostra um corpus de artigos científicos: sobre o que falam, como foram
			classificados e de onde vêm. Tudo o que aparece aqui sai dos arquivos gerados pelo pipeline, no
			seu computador.
		</p>
	</header>

	<section aria-labelledby="ajuda-secoes">
		<h2 id="ajuda-secoes">As seções</h2>
		<dl class="secoes">
			{#each secoes as s (s.id)}
				<div>
					<dt>
						<Icone nome={s.icone} tamanho={18} />
						{#if s.selo}
							<span>{s.rotulo}</span>
						{:else}
							<a href={rota(s.caminho)}>{s.rotulo}</a>
						{/if}
						<span class="chegada">chega {s.chegada}</span>
					</dt>
					<dd>{s.resumo}</dd>
				</div>
			{/each}
		</dl>
	</section>

	<div class="colunas">
		<section aria-labelledby="ajuda-links">
			<h2 id="ajuda-links">Links que guardam a vista</h2>
			<p>
				O endereço guarda a seção e os filtros depois do <code>#</code>, como em
				<code>#/mapa?anos=2012-2020</code>. Copie o endereço para compartilhar exatamente o que você está
				vendo.
			</p>
		</section>

		<section aria-labelledby="ajuda-temas">
			<h2 id="ajuda-temas">Dois temas</h2>
			<p>
				<strong>{NOMES_TEMA.observatorio}</strong> é o escuro, como um céu noturno.
				<strong>{NOMES_TEMA.prancha}</strong> é o claro, como o papel de um atlas. O tema segue a configuração
				do sistema até você escolher um no botão da barra superior; a escolha fica guardada neste
				navegador.
			</p>
		</section>

		<section aria-labelledby="ajuda-modo">
			<h2 id="ajuda-modo">Site ou painel</h2>
			<p>
				{#if manifesto.api}
					Você está no <strong>painel local</strong> (<code>mapa painel</code>), que roda só nesta máquina e
					poderá editar o projeto.
				{:else}
					Você está no <strong>site estático</strong>: os dados são somente leitura. Para editar um projeto,
					use o painel local, com <code>mapa painel</code>.
				{/if}
			</p>
		</section>

		<section aria-labelledby="ajuda-teclado">
			<h2 id="ajuda-teclado">Pelo teclado</h2>
			<p>
				<kbd>Tab</kbd> percorre os controles, e o primeiro deles é “Pular para o conteúdo”. O foco fica sempre
				visível, e as animações somem se o sistema pedir menos movimento.
			</p>
		</section>
	</div>
</div>

<style>
	.pagina {
		display: grid;
		gap: 2.5rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.75rem;
		max-width: 50rem;
	}

	.sobre {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--acento);
	}

	h1 {
		font-size: clamp(2.2rem, 4.5vw, 3.3rem);
		font-weight: 380;
	}

	h2 {
		font-size: 1.35rem;
		margin-bottom: 0.75rem;
	}

	.resumo {
		font-size: 1.1rem;
		color: var(--texto-suave);
	}

	.secoes {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
		gap: 0;
		margin: 0;
		border-top: 1px solid var(--linha);
	}

	.secoes div {
		display: grid;
		gap: 0.35rem;
		padding: 1rem 1.25rem 1.1rem 0;
		border-bottom: 1px solid var(--linha);
	}

	.secoes dt {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		font-weight: 600;
	}

	.secoes dt :global(.icone) {
		color: var(--acento);
	}

	.secoes a {
		text-decoration-color: var(--linha-forte);
		text-underline-offset: 3px;
	}

	.chegada {
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		font-weight: 400;
		color: var(--texto-suave);
	}

	.secoes dd {
		margin: 0;
		font-size: 0.9rem;
		color: var(--texto-suave);
	}

	.colunas {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: 2rem 2.5rem;
	}

	.colunas p {
		color: var(--texto-suave);
	}

	.colunas strong {
		color: var(--texto);
	}

	kbd {
		font-family: var(--fonte-mono);
		font-size: 0.8em;
		padding: 0.05em 0.4em;
		border: 1px solid var(--linha-forte);
		border-bottom-width: 2px;
		border-radius: var(--raio-pequeno);
		color: var(--texto);
	}
</style>
