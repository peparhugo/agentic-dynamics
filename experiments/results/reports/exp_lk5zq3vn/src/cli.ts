#!/usr/bin/env node
import { buildSite } from "./build.js";
import { startDevServer } from "./server.js";
import { DEFAULT_CONFIG, type SiteConfig } from "./types.js";

export interface CliOptions {
  command: "build" | "serve" | "help";
  config: SiteConfig;
  port: number;
}

export const HELP = `ssgen - static site generator

Usage:
  ssgen build [options]   Build the site once
  ssgen serve [options]   Build, serve, and live-reload on changes

Options:
  -s, --source <dir>       Source dir of Markdown files   (default: content)
  -t, --templates <dir>    Handlebars template dir        (default: templates)
  -o, --out <dir>          Output dir                     (default: dist-site)
      --drafts             Include draft: true pages
      --base-url <url>     Absolute base URL for RSS links
      --title <str>        Site title
      --description <str>  Site description
  -p, --port <n>           Dev server port                (default: 3000)
  -h, --help               Show help
`;

/** Parse argv (without node/script prefix). Throws on unknown flags / missing values. */
export function parseArgs(argv: string[]): CliOptions {
  const config: SiteConfig = { ...DEFAULT_CONFIG };
  let command: CliOptions["command"] = "help";
  let port = 3000;

  const args = [...argv];
  const first = args[0];
  if (first === "build" || first === "serve") {
    command = first;
    args.shift();
  } else if (first === "help" || first === "-h" || first === "--help") {
    return { command: "help", config, port };
  } else if (first !== undefined && !first.startsWith("-")) {
    throw new Error(`Unknown command: ${first}`);
  }

  const need = (flag: string): string => {
    const v = args.shift();
    if (v === undefined || v.startsWith("-")) throw new Error(`Missing value for ${flag}`);
    return v;
  };

  while (args.length) {
    const a = args.shift()!;
    switch (a) {
      case "-s": case "--source": config.sourceDir = need(a); break;
      case "-t": case "--templates": config.templateDir = need(a); break;
      case "-o": case "--out": config.outDir = need(a); break;
      case "--drafts": config.includeDrafts = true; break;
      case "--base-url": config.baseUrl = need(a); break;
      case "--title": config.siteTitle = need(a); break;
      case "--description": config.siteDescription = need(a); break;
      case "-p": case "--port": {
        const n = Number(need(a));
        if (!Number.isInteger(n) || n < 0 || n > 65535) throw new Error(`Invalid port: ${n}`);
        port = n;
        break;
      }
      case "-h": case "--help": command = "help"; break;
      default: throw new Error(`Unknown flag: ${a}`);
    }
  }
  return { command, config, port };
}

export async function main(argv: string[]): Promise<number> {
  let opts: CliOptions;
  try {
    opts = parseArgs(argv);
  } catch (err) {
    console.error(String(err instanceof Error ? err.message : err));
    console.error(HELP);
    return 2;
  }

  if (opts.command === "help") {
    console.log(HELP);
    return 0;
  }
  if (opts.command === "build") {
    const t0 = Date.now();
    const { pages, written } = buildSite(opts.config);
    console.log(`[ssgen] ${pages.length} pages, ${written.length} files -> ${opts.config.outDir} in ${Date.now() - t0}ms`);
    return 0;
  }
  await startDevServer(opts.config, opts.port);
  return 0;
}

// Only run when executed directly (not when imported by tests).
if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then((code) => {
    if (code !== 0) process.exitCode = code;
  });
}
