#!/usr/bin/env node
import { buildSiteWithStats } from './generator';
import { serveSite } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <port>]';
}

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

function options(args: string[], allowPort: boolean): CliOptions {
  const result: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index + 1];
    const option = args[index];
    if (option === '--incremental') { result.incremental = true; continue; }
    if (option === '--clean') { result.clean = true; continue; }
    if ((option === '--content' || option === '--output' || option === '--templates' || option === '--port') && (!value || value.startsWith('--'))) throw new Error(`Missing value for ${option}`);
    if (args[index] === '--content') result.contentDir = value;
    if (args[index] === '--output') result.outputDir = value;
    if (args[index] === '--templates') result.templateDir = value;
    if (option === '--port') {
      if (!allowPort) throw new Error(`Unknown option: ${option}`);
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer between 1 and 65535');
      result.port = port;
    }
    if (option.startsWith('--') && option !== '--content' && option !== '--output' && option !== '--templates' && option !== '--port') throw new Error(`Unknown option: ${option}`);
  }
  return result;
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command === 'build') {
    const result = await buildSiteWithStats(options(args, false));
    console.log(`Generated ${result.pages.length} page(s): ${result.stats.pagesBuilt} built, ${result.stats.pagesSkipped} skipped, ${result.stats.timeSavedMs}ms saved.`);
    return;
  }
  if (command === 'serve') {
    const { port, ...buildOptions } = options(args, true);
    await serveSite({ ...buildOptions, port });
    return;
  }
  throw new Error(usage());
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
