#!/usr/bin/env node

import { buildSite } from './index.js';
import { startDevServer } from './server.js';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
}

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]';
}

function parseOptions(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--content' || option === '--output' || option === '--templates') && (!value || value.startsWith('--'))) {
      throw new Error(`${option} requires a directory`);
    }
    if (option === '--port' && (!value || value.startsWith('--'))) {
      throw new Error('--port requires a value');
    }
    if (option === '--content') {
      options.contentDir = value;
      index += 1;
    } else if (option === '--output') {
      options.outputDir = value;
      index += 1;
    } else if (option === '--templates') {
      options.templatesDir = value;
      index += 1;
    } else if (option === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 0 || port > 65535) {
        throw new Error('--port must be an integer between 0 and 65535');
      }
      options.port = port;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${option}`);
    }
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  if (args[0] !== 'build' && args[0] !== 'serve') {
    throw new Error(usage());
  }
  const options = parseOptions(args.slice(1));
  if (args[0] === 'build') {
    if (options.port !== undefined) throw new Error('--port is only available for serve');
    const pages = await buildSite(options);
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
    return;
  }

  const server = await startDevServer(options);
  process.stdout.write(`Development server running at http://localhost:${server.port}\n`);
  const shutdown = (): void => { void server.close(); };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
