import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { loadConfig } from './config';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('loadConfig', () => {
  it('loads the built-in markdown and template plugins from the project ssg.config.ts by default', () => {
    const { plugins } = loadConfig();
    expect(plugins.map((p) => p.name)).toEqual(['markdown', 'template']);
  });

  it('falls back to the built-in plugins when the config path does not resolve to a file', () => {
    const { plugins } = loadConfig(path.join(os.tmpdir(), 'definitely-not-a-real-ssg-config'));
    expect(plugins.map((p) => p.name)).toEqual(['markdown', 'template']);
  });

  it('loads a custom plugin list from a user-supplied config path', () => {
    const dir = makeTmpDir('ssg-config-');
    const configPath = path.join(dir, 'custom.config.ts');
    fs.writeFileSync(
      configPath,
      "export default { plugins: [{ name: 'custom-plugin' }] };\n"
    );

    try {
      const { plugins } = loadConfig(configPath);
      expect(plugins.map((p) => p.name)).toEqual(['custom-plugin']);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});
