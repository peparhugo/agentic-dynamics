import type { Plugin, SsgContext } from '../src/plugin';
import type { Page } from '../src/types';

export class ExamplePlugin implements Plugin {
  readonly name = 'example';

  onStart(_context: SsgContext): void {
    // Runs once before the build pipeline starts.
  }

  beforeBuild(_context: SsgContext): void {
    // Runs after onStart, before any pages are processed.
  }

  onFile(_page: Page, _context: SsgContext): void {
    // Runs for every collected page, in plugin order.
  }

  afterBuild(_context: SsgContext): void {
    // Runs after every page has been processed.
  }

  onEnd(_context: SsgContext): void {
    // Runs last, once the build finishes.
  }
}
