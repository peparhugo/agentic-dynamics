#!/usr/bin/env node
import { buildSiteWithStats } from './build';
import { startDevServer } from './server';

function option(args: string[], name: string): string | undefined {
  const index = args.indexOf(name);
  if (index === -1) return undefined;
  const value = args[index + 1];
  if (!value || value.startsWith('--')) throw new Error(`${name} requires a value`);
  return value;
}

function portOption(args: string[]): number | undefined {
  const value = option(args, '--port');
  if (value === undefined) return undefined;
  const port = Number(value);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('--port must be an integer from 0 to 65535');
  return port;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] === 'build') {
    const result = await buildSiteWithStats(option(args, '--content'), option(args, '--output'), undefined, undefined, {
      incremental: args.includes('--incremental'),
      clean: args.includes('--clean'),
    });
    process.stdout.write(`Generated ${result.pages.length} page(s). Built ${result.stats.pagesBuilt}, skipped ${result.stats.pagesSkipped}, time saved ${result.stats.timeSavedMs}ms.\n`);
    return;
  }
  if (args[0] === 'serve') {
    const server = await startDevServer({ contentDirectory: option(args, '--content'), outputDirectory: option(args, '--output'), port: portOption(args) });
    process.stdout.write(`Serving on http://localhost:${server.port}\n`);
    return;
  }
  throw new Error('Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] | ssg serve [--port <port>] [--content <dir>] [--output <dir>]');
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
