#!/usr/bin/env node
import { buildSiteWithStats } from './generator.js';
import { parseBuildOptions, parseServeOptions } from './options.js';
import { startDevServer } from './server.js';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <port>]';
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command === 'build') {
    const { pages, stats } = await buildSiteWithStats(parseBuildOptions(args));
    process.stdout.write(`Generated ${pages.length} page(s). Built ${stats.pagesBuilt}, skipped ${stats.pagesSkipped}, time saved ${stats.timeSavedMs}ms.\n`);
    return;
  }
  if (command === 'serve') {
    const server = await startDevServer(parseServeOptions(args));
    process.stdout.write(`Serving on http://localhost:${server.port}\n`);
    return;
  }
  throw new Error(usage());
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
