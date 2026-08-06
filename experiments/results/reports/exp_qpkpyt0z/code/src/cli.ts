import { Command } from "commander";
import { resolve } from "node:path";
import { generate } from "./generator.js";
import { startDevServer } from "./dev-server.js";
import type { SiteConfig } from "./types.js";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator from Markdown files")
  .version("1.0.0")
  .option("-s, --source <dir>", "Source directory of Markdown files", "./content")
  .option("-t, --templates <dir>", "Template directory of Handlebars templates", "./templates")
  .option("-o, --output <dir>", "Output directory for generated site", "./dist-site")
  .option("--title <title>", "Site title", "My Site")
  .option("--url <url>", "Site URL for RSS feed", "http://localhost:3000")
  .option("--posts-per-page <n>", "Posts per page", "10");

function buildConfig(opts: Record<string, unknown>): SiteConfig {
  const sourceDir = resolve(String(opts.source ?? "./content"));
  const templateDir = resolve(String(opts.templates ?? "./templates"));
  const outputDir = resolve(String(opts.output ?? "./dist-site"));
  const siteTitle = String(opts.title ?? "My Site");
  const siteUrl = String(opts.url ?? "http://localhost:3000");
  const postsPerPage = parseInt(String(opts.postsPerPage ?? "10"), 10);

  return { sourceDir, templateDir, outputDir, siteTitle, siteUrl, postsPerPage };
}

program
  .command("build", { isDefault: true })
  .description("Build the static site")
  .action(async (opts) => {
    const parent = program.opts();
    const config = buildConfig(parent);
    console.log("Building site...");
    await generate(config);
    console.log(`Site built to ${config.outputDir}`);
  });

program
  .command("serve")
  .description("Start development server with live reload")
  .option("-p, --port <port>", "Port to listen on", "3000")
  .action(async (opts) => {
    const parent = program.opts();
    const config = buildConfig(parent);
    const port = parseInt(String(opts.port ?? "3000"), 10);
    await startDevServer(config, port);
  });

export default program;
