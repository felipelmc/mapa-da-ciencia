<!-- Tela enquanto o manifesto carrega (normalmente, uma fração de segundo). -->
<div class="abrindo" role="status">
	<svg viewBox="0 0 24 24" aria-hidden="true">
		<path d="M12 3.2 13.8 10.2 20.8 12 13.8 13.8 12 20.8 10.2 13.8 3.2 12 10.2 10.2Z" />
	</svg>
	<p>Abrindo o observatório…</p>
</div>

<style>
	.abrindo {
		min-height: 100dvh;
		display: grid;
		place-content: center;
		justify-items: center;
		gap: 1rem;
		color: var(--texto-suave);
		font-family: var(--fonte-mono);
		font-size: 0.8rem;
		letter-spacing: 0.08em;
	}

	svg {
		width: 2rem;
		height: 2rem;
		fill: var(--acento);
	}

	@media (prefers-reduced-motion: no-preference) {
		svg {
			animation: cintilar 1.6s ease-in-out infinite;
		}
	}

	@keyframes cintilar {
		50% {
			opacity: 0.35;
			transform: scale(0.85);
		}
	}
</style>
