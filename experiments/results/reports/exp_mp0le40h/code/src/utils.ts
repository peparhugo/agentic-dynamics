import {
  existsSync,
  mkdirSync,
  readdirSync,
  writeFileSync,
  copyFileSync,
  statSync,
} from 'fs';
import { join, dirname, extname } from 'path';

export function ensureDir(dir: string): void {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

export function writeFile(path: string, content: string): void {
  ensureDir(dirname(path));
  writeFileSync(path, content, 'utf-8');
}

export function copyStaticFiles(sourceDir: string, outputDir: string): void {
  if (!existsSync(sourceDir)) return;

  function walk(src: string, dest: string) {
    ensureDir(dest);
    for (const entry of readdirSync(src)) {
      if (entry.startsWith('_')) continue;

      const srcPath = join(src, entry);
      const destPath = join(dest, entry);
      const st = statSync(srcPath);

      if (st.isDirectory()) {
        walk(srcPath, destPath);
      } else if (extname(entry) !== '.md') {
        copyFileSync(srcPath, destPath);
      }
    }
  }

  walk(sourceDir, outputDir);
}
