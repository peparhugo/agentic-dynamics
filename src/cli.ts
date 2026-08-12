#!/usr/bin/env node
import { buildSite } from './index';
import { startDevServer } from './server';
import path from 'node:path';

function argumentValue(args: string[], option: string): string | undefined {
  const index = args.indexOf(option);
  return index === -1 ? undefined : args[index + 1];
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] !== 'build' && args[0] !== 'serve') {
     throw new Error('Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>] | ssg serve [--port <number>]');
  }
  const content = argumentValue(args, '--content');
  const output = argumentValue(args, '--output');
  const templates = argumentValue(args, '--templates');
  const portValue = argumentValue(args, '--port');
  if (content === undefined && args.includes('--content') || output === undefined && args.includes('--output') || templates === undefined && args.includes('--templates') || portValue === undefined && args.includes('--port')) {
    throw new Error('Options --content, --output, and --templates require a directory');
  }
  if (args[0] === 'serve') {
    const port = portValue === undefined ? 3000 : Number(portValue);
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Option --port must be a valid port number');
    await startDevServer({ contentDir: content, outputDir: output, templatesDir: templates, port });
    process.stdout.write(`Serving ${path.resolve(output ?? './dist')} at http://localhost:${port}\n`);
    return;
  }
  const started = Date.now();
  const pages = await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: args.includes('--incremental'), clean: args.includes('--clean') });
  const cachePath = path.join(path.resolve(output ?? './dist'), '.ssg-cache.json');
  let stats = { pagesBuilt: pages.length, pagesSkipped: 0, timeSaved: 0 };
  try { stats = JSON.parse(await (await import('node:fs/promises')).readFile(cachePath, 'utf8')).stats ?? stats; } catch { /* stats are informational */ }
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} (${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped, ${stats.timeSaved}ms saved, ${Date.now() - started}ms total).\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
