#!/usr/bin/env node
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { build } from "./ssg.js";
import { serve } from "./server.js";

function parseArgs(args: string[]) {
  const opts: Record<string, string | boolean> = {};
  for (let i = 2; i < args.length; i++) {
    const a = args[i];
    if (a === "--source" || a === "-s") { opts.source = args[++i]; }
    else if (a === "--templates" || a === "-t") { opts.templates = args[++i]; }
    else if (a === "--output" || a === "-o") { opts.output = args[++i]; }
    else if (a === "--port" || a === "-p") { opts.port = args[++i]; }
    else if (a === "--serve" || a === "-S") { opts.serve = true; }
    else if (a === "--help" || a === "-h") { opts.help = true; }
    else if (a.startsWith("--")) { opts[a.slice(2)] = args[i + 1]?.startsWith("-") ? true : args[++i]; }
  }
  return opts;
}

function showHelp() {
  console.log(`
Usage: ssg [options]

Options:
  -s, --source <dir>      Source directory of Markdown files (default: ./content)
  -t, --templates <dir>   Template directory of Handlebars templates (default: ./templates)
  -o, --output <dir>      Output directory for generated HTML (default: ./dist)
  -S, --serve             Start dev server after build
  -p, --port <port>       Dev server port (default: 3000)
  -h, --help              Show this help
`);
}

async function main() {
  const opts = parseArgs(process.argv);

  if (opts.help) { showHelp(); process.exit(0); }

  const sourceDir = resolve(String(opts.source ?? "content"));
  const templateDir = resolve(String(opts.templates ?? "templates"));
  const outputDir = resolve(String(opts.output ?? "dist"));
  const port = parseInt(String(opts.port ?? "3000"), 10);

  if (!existsSync(sourceDir)) { console.error(`Source directory not found: ${sourceDir}`); process.exit(1); }
  if (!existsSync(templateDir)) { console.error(`Template directory not found: ${templateDir}`); process.exit(1); }

  console.log("Building site...");
  const result = build(sourceDir, templateDir, outputDir);
  console.log(`  ${result.posts.length} posts, ${result.tags.length} tag pages`);
  console.log("Site built to", outputDir);

  if (opts.serve) {
    serve(outputDir, sourceDir, templateDir, port);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
