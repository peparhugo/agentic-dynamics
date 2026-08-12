#!/usr/bin/env node
import path from 'node:path';
import { buildSite } from './generator';
import { startDevServer, type ServeOptions } from './server';

function parseArgs(args: string[]): { command: 'build' | 'serve'; options: ServeOptions } {
  if (args[0] !== 'build' && args[0] !== 'serve') throw new Error('Usage: ssg build|serve [--content <dir>] [--output <dir>] [--templates <dir>] [--config <file>] [--port <port>]');
  let contentDir = './content';
  let outputDir = './dist';
  let templatesDir: string | undefined;
  let config: string | undefined;
  let port = 3000;
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--content' || option === '--output' || option === '--templates' || option === '--config' || option === '--port') && value && !value.startsWith('--')) {
      if (option === '--content') contentDir = value;
      else if (option === '--output') outputDir = value;
      else if (option === '--templates') templatesDir = value;
      else if (option === '--config') config = value;
      else {
        port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${value}`);
      }
      index += 1;
    } else {
      throw new Error(`Unknown or incomplete option: ${option}`);
    }
  }
  return {
    command: args[0],
    options: args[0] === 'serve'
      ? { contentDir, outputDir, templatesDir, config, port }
      : { contentDir, outputDir, templatesDir, config },
  };
}

export async function run(args: string[] = process.argv.slice(2)): Promise<void> {
  const parsed = parseArgs(args);
  if (parsed.command === 'serve') {
    await startDevServer(parsed.options);
    process.stdout.write(`Serving ${path.resolve(parsed.options.outputDir ?? './dist')} on http://localhost:${parsed.options.port}\n`);
    return;
  }
  const pages = await buildSite(parsed.options);
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}\n`);
}

if (require.main === module) {
  run().catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
