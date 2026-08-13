#!/usr/bin/env node
import { buildSite } from './site.js';
import { startDevelopmentServer } from './server.js';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>] [--incremental] [--clean]';
}

function parseArguments(arguments_: string[]): { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number; incremental?: boolean; clean?: boolean } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number; incremental?: boolean; clean?: boolean } = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === '--incremental') options.incremental = true;
    else if (argument === '--clean') options.clean = true;
    else if (argument === '--content' || argument === '--output' || argument === '--templates' || argument === '--port') {
      const value = arguments_[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else if (argument === '--templates') options.templatesDir = value;
      else {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port must be an integer between 1 and 65535');
        options.port = port;
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
  const options = parseArguments(arguments_);
  if (command === 'build') {
    const pages = await buildSite(options);
    process.stdout.write(`Built ${pages.stats.pagesBuilt} page(s), skipped ${pages.stats.pagesSkipped}; time saved: ${pages.stats.timeSaved} page(s).\n`);
    return;
  }
  const developmentServer = await startDevelopmentServer(options);
  process.stdout.write(`Serving on http://localhost:${developmentServer.port}\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
