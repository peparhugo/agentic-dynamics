#!/usr/bin/env node
import { buildSite } from './generator.js';
import { serveSite } from './server.js';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]';
}

function parseArguments(arguments_: string[]): { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number } = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === '--content' || argument === '--output' || argument === '--templates' || argument === '--port') {
      const value = arguments_[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else if (argument === '--templates') options.templatesDir = value;
      else {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${value}`);
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
  if (command === 'serve') {
    await serveSite(options);
    return;
  }
  const pages = await buildSite(options);
  process.stdout.write(`Built ${pages.length} page(s).\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
