#!/usr/bin/env node

import { buildSite } from './index';
import { startDevServer } from './server';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
}

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]';
}

function parseOptions(args: string[], allowPort: boolean): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const option = args[index];
    if (option !== '--content' && option !== '--output' && option !== '--templates' && (option !== '--port' || !allowPort)) {
      throw new Error(`Unknown option: ${option}`);
    }
    const value = args[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${option}`);
    if (option === '--content') options.contentDir = value;
    if (option === '--output') options.outputDir = value;
    if (option === '--templates') options.templatesDir = value;
    if (option === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${value}`);
      options.port = port;
    }
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const [command, ...optionArgs] = args;
  if (command === 'build') {
    const pages = await buildSite(parseOptions(optionArgs, false));
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
    return;
  }
  if (command === 'serve') {
    const server = await startDevServer(parseOptions(optionArgs, true));
    process.stdout.write(`Serving dist at http://localhost:${server.port}\n`);
    return;
  }
  throw new Error(usage());
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
