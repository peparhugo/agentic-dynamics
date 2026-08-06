import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";

const projectRoot = path.resolve(import.meta.dirname ?? ".", "..");
const cliEntry = path.join(projectRoot, "dist", "index.js");

function runCli(args: string[]): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync("node", [cliEntry, ...args], {
    cwd: projectRoot,
    encoding: "utf-8",
    timeout: 15000,
  });
  return {
    status: result.status,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

describe("CLI build command", () => {
  let tmpOut: string;

  before(async () => {
    // Ensure the CLI is built
    const result = spawnSync("npx", ["tsc"], {
      cwd: projectRoot,
      encoding: "utf-8",
    });
    if (result.status !== 0) {
      console.error("TypeScript build failed:", result.stderr);
    }
  });

  after(async () => {
    if (tmpOut) {
      await fs.rm(tmpOut, { recursive: true, force: true });
    }
  });

  it("builds a site from source and templates", async () => {
    tmpOut = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-out-"));
    const sourceDir = path.join(projectRoot, "tests", "fixtures", "source");
    const tplDir = path.join(projectRoot, "tests", "fixtures", "templates");

    const { status, stdout, stderr } = runCli([
      "build",
      "-s", sourceDir,
      "-t", tplDir,
      "-o", tmpOut,
      "--site-title", "Test Site",
      "--site-description", "A test site",
      "--site-url", "http://example.com",
    ]);

    assert.equal(status, 0, `Build failed: ${stderr}`);

    const files = await fs.readdir(tmpOut);
    assert.ok(files.includes("index.html"));
    assert.ok(files.includes("hello-world.html"));
    assert.ok(files.includes("another-post.html"));
    assert.ok(files.includes("feed.xml"));

    const tagDir = path.join(tmpOut, "tags");
    const tagFiles = await fs.readdir(tagDir);
    assert.ok(tagFiles.includes("intro.html"));
    assert.ok(tagFiles.includes("tutorial.html"));
  });

  it("excludes drafts by default", async () => {
    tmpOut = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-out2-"));
    const sourceDir = path.join(projectRoot, "tests", "fixtures", "source");
    const tplDir = path.join(projectRoot, "tests", "fixtures", "templates");

    runCli(["build", "-s", sourceDir, "-t", tplDir, "-o", tmpOut]);
    const files = await fs.readdir(tmpOut);
    assert.ok(!files.includes("draft-post.html"));
  });

  it("includes drafts with --drafts flag", async () => {
    tmpOut = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-out3-"));
    const sourceDir = path.join(projectRoot, "tests", "fixtures", "source");
    const tplDir = path.join(projectRoot, "tests", "fixtures", "templates");

    runCli(["build", "-s", sourceDir, "-t", tplDir, "-o", tmpOut, "--drafts"]);
    const files = await fs.readdir(tmpOut);
    assert.ok(files.includes("draft-post.html"));
  });

  it("generates valid RSS feed", async () => {
    tmpOut = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-out4-"));
    const sourceDir = path.join(projectRoot, "tests", "fixtures", "source");
    const tplDir = path.join(projectRoot, "tests", "fixtures", "templates");

    runCli(["build", "-s", sourceDir, "-t", tplDir, "-o", tmpOut, "--site-url", "http://example.com"]);
    const feed = await fs.readFile(path.join(tmpOut, "feed.xml"), "utf-8");
    assert.ok(feed.includes("<?xml"));
    assert.ok(feed.includes("<rss"));
    assert.ok(feed.includes("<channel>"));
    assert.ok(feed.includes("<item>"));
    assert.ok(feed.includes("Hello World"));
  });

  it("generates HTML with syntax highlighting in code blocks", async () => {
    tmpOut = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-out5-"));
    const sourceDir = path.join(projectRoot, "tests", "fixtures", "source");
    const tplDir = path.join(projectRoot, "tests", "fixtures", "templates");

    runCli(["build", "-s", sourceDir, "-t", tplDir, "-o", tmpOut]);
    const helloWorld = await fs.readFile(path.join(tmpOut, "hello-world.html"), "utf-8");
    assert.ok(helloWorld.includes("hljs"));
    assert.ok(helloWorld.includes("language-javascript"));
    assert.ok(helloWorld.includes("language-python"));
  });
});

describe("CLI serve command", () => {
  it("shows help for serve command", () => {
    const { stdout } = runCli(["serve", "--help"]);
    assert.ok(stdout.includes("--port"));
    assert.ok(stdout.includes("--drafts"));
  });
});

describe("CLI help and version", () => {
  it("shows version", () => {
    const { stdout } = runCli(["--version"]);
    assert.ok(stdout.includes("1.0.0"));
  });

  it("shows help", () => {
    const { stdout } = runCli(["--help"]);
    assert.ok(stdout.includes("build"));
    assert.ok(stdout.includes("serve"));
  });
});
