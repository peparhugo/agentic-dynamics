#!/usr/bin/env node
import { buildSite } from './index.js';
import { startDevServer } from './server.js';

export interface CliOptions {
  command?: string;
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
}

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]';
}

export function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = { command: args[0] };
  for (let index = 1; index < args.length; index += 1) {
    const argument = args[index];
    if (argument !== '--content' && argument !== '--output' && argument !== '--templates' && argument !== '--port') {
      throw new Error(`Unknown option: ${argument}`);
    }
    const value = args[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${argument}`);
    }
    if (argument === '--content') options.contentDir = value;
    if (argument === '--output') options.outputDir = value;
    if (argument === '--templates') options.templatesDir = value;
    if (argument === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error(`Invalid port: ${value}`);
      }
      options.port = port;
    }
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const options = parseArgs(args);
  if (options.command === 'build') {
    if (options.port !== undefined) throw new Error('--port is only valid with the serve command');
    const pages = await buildSite(options);
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
    return;
  }
  if (options.command === 'serve') {
    const server = await startDevServer(options);
    process.stdout.write(`Development server running at http://localhost:${server.port}\n`);
    return;
  }
  throw new Error(usage());
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
