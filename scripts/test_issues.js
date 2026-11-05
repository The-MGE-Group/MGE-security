// Runs scripts/issues.js against a fake GitHub to check it opens, skips and closes the right issues.
// Run: node scripts/test_issues.js
const fs = require('fs'), os = require('os'), path = require('path'), assert = require('assert');
const code = fs.readFileSync(path.join(__dirname, 'issues.js'), 'utf8');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function fakeGitHub(existing) {
  const log = { created: [], closed: [], comments: [], labels: [] };
  const issues = existing.map((b, i) => ({ number: i + 1, state: b.state, body: b.body }));
  const rest = { issues: {
    getLabel: async () => { if (!log.labelMade) throw new Error('404'); },
    createLabel: async (a) => { log.labelMade = true; log.labels.push(a.name); },
    listForRepo: 'list',
    create: async (a) => log.created.push(a),
    createComment: async (a) => log.comments.push(a.issue_number),
    update: async (a) => log.closed.push(a.issue_number),
  } };
  return { log, github: { rest, paginate: async () => issues } };
}

async function run(findings, tools, existing, canClose) {
  const file = path.join(os.tmpdir(), `findings-${Math.random()}.json`);
  fs.writeFileSync(file, JSON.stringify({ findings, tools }));
  process.env.FINDINGS = file; process.env.SOURCE = 'weekly'; process.env.CAN_CLOSE = canClose ? 'true' : 'false';
  const { log, github } = fakeGitHub(existing);
  const context = { repo: { owner: 'o', repo: 'r' }, serverUrl: 'https://github.com', runId: 1 };
  const core = { info() {}, warning() {} };
  await new AsyncFunction('require', 'github', 'context', 'core', code)(require, github, context, core);
  return log;
}
const mark = (id, tool, source = 'weekly') => `x\n<!-- mge-security-id: ${id} source: ${source} tool: ${tool} -->`;
const f = (id, tool, blocks = true) => ({ id, tool, blocks, severity: 'high', title: 't', where: 'w', proof: 'p', fix: 'f' });

(async () => {
  // New blocking finding -> one issue; non-blocking -> none; already filed (even closed) -> none.
  let log = await run([f('new1', 'zap'), f('low1', 'zap', false), f('old1', 'zap')], { zap: 'ok' },
                      [{ state: 'closed', body: mark('old1', 'zap') }], true);
  assert.deepStrictEqual(log.created.map(c => c.body.match(/id: (\w+)/)[1]), ['new1']);
  assert.deepStrictEqual(log.labels, ['mge-security']);
  // Fixed finding with its tool ok -> closed with a comment.
  log = await run([], { zap: 'ok', nuclei: 'skipped (x)' },
                  [{ state: 'open', body: mark('gone', 'zap') }, { state: 'open', body: mark('maybe', 'nuclei') },
                   { state: 'open', body: mark('other', 'zap', 'pr-scan') }], true);
  assert.deepStrictEqual(log.closed, [1], 'only the zap issue closes; skipped tool and other source stay open');
  assert.deepStrictEqual(log.comments, [1]);
  // Closing turned off -> nothing closes.
  log = await run([], { zap: 'ok' }, [{ state: 'open', body: mark('gone', 'zap') }], false);
  assert.deepStrictEqual(log.closed, []);
  console.log('issues.js checks passed');
})().catch(e => { console.error(e); process.exit(1); });
