#!/usr/bin/env node

import { buildSite, BuildOptions } from './index';
import { startDevServer } from './server';

export interface CliIO {
  stdout: { write(chunk: string): unknown };
  stderr: { write(chunk: string): unknown };
}

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]\n';
}

function valueAfter(args: string[], index: number, option: string): string {
  const value = args[index + 1];
  if (!value || value.startsWith('--')) {
    throw new Error(`${option} requires a directory`);
  }
  return value;
}

export async function runCli(
  args: string[],
  io: CliIO = { stdout: process.stdout, stderr: process.stderr }
): Promise<number> {
  const command = args[0];
  if (command !== 'build' && command !== 'serve') {
    io.stderr.write(usage());
    return 1;
  }

  const options: BuildOptions = {};
  let port = 3000;
  try {
    for (let index = 1; index < args.length; index += 1) {
      const argument = args[index];
      if (argument === '--content') {
        options.contentDir = valueAfter(args, index, argument);
        index += 1;
      } else if (argument === '--output') {
        options.outputDir = valueAfter(args, index, argument);
        index += 1;
      } else if (argument === '--templates') {
        options.templatesDir = valueAfter(args, index, argument);
        index += 1;
      } else if (argument === '--port' && command === 'serve') {
        const value = valueAfter(args, index, argument);
        port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
          throw new Error(`Invalid port: ${value}`);
        }
        index += 1;
      } else {
        throw new Error(`Unknown option: ${argument}`);
      }
    }

    if (command === 'serve') {
      await startDevServer({ ...options, port, io });
      io.stdout.write(`Serving ${options.outputDir ?? './dist'} at http://localhost:${port}\n`);
    } else {
      const pages = await buildSite(options);
      io.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
    }
    return 0;
  } catch (error) {
    io.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    return 1;
  }
}

if (require.main === module) {
  void runCli(process.argv.slice(2)).then((exitCode) => {
    process.exitCode = exitCode;
  });
}
