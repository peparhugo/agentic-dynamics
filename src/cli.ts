#!/usr/bin/env node
import { buildSiteWithStats } from './generator';
import { startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--incremental] [--clean] [--port <number>]';
}

function parseArguments(arguments_: string[], allowPort = false): { contentDir?: string; outputDir?: string; port?: number; incremental?: boolean; clean?: boolean } {
  const options: { contentDir?: string; outputDir?: string; port?: number; incremental?: boolean; clean?: boolean } = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (!allowPort && (argument === '--incremental' || argument === '--clean')) {
      options[argument === '--incremental' ? 'incremental' : 'clean'] = true;
    } else if (argument === '--content' || argument === '--output' || (allowPort && argument === '--port')) {
      const value = arguments_[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
      if (argument === '--port') {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer between 1 and 65535');
        options.port = port;
      } else {
        options[argument === '--content' ? 'contentDir' : 'outputDir'] = value;
      }
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

async function main(): Promise<void> {
  const [command, ...arguments_] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options = parseArguments(arguments_, command === 'serve');
  if (command === 'serve') {
    await startDevServer(options);
    return;
  }
  const { pages, stats } = await buildSiteWithStats(options);
  console.log(`Generated ${pages.length} page(s). Pages built: ${stats.pagesBuilt}, pages skipped: ${stats.pagesSkipped}, time saved: ${stats.timeSaved} page-build(s).`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
