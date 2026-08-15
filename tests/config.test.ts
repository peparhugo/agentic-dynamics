import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { loadConfig } from '../src/config';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('loadConfig', () => {
  let dir: string;

  beforeEach(() => {
    dir = makeTempDir('ssg-config-');
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('returns an empty config when the file does not exist', () => {
    expect(loadConfig(path.join(dir, 'ssg.config.ts'))).toEqual({});
  });

  it('loads a default-exported config object from a TypeScript file', () => {
    const configPath = path.join(dir, 'ssg.config.ts');
    fs.writeFileSync(
      configPath,
      `
      const plugins = [{ name: 'noop' }];
      export default { plugins };
      `
    );

    const config = loadConfig(configPath);
    expect(config.plugins).toHaveLength(1);
    expect(config.plugins?.[0].name).toBe('noop');
  });

  it('loads a CommonJS module.exports config', () => {
    const configPath = path.join(dir, 'ssg.config.js');
    fs.writeFileSync(
      configPath,
      `module.exports = { plugins: [{ name: 'commonjs-plugin' }] };`
    );

    const config = loadConfig(configPath);
    expect(config.plugins?.[0].name).toBe('commonjs-plugin');
  });
});
