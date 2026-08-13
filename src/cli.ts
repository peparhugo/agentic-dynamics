#!/usr/bin/env node
import { buildSite } from './generator';
import { startDevelopmentServer } from './dev-server';

function parseArguments(args: string[]): { contentDir?: string; outputDir?: string; templateDir?: string; port?: number } {
  const options: { contentDir?: string; outputDir?: string; templateDir?: string; port?: number } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content') options.contentDir = args[++index];
    else if (argument === '--output') options.outputDir = args[++index];
    else if (argument === '--templates') options.templateDir = args[++index];
    else if (argument === '--port') {
      const port = Number(args[++index]);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer between 1 and 65535');
      options.port = port;
    } else if (argument !== 'build' && argument !== 'serve') throw new Error(`Unknown argument: ${argument}`);
  }
  return options;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] === 'build') {
    const pages = await buildSite(parseArguments(args));
    console.log(`Generated ${pages.length} page(s).`);
    return;
  }
  if (args[0] === 'serve') {
    await startDevelopmentServer(parseArguments(args));
    return;
  }
  throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n       ssg serve [--port <port>] [--content <dir>] [--output <dir>] [--templates <dir>]');
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
