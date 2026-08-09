#!/usr/bin/env node
import { Command } from "commander";
import { build } from "./build.js";
import { startServer } from "./server.js";
import { generateRss } from "./rss.js";
import type { BuilderOptions } from "./types.js";

function makeOpts(cmd: Command): BuilderOptions {
  const opts = cmd.opts();
  return {
    sourceDir: opts.source,
    templateDir: opts.templates,
    outputDir: opts.output,
    baseUrl: opts.baseUrl ?? "http://localhost:3000/",
    siteTitle: opts.title ?? "My Site",
    siteDescription: opts.description ?? "A static site",
  };
}

const program = new Command()
  .name("static-gen")
  .version("1.0.0")
  .description("Static site generator");

program.option("-s, --source <dir>", "Source directory of markdown files", "content")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated HTML", "dist")
  .option("--base-url <url>", "Site base URL", "http://localhost:3000/")
  .option("--title <title>", "Site title", "My Site")
  .option("--description <desc>", "Site description", "A static site");

program
  .command("build")
  .description("Build the static site")
  .action(() => {
    const opts = makeOpts(program);
    const result = build(opts);
    generateRss(result.posts, opts.outputDir, opts.baseUrl, opts.siteTitle, opts.siteDescription);
    console.log(`Built ${result.posts.length} posts, ${result.tagPages.length} tag pages to ${opts.outputDir}`);
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .option("-p, --port <port>", "Port to listen on", "3000")
  .action((cmd) => {
    const opts = makeOpts(program);
    startServer(opts, parseInt(cmd.port, 10));
  });

program.parse();
