import { run } from '../src/cli';

describe('CLI', () => {
  test('rejects commands other than build', async () => {
    await expect(run(['serve'])).rejects.toThrow('Usage: ssg build');
  });

  test('rejects options without values', async () => {
    await expect(run(['build', '--content'])).rejects.toThrow('Missing value for --content');
  });
});
