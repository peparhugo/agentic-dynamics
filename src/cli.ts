#!/usr/bin/env node
import { buildSiteWithStats } from './generator';
import { startDevelopmentServer } from './dev-server';

function parseArguments(args: string[]): { contentDir?: string; outputDir?: string; templateDir?: string; port?: number; incremental?: boolean; clean?: boolean } {
  const options: { contentDir?: string; outputDir?: string; templateDir?: string; port?: number; incremental?: boolean; clean?: boolean } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content') options.contentDir = args[++index];
    else if (argument === '--output') options.outputDir = args[++index];
    else if (argument === '--templates') options.templateDir = args[++index];
    else if (argument === '--incremental') options.incremental = true;
    else if (argument === '--clean') options.clean = true;
    else if (argument === '--port') {
      const port = Number(args[++index]);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer between 1 and 65535');
      options.port = port;
    } else if (argument !== 'build' && argument !== 'serve') throw new Error(`Unknown argument: ${argument}`);
  }
  return options;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] === 'build') {
    const { pages, stats } = await buildSiteWithStats(parseArguments(args));
    console.log(`Generated ${pages.length} page(s).`);
    console.log(`Pages built: ${stats.pagesBuilt}, pages skipped: ${stats.pagesSkipped}, time saved: ${stats.timeSavedMs}ms.`);
    return;
  }
  if (args[0] === 'serve') {
    await startDevelopmentServer(parseArguments(args));
    return;
  }
  throw new Error('Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>]\n       ssg serve [--port <port>] [--content <dir>] [--output <dir>] [--templates <dir>]');
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
