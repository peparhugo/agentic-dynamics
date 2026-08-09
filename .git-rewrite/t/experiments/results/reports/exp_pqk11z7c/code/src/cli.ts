#!/usr/bin/env node
import { Command } from "commander";
import path from "node:path";
import { buildSite } from "./build.js";
import { startDevServer } from "./server.js";
import type { SiteConfig } from "./types.js";

interface CommonOpts {
  source: string;
  templates: string;
  out: string;
  baseUrl: string;
  title: string;
  description: string;
  drafts: boolean;
}

function toConfig(opts: CommonOpts): SiteConfig {
  return {
    sourceDir: path.resolve(opts.source),
    templateDir: path.resolve(opts.templates),
    outDir: path.resolve(opts.out),
    baseUrl: opts.baseUrl,
    siteTitle: opts.title,
    siteDescription: opts.description,
    includeDrafts: opts.drafts,
  };
}

function addCommonOptions(cmd: Command): Command {
  return cmd
    .option("-s, --source <dir>", "source directory of markdown files", "content")
    .option("-t, --templates <dir>", "handlebars template directory", "templates")
    .option("-o, --out <dir>", "output directory", "dist-site")
    .option("--base-url <url>", "site base URL for absolute links/RSS", "http://localhost:3000")
    .option("--title <title>", "site title", "My Site")
    .option("--description <desc>", "site description", "")
    .option("--drafts", "include draft pages", false);
}

export function createProgram(): Command {
  const program = new Command();
  program.name("ssg").description("Static site generator: Markdown + Handlebars").version("1.0.0");

  addCommonOptions(program.command("build").description("build the site"))
    .action((opts: CommonOpts) => {
      const config = toConfig(opts);
      const result = buildSite(config);
      console.log(`[ssg] built ${result.filesWritten.length} files to ${config.outDir}`);
    });

  addCommonOptions(program.command("serve").description("build and serve with live reload"))
    .option("-p, --port <port>", "port to listen on", "3000")
    .action(async (opts: CommonOpts & { port: string }) => {
      await startDevServer(toConfig(opts), parseInt(opts.port, 10));
    });

  return program;
}

const isMain = process.argv[1] && import.meta.url.endsWith(path.basename(process.argv[1]));
if (isMain) {
  createProgram().parseAsync(process.argv).catch((err) => {
    console.error("[ssg] error:", err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
