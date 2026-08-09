#!/usr/bin/env node
import path from "node:path";
import { buildSite } from "./build.js";
import { serve } from "./server.js";
import type { SiteConfig } from "./types.js";

export interface CliOptions {
  command: "build" | "serve" | "help";
  source: string;
  templates: string;
  out: string;
  baseUrl: string;
  title: string;
  drafts: boolean;
  port: number;
}

export const DEFAULTS: Omit<CliOptions, "command"> = {
  source: "content",
  templates: "templates",
  out: "dist-site",
  baseUrl: "http://localhost:3000",
  title: "My Site",
  drafts: false,
  port: 3000,
};

const FLAG_ALIASES: Record<string, string> = {
  "-s": "--source",
  "-t": "--templates",
  "-o": "--out",
  "-p": "--port",
};

/** Parse CLI arguments. Throws on unknown flags or missing values. */
export function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = { command: "help", ...DEFAULTS };
  const args = [...argv];

  const cmd = args[0];
  if (cmd === "build" || cmd === "serve") {
    opts.command = cmd;
    args.shift();
  } else if (cmd === "help" || cmd === "--help" || cmd === "-h" || cmd === undefined) {
    opts.command = "help";
    return opts;
  } else {
    throw new Error(`Unknown command: ${cmd}`);
  }

  while (args.length > 0) {
    let flag = args.shift()!;
    flag = FLAG_ALIASES[flag] ?? flag;
    const takeValue = (): string => {
      const v = args.shift();
      if (v === undefined || v.startsWith("-")) throw new Error(`Missing value for ${flag}`);
      return v;
    };
    switch (flag) {
      case "--source": opts.source = takeValue(); break;
      case "--templates": opts.templates = takeValue(); break;
      case "--out": opts.out = takeValue(); break;
      case "--base-url": opts.baseUrl = takeValue(); break;
      case "--title": opts.title = takeValue(); break;
      case "--drafts": opts.drafts = true; break;
      case "--port": {
        const v = Number(takeValue());
        if (!Number.isInteger(v) || v < 0 || v > 65535) throw new Error(`Invalid port: ${v}`);
        opts.port = v;
        break;
      }
      default:
        throw new Error(`Unknown flag: ${flag}`);
    }
  }
  return opts;
}

export function toSiteConfig(opts: CliOptions, cwd = process.cwd()): SiteConfig {
  return {
    sourceDir: path.resolve(cwd, opts.source),
    templateDir: path.resolve(cwd, opts.templates),
    outDir: path.resolve(cwd, opts.out),
    baseUrl: opts.baseUrl,
    title: opts.title,
    includeDrafts: opts.drafts,
  };
}

const HELP = `ssg — static site generator

Usage:
  ssg build [options]   Build the site once
  ssg serve [options]   Build, serve, and live-reload on changes

Options:
  -s, --source <dir>      Markdown source directory (default: content)
  -t, --templates <dir>   Handlebars template directory (default: templates)
  -o, --out <dir>         Output directory (default: dist-site)
      --base-url <url>    Absolute base URL for RSS links
      --title <title>     Site title
      --drafts            Include posts marked draft: true
  -p, --port <port>       Dev server port (default: 3000, serve only)
  -h, --help              Show this help
`;

async function main(): Promise<void> {
  let opts: CliOptions;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(err instanceof Error ? err.message : err);
    console.error(HELP);
    process.exit(2);
  }

  if (opts.command === "help") {
    console.log(HELP);
    return;
  }

  const site = toSiteConfig(opts);
  if (opts.command === "build") {
    const result = buildSite(site);
    console.log(`[ssg] built ${result.posts.length} posts, ${result.tagIndex.size} tags, ${result.pagesWritten.length} files -> ${site.outDir}`);
  } else {
    await serve(site, opts.port);
  }
}

// Only run when executed directly (not when imported by tests).
if (process.argv[1] && /cli\.(ts|js)$/.test(process.argv[1])) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
