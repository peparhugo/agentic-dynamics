#!/usr/bin/env node
import { buildSite } from './site';
import { startDevelopmentServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]';
}

function parseArguments(args: string[]): { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument !== '--content' && argument !== '--output' && argument !== '--templates' && argument !== '--port') throw new Error(`Unknown option: ${argument}`);
    const value = args[index + 1];
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
  }
  return options;
}

function main(): void {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options = parseArguments(args);
  if (command === 'serve') {
    const developmentServer = startDevelopmentServer(options);
    developmentServer.server.once('listening', () => process.stdout.write(`Serving on http://localhost:${options.port ?? 3000}\n`));
    return;
  }
  const pages = buildSite(options);
  process.stdout.write(`Generated ${pages.length} page(s).\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
