#!/usr/bin/env node
import { buildSite } from './generator';
import { startServer } from './server';

function optionValue(args: string[], option: string): string | undefined {
  const index = args.indexOf(option);
  if (index === -1) return undefined;
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(`${option} requires a value`);
  return args[index + 1];
}

function portValue(args: string[]): number | undefined {
  const value = optionValue(args, '--port');
  if (value === undefined) return undefined;
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port must be an integer between 1 and 65535');
  return port;
}

function main(args: string[]): void {
  const options = {
    contentDir: optionValue(args, '--content'),
    outputDir: optionValue(args, '--output'),
    templatesDir: optionValue(args, '--templates'),
  };
  if (args[0] === 'serve') {
    startServer({ ...options, port: portValue(args) });
    return;
  }
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n       ssg serve [--port <port>] [--content <dir>] [--output <dir>] [--templates <dir>]');
  const pages = buildSite(options);
  console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

try {
  main(process.argv.slice(2));
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
}
