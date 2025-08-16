const fs = require('fs');
const { execSync, execFileSync } = require('child_process');
const path = require('path');

if (process.argv.length < 3) {
  console.error('Usage: node vitest-bisect.js <test-file-path>');
  process.exit(2);
}

const testPath = process.argv[2];
const abs = path.resolve(testPath);
const content = fs.readFileSync(abs, 'utf8');
const lines = content.split('\n');

const dir = path.dirname(abs);
const tempName = path.join(dir, '__bisect_temp.test.js');

function runTemp(linesToWrite) {
  fs.writeFileSync(tempName, linesToWrite.join('\n'));
  try {
    // run vitest for this single file
    execFileSync(
      'npm',
      [
        '--prefix', 'frontend',
        'test',
        '--silent',
        '--',
        '--run', path.relative(process.cwd(), tempName),
        '--reporter', 'verbose'
      ],
      { stdio: 'pipe', timeout: 20000 }
    );
    return { ok: true };
  } catch (e) {
    return { ok: false, out: e.stdout ? e.stdout.toString() : '', err: e.stderr ? e.stderr.toString() : e.toString() };
  }
}

let low = 0, high = lines.length;
let lastFail = null;

// First ensure the whole file fails (to validate bisect)
fs.writeFileSync(tempName, content);
let full = runTemp(lines);
if (full.ok) {
  console.error('Full file did not fail; aborting bisect.');
  process.exit(3);
}

while (low < high - 1) {
  const mid = Math.floor((low + high) / 2);
  const chunk = lines.slice(0, mid);
  const res = runTemp(chunk);
  console.error(`Tried lines 0..${mid} => ok=${res.ok}`);
  if (!res.ok) {
    // failure present in first half
    high = mid;
    lastFail = mid;
  } else {
    // first half ok, failure in second half
    low = mid;
  }
}

console.error('Bisect finished. Candidate line:', high);
console.error('Context around line:');
const start = Math.max(0, high - 5);
const end = Math.min(lines.length, high + 5);
console.error(lines.slice(start, end).map((l,i)=>`${start + i + 1}: ${l}`).join('\n'));

// cleanup
try { fs.unlinkSync(tempName); } catch(e){}

process.exit(0);
