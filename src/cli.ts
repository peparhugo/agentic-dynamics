#!/usr/bin/env node

import { build } from './generator';

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
    process.exit(1);
  }

  let contentDir = './content';
  let outputDir = './dist';

  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--content' && args[i + 1]) {
      contentDir = args[i + 1];
      i++;
    } else if (args[i] === '--output' && args[i + 1]) {
      outputDir = args[i + 1];
      i++;
    }
  }

  try {
    await build(contentDir, outputDir);
    console.log(`✓ Site built successfully to ${outputDir}`);
  } catch (error) {
    if (error instanceof Error) {
      console.error(`✗ Error: ${error.message}`);
    } else {
      console.error('✗ Unknown error occurred');
    }
    process.exit(1);
  }
}

main();
