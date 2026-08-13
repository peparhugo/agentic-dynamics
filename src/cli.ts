#!/usr/bin/env node

import { createEngine, BuildOptions } from './index';
import { startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <number>]';
}

export async function run(argv: string[]): Promise<void> {
  const command = argv[0];
  if (command !== 'build' && command !== 'serve') {
    throw new Error(usage());
  }

  const options: BuildOptions = {};
  let port = 3000;
  for (let index = 1; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === '--incremental' || argument === '--clean') {
      if (command !== 'build') throw new Error(`Unknown option: ${argument}\n${usage()}`);
      if (argument === '--incremental') options.incremental = true;
      if (argument === '--clean') options.clean = true;
      continue;
    }
    if (argument !== '--content' && argument !== '--output' && argument !== '--templates' && argument !== '--port') {
      throw new Error(`Unknown option: ${argument}\n${usage()}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${argument}\n${usage()}`);
    }
    if (argument === '--content') options.contentDir = value;
    if (argument === '--output') options.outputDir = value;
    if (argument === '--templates') options.templatesDir = value;
    if (argument === '--port') {
      if (command !== 'serve') throw new Error(`Unknown option: ${argument}\n${usage()}`);
      port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error(`Invalid port: ${value}\n${usage()}`);
      }
    }
    index += 1;
  }

  if (command === 'serve') {
    const server = await startDevServer({ ...options, port });
    process.stdout.write(`Development server running at http://localhost:${server.port}\n`);
    return;
  }

  const engine = await createEngine(options);
  const pages = await engine.build();
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
  const stats = engine.lastBuildStats;
  process.stdout.write(`Build stats: ${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped, ${Math.round(stats.timeSavedMs)}ms saved (${Math.round(stats.durationMs)}ms total).\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`${message}\n`);
    process.exitCode = 1;
  });
}
