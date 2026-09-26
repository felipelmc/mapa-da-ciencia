import { defineConfig, devices } from '@playwright/test';

// Testes de ponta a ponta sobre o BUILD (não o `vite dev`): tests/e2e/preparar.ts copia
// build/ e os dados de exemplo para uma pasta temporária e sobe servidores estáticos sem
// regra de reescrita, na raiz e num subcaminho (ADR 0002). Rode `npm run build` antes.
export default defineConfig({
	testDir: 'tests/e2e',
	outputDir: 'test-results/playwright',
	globalSetup: './tests/e2e/preparar.ts',
	// Um worker só: a suíte é curta e a máquina de desenvolvimento roda outros jobs pesados.
	workers: 1,
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: 0,
	reporter: [['list']],
	use: {
		trace: 'retain-on-failure'
	},
	projects: [
		{
			name: 'chromium',
			use: {
				...devices['Desktop Chrome'],
				viewport: { width: 1440, height: 900 },
				launchOptions: {
					// ADR 0002: no CI (Linux sem GPU), WebGL por software com estas flags; no
					// macOS basta o headless padrão. Aqui elas deixaram a suíte da casca de 5 a 6×
					// mais lenta (28–33 s contra 5–6 s), sem ganho enquanto não há WebGL (M3).
					args: process.env.CI ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : []
				}
			}
		}
	]
});
