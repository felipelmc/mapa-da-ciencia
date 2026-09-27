import { defineConfig, devices } from '@playwright/test';

// A abertura do site da documentação ("Céu que se forma"), sobre o site montado pelo MkDocs em ../site
// (`uv run --group docs mkdocs build` antes). Roda no workflow da documentação, que tem Python e Node.
export default defineConfig({
	testDir: 'tests/pagina',
	outputDir: 'test-results/pagina',
	globalSetup: './tests/pagina/preparar.ts',
	workers: 1,
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: 0,
	reporter: [['list']],
	use: { trace: 'retain-on-failure' },
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }]
});
