#!/usr/bin/env node
import { buildSite, BuildOptions } from './index';
import { ServeOptions, startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>]\n'
    + '       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]';
}

export function parseArgs(args: string[]): BuildOptions {
  const options: BuildOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--incremental') options.incremental = true;
    else if (argument === '--clean') options.clean = true;
    else if (argument === '--content' || argument === '--output' || argument === '--templates') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${argument} requires a directory`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else options.templatesDir = value;
      index += 1;
    } else if (argument.startsWith('--')) {
      throw new Error(`Unknown option: ${argument}`);
    } else {
      throw new Error(`Unexpected argument: ${argument}`);
    }
  }
  return options;
}

export function parseServeArgs(args: string[]): ServeOptions {
  const options: ServeOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--port') {
      const value = args[index + 1];
      const port = Number(value);
      if (!value || value.startsWith('--') || !Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error('--port requires a number between 1 and 65535');
      }
      options.port = port;
      index += 1;
    } else if (argument === '--content' || argument === '--output' || argument === '--templates') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${argument} requires a directory`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else options.templatesDir = value;
      index += 1;
    } else if (argument.startsWith('--')) {
      throw new Error(`Unknown option: ${argument}`);
    } else {
      throw new Error(`Unexpected argument: ${argument}`);
    }
  }
  return options;
}

export function main(args: string[] = process.argv.slice(2)): void | Promise<void> {
  const [command, ...rest] = args;
  if (command === 'build') {
    const options = parseArgs(rest);
    options.onStats = (stats) => process.stdout.write(
      `Built ${stats.pagesBuilt} page(s), skipped ${stats.pagesSkipped}; saved ${stats.timeSavedMs.toFixed(1)}ms\n`,
    );
    buildSite(options);
  }
  else if (command === 'serve') return startDevServer(parseServeArgs(rest)).then(() => undefined);
  else throw new Error(usage());
}

if (require.main === module) {
  try {
    Promise.resolve(main()).catch((error) => {
      process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
      process.exitCode = 1;
    });
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
