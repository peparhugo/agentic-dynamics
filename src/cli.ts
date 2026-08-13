#!/usr/bin/env node
import { buildSite } from './generator.js';
import { serveSite } from './server.js';

interface CliOptions {
  content?: string;
  output?: string;
  templates?: string;
  port?: number;
}

export function parseArguments(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output' || argument === '--templates' || argument === '--port') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error(argument === '--port' ? '--port requires a value' : `${argument} requires a directory`);
      if (argument === '--port') {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port must be an integer between 1 and 65535');
        options.port = port;
      } else {
        options[argument.slice(2) as 'content' | 'output' | 'templates'] = value;
      }
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const command = args[0];
  if (command === 'build') {
    const pages = await buildSite(parseArguments(args.slice(1)));
    process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
    return;
  }
  if (command === 'serve') {
    await serveSite(parseArguments(args.slice(1)));
    return;
  }
  throw new Error('Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
}

if (/cli\.(?:js|ts)$/.test(process.argv[1] ?? '')) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
