#!/usr/bin/env node
import { buildSite } from './generator';

function options(args: string[]): { content: string; output: string } {
  let content = './content';
  let output = './dist';
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--content' && args[index + 1]) content = args[++index];
    else if (args[index] === '--output' && args[index + 1]) output = args[++index];
  }
  return { content, output };
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') {
    throw new Error('Usage: ssg build [--content <dir>] [--output <dir>]');
  }
  const { content, output } = options(args);
  const pages = await buildSite(content, output);
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} in ${output}\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
