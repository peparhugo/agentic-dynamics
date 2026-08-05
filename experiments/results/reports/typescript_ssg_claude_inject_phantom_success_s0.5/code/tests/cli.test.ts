import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createProgram } from "../src/cli.js";

let root: string;

function write(rel: string, content: string): void {
  const full = path.join(root, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
}

async function runCli(args: string[]): Promise<void> {
  const program = createProgram();
  program.exitOverride();
  await program.parseAsync(["node", "ssg", ...args]);
}

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-cli-"));
  write("content/a.md", `---\ntitle: A\ndate: 2024-01-01\ntags: [x]\n---\nhello`);
  write("content/d.md", `---\ntitle: D\ndraft: true\n---\nsecret`);
  vi.spyOn(console, "log").mockImplementation(() => {});
});

afterEach(() => {
  fs.rmSync(root, { recursive: true, force: true });
  vi.restoreAllMocks();
});

describe("ssg build flags", () => {
  it("--source/--templates/--out control directories", async () => {
    const out = path.join(root, "custom-out");
    await runCli(["build", "--source", path.join(root, "content"), "--templates", path.join(root, "tpl"), "--out", out]);
    expect(fs.existsSync(path.join(out, "a", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(out, "feed.xml"))).toBe(true);
  });

  it("excludes drafts by default, includes with --drafts", async () => {
    const out1 = path.join(root, "out1");
    await runCli(["build", "-s", path.join(root, "content"), "-t", path.join(root, "tpl"), "-o", out1]);
    expect(fs.existsSync(path.join(out1, "d", "index.html"))).toBe(false);

    const out2 = path.join(root, "out2");
    await runCli(["build", "-s", path.join(root, "content"), "-t", path.join(root, "tpl"), "-o", out2, "--drafts"]);
    expect(fs.existsSync(path.join(out2, "d", "index.html"))).toBe(true);
  });

  it("--base-url and --title feed into RSS output", async () => {
    const out = path.join(root, "out3");
    await runCli([
      "build", "-s", path.join(root, "content"), "-t", path.join(root, "tpl"), "-o", out,
      "--base-url", "https://blog.example", "--title", "My Blog",
    ]);
    const xml = fs.readFileSync(path.join(out, "feed.xml"), "utf8");
    expect(xml).toContain("<title>My Blog</title>");
    expect(xml).toContain("<link>https://blog.example/a/</link>");
  });

  it("rejects unknown flags", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(runCli(["build", "--bogus"])).rejects.toThrow();
  });

  it("prints a build summary", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const out = path.join(root, "out4");
    await runCli(["build", "-s", path.join(root, "content"), "-t", path.join(root, "tpl"), "-o", out]);
    expect(log.mock.calls.some(([msg]) => String(msg).includes("built"))).toBe(true);
  });
});
