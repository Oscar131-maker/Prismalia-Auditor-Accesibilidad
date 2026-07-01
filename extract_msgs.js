const fs = require('fs');
const path = require('path');

function walk(dir) {
    let files = [];
    try {
        for (const f of fs.readdirSync(dir)) {
            const full = path.join(dir, f);
            if (fs.statSync(full).isDirectory()) files = files.concat(walk(full));
            else if (f.endsWith('.js')) files.push(full);
        }
    } catch(e) {}
    return files;
}

const base = 'node_modules/html_codesniffer';
const files = walk(base);
const msgs = new Set();

for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    // Match string literals (single or double quoted) that are English sentences
    const re = /'((?:[^'\\]|\\.)*)'/g;
    const re2 = /"((?:[^"\\]|\\.)*)"/g;
    for (const regex of [re, re2]) {
        let m;
        while ((m = regex.exec(src)) !== null) {
            const s = m[1].replace(/\\n/g, ' ').replace(/\\t/g, ' ').replace(/\s+/g, ' ').trim();
            // Only sentences: starts uppercase, has spaces, >35 chars, ends with period/dot
            if (s.length > 35 && s.includes(' ') && /^[A-Z]/.test(s) && /\.$/.test(s)) {
                msgs.add(s);
            }
        }
    }
}

const sorted = [...msgs].sort();
sorted.forEach(m => console.log(m));
process.stderr.write('\nTotal: ' + sorted.length + ' mensajes\n');
