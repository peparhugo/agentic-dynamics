import { SsgEngine } from './engine';

export function build(contentDir: string, outputDir: string, templatesDir?: string): void {
  const engine = new SsgEngine();
  engine.build(contentDir, outputDir, templatesDir);
}
