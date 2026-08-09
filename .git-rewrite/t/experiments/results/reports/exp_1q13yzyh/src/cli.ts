#!/usr/bin/env node
import { pathToFileURL } from "node:url";
import { Command } from "commander";
import { buildSite, type BuildOptions } from "./build.js";
import { startDevServer, type DevServer } from "./server.js";

interface CommonFlags {
  source: string;
  templates: string;
  out: string;
  baseUrl: string;
  title: string;
  description: string;
  drafts: boolean;
}

function toBuildOptions(flags: CommonFlags): BuildOptions {
  return {
    sourceDir: flags.source,
    templateDir: flags.templates,
    outDir: flags.out,
    baseUrl: flags.baseUrl,
    siteTitle: flags.title,
    siteDescription: flags.description,
    includeDrafts: flags.drafts,
  };
}

function addCommonFlags(cmd: Command): Command {
  return cmd
    .option("-s, --source <dir>", "source directory of markdown files", "content")
    .option("-t, --templates <dir>", "template directory", "templates")
    .option("-o, --out <dir>", "output directory", "dist")
    .option("--base-url <url>", "site base URL (used in RSS)", "http://localhost:3000")
    .option("--title <title>", "site title", "My Site")
    .option("--description <text>", "site description", "")
    .option("--drafts", "include draft posts", false);
}

export interface CliHooks {
  /** Called with the started dev server so tests/callers can shut it down. */
  onServe?: (server: DevServer) => void;
}

export function makeProgram(hooks: CliHooks = {}): Command {
  const program = new Command();
  program.name("ssg").description("Static site generator").version("1.0.0");

  addCommonFlags(program.command("build"))
    .description("build the site once")
    .action(async (flags: CommonFlags) => {
      const result = await buildSite(toBuildOptions(flags));
      console.log(`[ssg] built ${result.posts.length} posts, ${result.files.length} files -> ${flags.out}`);
    });

  addCommonFlags(program.command("serve"))
    .description("build, serve, and rebuild on change with live reload")
    .option("-p, --port <port>", "port to listen on", (v) => Number.parseInt(v, 10), 3000)
    .action(async (flags: CommonFlags & { port: number }) => {
      const server = await startDevServer({ ...toBuildOptions(flags), port: flags.port });
      hooks.onServe?.(server);
    });

  return program;
}

export async function runCli(argv: string[], hooks: CliHooks = {}): Promise<void> {
  await makeProgram(hooks).parseAsync(argv);
}

const isMain =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  runCli(process.argv).catch((err) => {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
