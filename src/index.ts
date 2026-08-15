#!/usr/bin/env node

import { parseArgs } from './cli.js';
import { build } from './ssg.js';

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  console.log(`
Static Site Generator

Usage: ssg build [options]

Options:
  --content <dir>   Content directory (default: ./content)
  --output <dir>    Output directory (default: ./dist)
  --help           Show this help message
  `);
  process.exit(0);
}

if (args.command !== 'build') {
  console.error('Error: only "build" command is supported');
  process.exit(1);
}

try {
  build(args.contentDir, args.outputDir);
  console.log(`✓ Site built successfully to ${args.outputDir}`);
} catch (err) {
  console.error('Build failed:', err instanceof Error ? err.message : String(err));
  process.exit(1);
}
