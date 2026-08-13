#!/usr/bin/env node
import { buildSite } from './generator';
import { SsgEngine } from './engine';
import { serveSite, ServeOptions } from './server';

const usage = 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <number>]';

export function parseArgs(args: string[]): ServeOptions {
  const command = args[0];
  if (command !== 'build' && command !== 'serve') {
    throw new Error(usage);
  }

  const options: ServeOptions = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if (command === 'build' && (option === '--incremental' || option === '--clean')) {
      if (option === '--incremental') options.incremental = true;
      if (option === '--clean') options.clean = true;
      continue;
    }
    if ((option === '--content' || option === '--output' || option === '--templates') && value && !value.startsWith('--')) {
      if (option === '--content') options.contentDir = value;
      if (option === '--output') options.outputDir = value;
      if (option === '--templates') options.templatesDir = value;
      index += 1;
      continue;
    }
    if (command === 'serve' && option === '--port' && value && !value.startsWith('--')) {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error(`Invalid port: ${value}`);
      }
      options.port = port;
      index += 1;
      continue;
    }
    throw new Error(`Invalid option: ${option}`);
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const options = parseArgs(args);
  if (args[0] === 'serve') {
    await serveSite(options);
    return;
  }
  if (!options.incremental && !options.clean) {
    const pages = await buildSite(options);
    process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
    return;
  }
  const engine = new SsgEngine(options);
  try {
    await engine.build();
    const { pagesBuilt, pagesSkipped, durationMs, timeSavedMs } = engine.stats;
    process.stdout.write(`Built ${pagesBuilt}, skipped ${pagesSkipped} page${pagesSkipped === 1 ? '' : 's'} in ${Math.round(durationMs)}ms (${Math.round(timeSavedMs)}ms saved).\n`);
  } finally {
    await engine.stop();
  }
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
