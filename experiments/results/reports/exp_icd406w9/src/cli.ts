#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import { build } from "./build.js";
import { serve } from "./server.js";

export interface CliOptions {
  command: "build" | "serve";
  source: string;
  templates: string;
  output: string;
  drafts: boolean;
  port: number;
  siteTitle: string;
  siteUrl: string;
  help: boolean;
}

export const HELP = `ssg - static site generator

Usage:
  ssg build [options]   Build the site once
  ssg serve [options]   Build, serve, and rebuild on changes (live reload)

Options:
  -s, --source <dir>      Markdown source directory      (default: content)
  -t, --templates <dir>   Handlebars template directory  (default: templates)
  -o, --output <dir>      Output directory               (default: dist-site)
  -d, --drafts            Include draft: true pages
  -p, --port <n>          Dev server port                (default: 3000)
      --site-title <s>    Site title (templates + RSS)   (default: Site)
      --site-url <url>    Absolute site URL for RSS      (default: http://localhost)
  -h, --help              Show this help
`;

export class CliError extends Error {}

/** Parse argv (without the leading node/script entries) into CLI options. */
export function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    command: "build",
    source: "content",
    templates: "templates",
    output: "dist-site",
    drafts: false,
    port: 3000,
    siteTitle: "Site",
    siteUrl: "http://localhost",
    help: false,
  };

  const args = [...argv];
  const first = args[0];
  if (first === "build" || first === "serve") {
    opts.command = first;
    args.shift();
  } else if (first && !first.startsWith("-")) {
    throw new CliError(`Unknown command: ${first}`);
  }

  const takeValue = (flag: string): string => {
    const v = args.shift();
    if (v === undefined || v.startsWith("-")) {
      throw new CliError(`Missing value for ${flag}`);
    }
    return v;
  };

  while (args.length) {
    const arg = args.shift()!;
    switch (arg) {
      case "-s":
      case "--source":
        opts.source = takeValue(arg);
        break;
      case "-t":
      case "--templates":
        opts.templates = takeValue(arg);
        break;
      case "-o":
      case "--output":
        opts.output = takeValue(arg);
        break;
      case "-d":
      case "--drafts":
        opts.drafts = true;
        break;
      case "-p":
      case "--port": {
        const n = Number(takeValue(arg));
        if (!Number.isInteger(n) || n < 0 || n > 65535) {
          throw new CliError(`Invalid port: ${n}`);
        }
        opts.port = n;
        break;
      }
      case "--site-title":
        opts.siteTitle = takeValue(arg);
        break;
      case "--site-url":
        opts.siteUrl = takeValue(arg);
        break;
      case "-h":
      case "--help":
        opts.help = true;
        break;
      default:
        throw new CliError(`Unknown option: ${arg}`);
    }
  }
  return opts;
}

export async function main(argv: string[]): Promise<number> {
  let opts: CliOptions;
  try {
    opts = parseArgs(argv);
  } catch (err) {
    if (err instanceof CliError) {
      console.error(`Error: ${err.message}\n\n${HELP}`);
      return 2;
    }
    throw err;
  }

  if (opts.help) {
    console.log(HELP);
    return 0;
  }

  const shared = {
    source: opts.source,
    templates: opts.templates,
    output: opts.output,
    includeDrafts: opts.drafts,
    siteTitle: opts.siteTitle,
    siteUrl: opts.siteUrl,
  };

  if (opts.command === "serve") {
    await serve({ ...shared, port: opts.port });
    return 0; // keeps running; server holds the event loop
  }

  const result = await build(shared);
  console.log(
    `Built ${result.pages.length} page(s), ${result.tagPages.length} tag page(s), ` +
      `feed.xml (${result.skippedDrafts} draft(s) skipped) -> ${opts.output}`
  );
  return 0;
}

const isDirectRun =
  process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isDirectRun) {
  main(process.argv.slice(2)).then(
    (code) => {
      if (code !== 0) process.exitCode = code;
    },
    (err) => {
      console.error(err instanceof Error ? err.message : err);
      process.exitCode = 1;
    }
  );
}
