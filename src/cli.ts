#!/usr/bin/env node
import { buildSiteWithStats } from './ssg';
import { startDevServer } from './serve';

function usage(): never {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean]');
  console.error('   or: ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]');
  process.exit(1);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args.shift();
  if (command !== 'build' && command !== 'serve') usage();
  let contentDir: string | undefined;
  let outputDir: string | undefined;
  let templatesDir: string | undefined;
  let port: number | undefined;
  let incremental = false;
  let clean = false;
  while (args.length) {
    const option = args.shift();
    if (option === '--incremental') { if (command !== 'build') usage(); incremental = true; continue; }
    if (option === '--clean') { if (command !== 'build') usage(); clean = true; continue; }
    if (option !== '--content' && option !== '--output' && option !== '--templates' && option !== '--port') usage();
    if (option === '--port' && command !== 'serve') usage();
    const value = args.shift();
    if (!value || value.startsWith('--')) usage();
    if (option === '--content') contentDir = value;
    else if (option === '--output') outputDir = value;
    else if (option === '--templates') templatesDir = value;
    else {
      port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) usage();
    }
  }
  if (command === 'serve') {
    const server = await startDevServer({ contentDir, outputDir, templatesDir, port });
    console.log(`Serving ${server.outputDir} at http://localhost:${server.port}`);
    return;
  }
  const result = await buildSiteWithStats({ contentDir, outputDir, templatesDir, incremental, clean });
  console.log(`Built ${result.stats.pagesBuilt}, skipped ${result.stats.pagesSkipped} page${result.pages.length === 1 ? '' : 's'} (${result.stats.timeSavedMs}ms saved).`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
