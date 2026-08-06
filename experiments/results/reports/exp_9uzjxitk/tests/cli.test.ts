import { describe, it, expect, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.join(__dirname, 'fixtures');
const testOutput = path.join(__dirname, '..', 'test-output');
const projectRoot = path.join(__dirname, '..');
const cliPath = path.join(projectRoot, 'dist', 'cli.js');

function cleanOutput() {
  if (fs.existsSync(testOutput)) {
    fs.rmSync(testOutput, { recursive: true, force: true });
  }
}

afterEach(cleanOutput);

describe('CLI build command', () => {
  it('generates index.html', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    expect(fs.existsSync(path.join(testOutput, 'index.html'))).toBe(true);
  });

  it('generates post pages', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    expect(fs.existsSync(path.join(testOutput, 'post1.html'))).toBe(true);
    expect(fs.existsSync(path.join(testOutput, 'post3.html'))).toBe(true);
  });

  it('excludes draft posts from output', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    expect(fs.existsSync(path.join(testOutput, 'post2.html'))).toBe(false);
  });

  it('generates tag index pages', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    expect(fs.existsSync(path.join(testOutput, 'tags', 'javascript', 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(testOutput, 'tags', 'typescript', 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(testOutput, 'tags', 'tutorial', 'index.html'))).toBe(true);
  });

  it('generates RSS feed', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    expect(fs.existsSync(path.join(testOutput, 'rss.xml'))).toBe(true);
    const rss = fs.readFileSync(path.join(testOutput, 'rss.xml'), 'utf-8');
    expect(rss).toContain('Hello World');
    expect(rss).not.toContain('Second Post'); // draft excluded
  });

  it('accepts custom base-url flag', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url https://mysite.com --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    const index = fs.readFileSync(path.join(testOutput, 'index.html'), 'utf-8');
    expect(index).toContain('https://mysite.com');
    const rss = fs.readFileSync(path.join(testOutput, 'rss.xml'), 'utf-8');
    expect(rss).toContain('https://mysite.com');
  });

  it('accepts --site-title flag', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "My Custom Site"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    const index = fs.readFileSync(path.join(testOutput, 'index.html'), 'utf-8');
    expect(index).toContain('My Custom Site');
  });

  it('accepts --site-description flag', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test" --site-description "Custom description"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    const rss = fs.readFileSync(path.join(testOutput, 'rss.xml'), 'utf-8');
    expect(rss).toContain('Custom description');
  });

  it('uses default values when flags omitted', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput}`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    expect(fs.existsSync(path.join(testOutput, 'index.html'))).toBe(true);
  });

  it('includes syntax-highlighted code blocks in output', () => {
    execSync(
      `node ${cliPath} build --src ${path.join(fixtures, 'posts')} --templates ${path.join(fixtures, 'templates')} --output ${testOutput} --base-url http://localhost:8080 --site-title "Test Blog"`,
      { cwd: projectRoot, stdio: 'pipe' },
    );
    const post1 = fs.readFileSync(path.join(testOutput, 'post1.html'), 'utf-8');
    expect(post1).toContain('class="hljs');
    expect(post1).toContain('language-javascript');
  });
});

describe('CLI serve command', () => {
  it('supports --port flag in help', () => {
    const result = execSync(`node ${cliPath} serve --help`, { cwd: projectRoot, stdio: 'pipe' });
    expect(result.toString()).toContain('--port');
  });

  it('shows help without command', () => {
    try {
      execSync(`node ${cliPath}`, { cwd: projectRoot, stdio: 'pipe' });
    } catch (e: any) {
      expect(e.stderr.toString()).toContain('You need');
    }
  });
});
