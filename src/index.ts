#!/usr/bin/env node

import { parseFiles } from './parser';
import { generateSite } from './generator';

function parseArgs(args: string[]): { contentDir: string; outputDir: string; command: string } {
  const command = args[0] || 'build';
  let contentDir = './content';
  let outputDir = './dist';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--content' && i + 1 < args.length) {
      contentDir = args[i + 1];
      i++;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      outputDir = args[i + 1];
      i++;
    }
  }

  return { command, contentDir, outputDir };
}

function main() {
  const args = process.argv.slice(2);
  const { command, contentDir, outputDir } = parseArgs(args);

  if (command !== 'build') {
    console.error(`Unknown command: ${command}`);
    console.error('Usage: npx ssg build [--content <dir>] [--output <dir>]');
    process.exit(1);
  }

  try {
    const parseResult = parseFiles({ contentDir, outputDir });
    generateSite(parseResult, outputDir);
    console.log(`Site generated in ${outputDir}`);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`Error: ${message}`);
    process.exit(1);
  }
}

main();
