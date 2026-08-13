#!/usr/bin/env node
import { startDevelopmentServer } from '../plugins/dev-server.js';
import { buildSite, type BuildStats } from './generator.js';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean]\n       ssg serve [--content <dir>] [--templates <dir>] [--port <port>]';
}

export interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

export function parseArguments(args: string[]): CliOptions {
  const command = args[0];
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options: CliOptions = {};
  for (let index = 1; index < args.length; index += 1) {
    const flag = args[index];
    if (flag === '--incremental' || flag === '--clean') {
      if (command !== 'build') throw new Error(usage());
      if (flag === '--incremental') options.incremental = true;
      if (flag === '--clean') options.clean = true;
      continue;
    }
    const value = args[index + 1];
    if ((flag !== '--content' && flag !== '--output' && flag !== '--templates' && flag !== '--port') || !value || value.startsWith('--')) throw new Error(usage());
    if ((command === 'serve' && flag === '--output') || (command === 'build' && flag === '--port')) throw new Error(usage());
    if (flag === '--content') options.contentDir = value;
    if (flag === '--output') options.outputDir = value;
    if (flag === '--templates') options.templatesDir = value;
    if (flag === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(usage());
      options.port = port;
    }
    index += 1;
  }
  return options;
}

export { startDevelopmentServer } from '../plugins/dev-server.js';

async function main(): Promise<void> {
  try {
    const args = process.argv.slice(2);
    const options = parseArguments(args);
    if (args[0] === 'serve') {
      const server = await startDevelopmentServer(options);
      const address = server.server.address();
      const port = typeof address === 'object' && address ? address.port : options.port ?? 3000;
      process.stdout.write(`Serving at http://localhost:${port}\n`);
      return;
    }
    let stats: BuildStats | undefined;
    const pages = await buildSite({ ...options, onBuildComplete: (result) => { stats = result; } });
    process.stdout.write(`Generated ${pages.length} page(s).\n`);
    process.stdout.write(`Build stats: ${stats?.pagesBuilt ?? 0} pages built, ${stats?.pagesSkipped ?? 0} pages skipped, ${stats?.timeSavedMs ?? 0}ms saved.\n`);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}

void main();
