#!/usr/bin/env node
import { buildSiteWithStats } from './generator';
import { startServer } from './server';

function options(args: string[]): { content: string; output: string; templates: string; port: number; incremental: boolean; clean: boolean } {
  let content = './content';
  let output = './dist';
  let templates = './templates';
  let port = 3000;
  let incremental = false;
  let clean = false;
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--content' && args[index + 1]) content = args[++index];
    else if (args[index] === '--output' && args[index + 1]) output = args[++index];
    else if (args[index] === '--templates' && args[index + 1]) templates = args[++index];
    else if (args[index] === '--port' && args[index + 1]) port = Number(args[++index]);
    else if (args[index] === '--incremental') incremental = true;
    else if (args[index] === '--clean') clean = true;
  }
  return { content, output, templates, port, incremental, clean };
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') {
    throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean]\n       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]');
  }
  const { content, output, templates, port, incremental, clean } = options(args);
  if (command === 'serve') {
    await startServer({ content, output, templates, port });
    return;
  }
  const result = await buildSiteWithStats(content, output, templates, { incremental, clean });
  process.stdout.write(`Built ${result.pages.length} page${result.pages.length === 1 ? '' : 's'} in ${output} (${result.stats.pagesBuilt} built, ${result.stats.pagesSkipped} skipped, ${result.stats.timeSavedMs}ms saved)\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
