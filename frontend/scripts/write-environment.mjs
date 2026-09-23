import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const configuredApiUrl = process.env.REVISEE_API_URL?.trim();

if (!configuredApiUrl) {
  throw new Error('REVISEE_API_URL is required for a production frontend build.');
}

let apiUrl;
try {
  apiUrl = new URL(configuredApiUrl);
} catch {
  throw new Error('REVISEE_API_URL must be a valid absolute URL.');
}

if (apiUrl.protocol !== 'https:') {
  throw new Error('REVISEE_API_URL must use HTTPS for production builds.');
}

if (apiUrl.username || apiUrl.password || apiUrl.search || apiUrl.hash) {
  throw new Error('REVISEE_API_URL must not contain credentials, a query, or a fragment.');
}

const normalizedApiUrl = apiUrl.toString().replace(/\/$/, '');
const outputPath = fileURLToPath(
  new URL('../src/environments/environment.production.ts', import.meta.url),
);

mkdirSync(fileURLToPath(new URL('../src/environments', import.meta.url)), { recursive: true });
writeFileSync(
  outputPath,
  `// Generated during the production build. Do not commit this file.\n` +
    `export const environment = {\n` +
    `  production: true,\n` +
    `  apiUrl: ${JSON.stringify(normalizedApiUrl)},\n` +
    `  features: {\n` +
    `    phase3Results: true,\n` +
    `    phase4SmartRevision: false,\n` +
    `  },\n` +
    `};\n`,
  { encoding: 'utf8', mode: 0o600 },
);

console.log('Generated the production Angular environment.');
