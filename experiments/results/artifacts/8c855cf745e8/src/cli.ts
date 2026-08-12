#!/usr/bin/env node
import { buildSite } from './generator';
import { startDevServer } from './server';

function usage(): void {
  console.error('Usage: ssg build|serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>] [--incremental] [--clean]');
}

export async function main(args: string[] = process.argv.slice(2)): Promise<void> {
  if (args[0] !== 'build' && args[0] !== 'serve') {
    usage();
    process.exitCode = 1;
    return;
  }
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number; incremental?: boolean; clean?: boolean } = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    if (option === '--incremental') options.incremental = true;
    else if (option === '--clean') options.clean = true;
    else if (option === '--content' || option === '--output' || option === '--templates' || option === '--port') {
      const value = args[index + 1];
      if (!value) throw new Error(`${option} requires a value`);
      if (option === '--port') {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('--port requires a valid port');
        options.port = port;
      } else if (option === '--content') options.contentDir = value;
      else if (option === '--output') options.outputDir = value;
      else options.templatesDir = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${option}`);
    }
  }
  if (args[0] === 'serve') {
    const server = await startDevServer(options);
    console.log(`Serving ${options.outputDir ?? './dist'} at http://localhost:${(server.server.address() as { port: number }).port}`);
    return;
  }
  const pages = await buildSite({ ...options, onStats: (stats) => console.log(`Built ${stats.pagesBuilt}, skipped ${stats.pagesSkipped} page${stats.pagesSkipped === 1 ? '' : 's'} (time saved: ${stats.timeSaved}).`) });
  if (!pages.stats.pagesSkipped) console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

if (require.main === module) {
  main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
