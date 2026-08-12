#!/usr/bin/env node
import { buildSite, BuildOptions, getLastBuildStats } from './generator';
import { startDevServer } from './server';

export function parseArgs(args: string[]): BuildOptions & { port?: number } {
  const options: BuildOptions & { port?: number } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--port') {
      const value = args[++index];
      const port = Number(value);
      if (!value || !Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port requires a valid port');
      options.port = port;
    } else if (argument === '--content' || argument === '--output' || argument === '--templates') {
      const value = args[++index];
      if (!value) throw new Error(`${argument} requires a directory`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else options.templatesDir = value;
    } else if (argument === '--incremental') options.incremental = true;
    else if (argument === '--clean') options.clean = true;
    }
  }
  return options;
}

if (require.main === module) {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') {
    console.error('Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>] | ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
    process.exitCode = 1;
  } else {
    try {
      const options = parseArgs(args);
      if (command === 'serve') {
        startDevServer(options).then(() => console.log(`SSG dev server running at http://localhost:${options.port ?? 3000}`)).catch((error) => {
          console.error(error instanceof Error ? error.message : error);
          process.exitCode = 1;
        });
      } else {
        const pages = buildSite(parseArgs(args));
        const stats = getLastBuildStats();
        console.log(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} (${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped, ${stats.timeSaved}ms saved).`);
      }
    } catch (error) {
      console.error(error instanceof Error ? error.message : error);
      process.exitCode = 1;
    }
  }
}
