#!/usr/bin/env node
import { buildSiteWithStats } from './generator';
import { ServeOptions, startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <number>]';
}

export function parseArguments(args: string[], allowPort = false): ServeOptions {
  const options: ServeOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--incremental' || argument === '--clean') {
      options[argument.slice(2) as 'incremental' | 'clean'] = true;
    } else if (argument === '--content' || argument === '--output' || argument === '--templates' || (allowPort && argument === '--port')) {
      const value = args[++index];
      if (!value || value.startsWith('--')) throw new Error(`${argument} requires a ${argument === '--port' ? 'number' : 'directory'}`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else if (argument === '--templates') options.templatesDir = value;
      else {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port requires a number between 1 and 65535');
        options.port = port;
      }
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  if (args[0] === 'build') {
    const { pages, stats } = await buildSiteWithStats(parseArguments(args.slice(1)));
    process.stdout.write(`Generated ${pages.length} page(s). Built ${stats.built}, skipped ${stats.skipped}, time saved ${stats.timeSavedMs}ms.\n`);
    return;
  }
  if (args[0] === 'serve') {
    const server = await startDevServer(parseArguments(args.slice(1), true));
    process.stdout.write(`Serving on http://localhost:${server.port}\n`);
    return;
  }
  throw new Error(usage());
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
