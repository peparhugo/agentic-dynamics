#!/usr/bin/env node
import { buildSite } from './generator';
import { startServer } from './server';

function options(args: string[]): { content: string; output: string; templates: string; port: number } {
  let content = './content';
  let output = './dist';
  let templates = './templates';
  let port = 3000;
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--content' && args[index + 1]) content = args[++index];
    else if (args[index] === '--output' && args[index + 1]) output = args[++index];
    else if (args[index] === '--templates' && args[index + 1]) templates = args[++index];
    else if (args[index] === '--port' && args[index + 1]) port = Number(args[++index]);
  }
  return { content, output, templates, port };
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') {
    throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]');
  }
  const { content, output, templates, port } = options(args);
  if (command === 'serve') {
    await startServer({ content, output, templates, port });
    return;
  }
  const pages = await buildSite(content, output, templates);
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} in ${output}\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
