import { describe, it, expect, beforeEach, afterEach } from "vitest";
import path from "path";
import fs from "fs";
import os from "os";
import { execSync } from "child_process";

const cliPath = path.join(__dirname, "..", "dist", "index.js");

function runCLI(args: string): string {
  try {
    return execSync(`node ${cliPath} ${args}`, {
      encoding: "utf-8",
      env: { ...process.env },
      timeout: 15000,
    });
  } catch (err: unknown) {
    const e = err as { stdout?: string; stderr?: string; status?: number };
    return (e.stdout || "") + (e.stderr || "");
  }
}

describe("CLI", () => {
  let outputDir: string;
  let sourceDir: string;
  let templateDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-cli-"));
    sourceDir = path.join(__dirname, "fixtures", "source");
    templateDir = path.join(__dirname, "fixtures", "templates");
  });

  afterEach(() => {
    if (fs.existsSync(outputDir)) {
      fs.rmSync(outputDir, { recursive: true });
    }
  });

  it("builds a site from source and template directories", () => {
    const result = runCLI(
      `--source "${sourceDir}" --template "${templateDir}" --output "${outputDir}"`
    );
    expect(fs.existsSync(path.join(outputDir, "posts", "hello-world", "index.html"))).toBe(
      true
    );
  });

  it("requires --source flag", () => {
    const result = runCLI(
      `--template "${templateDir}" --output "${outputDir}"`
    );
    expect(result).toContain("required option");
  });

  it("requires --template flag", () => {
    const result = runCLI(
      `--source "${sourceDir}" --output "${outputDir}"`
    );
    expect(result).toContain("required option");
  });

  it("requires --output flag", () => {
    const result = runCLI(
      `--source "${sourceDir}" --template "${templateDir}"`
    );
    expect(result).toContain("required option");
  });

  it("generates RSS feed", () => {
    runCLI(
      `--source "${sourceDir}" --template "${templateDir}" --output "${outputDir}"`
    );
    expect(fs.existsSync(path.join(outputDir, "feed.xml"))).toBe(true);
  });

  it("generates tag indexes", () => {
    runCLI(
      `--source "${sourceDir}" --template "${templateDir}" --output "${outputDir}"`
    );
    expect(
      fs.existsSync(path.join(outputDir, "tags", "javascript", "index.html"))
    ).toBe(true);
  });

  it("excludes draft posts from output", () => {
    runCLI(
      `--source "${sourceDir}" --template "${templateDir}" --output "${outputDir}"`
    );
    expect(
      fs.existsSync(path.join(outputDir, "posts", "draft-post", "index.html"))
    ).toBe(false);
  });

  it("exits with error for missing source directory", () => {
    const result = runCLI(
      `--source "/nonexistent/path" --template "${templateDir}" --output "${outputDir}"`
    );
    expect(result).toContain("not found");
  });
});
