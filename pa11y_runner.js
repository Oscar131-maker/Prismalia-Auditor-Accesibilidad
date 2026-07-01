#!/usr/bin/env node
'use strict';

// Force UTF-8 on stdout/stderr so Windows doesn't use a legacy code page
if (process.stdout.setEncoding) process.stdout.setEncoding('utf8');
if (process.stderr.setEncoding) process.stderr.setEncoding('utf8');

// Redirect all console output to stderr so stdout stays clean for JSON
console.log = (...args) => process.stderr.write(args.join(' ') + '\n');
console.warn = (...args) => process.stderr.write(args.join(' ') + '\n');
console.error = (...args) => process.stderr.write(args.join(' ') + '\n');

const pa11y = require('pa11y');
const puppeteer = require('puppeteer');

async function enrichIssues(browser, url, issues) {
    if (!issues || !issues.length) return issues;
    let page;
    try {
        page = await browser.newPage();
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await new Promise(r => setTimeout(r, 800));

        const selectors = issues.map(i => i.selector || '');
        const enriched = await page.evaluate((sels) => {
            return sels.map(sel => {
                if (!sel) return { fullHtml: '', parentHtml: '', resources: [] };
                try {
                    const el = document.querySelector(sel);
                    if (!el) return { fullHtml: '', parentHtml: '', resources: [] };

                    const fullHtml = el.outerHTML;
                    const parentEl = el.parentElement;
                    let parentHtml = '';
                    if (parentEl && parentEl !== document.body && parentEl !== document.documentElement) {
                        const clone = parentEl.cloneNode(true);
                        // Limit parent HTML size: keep only the target child + truncate siblings
                        if (clone.innerHTML.length > 4000) {
                            // Just wrap target in parent tag with its attrs
                            const pTag = parentEl.tagName.toLowerCase();
                            let attrs = '';
                            for (const a of parentEl.attributes) {
                                attrs += ` ${a.name}="${a.value}"`;
                            }
                            parentHtml = `<${pTag}${attrs}>${el.outerHTML}</${pTag}>`;
                        } else {
                            parentHtml = clone.outerHTML;
                        }
                    }

                    const resources = [];
                    // Collect resource URLs from element and descendants
                    const collectUrls = (node) => {
                        if (node.tagName === 'IMG' || node.tagName === 'VIDEO' || node.tagName === 'AUDIO' || node.tagName === 'SOURCE') {
                            const src = node.src || node.getAttribute('src') || '';
                            if (src && !src.startsWith('data:')) resources.push({ type: node.tagName.toLowerCase(), url: src });
                            const poster = node.poster || node.getAttribute('poster') || '';
                            if (poster) resources.push({ type: 'poster', url: poster });
                        }
                        if (node.tagName === 'A') {
                            const href = node.href || '';
                            if (href && !href.startsWith('javascript:') && !href.startsWith('#')) resources.push({ type: 'link', url: href });
                        }
                        if (node.tagName === 'IFRAME') {
                            const src = node.src || '';
                            if (src) resources.push({ type: 'iframe', url: src });
                        }
                        // background-image
                        try {
                            const bg = getComputedStyle(node).backgroundImage;
                            if (bg && bg !== 'none') {
                                const m = bg.match(/url\(["']?([^)"']+)["']?\)/);
                                if (m && !m[1].startsWith('data:')) resources.push({ type: 'bg', url: m[1] });
                            }
                        } catch(e) {}
                        for (const child of node.children) collectUrls(child);
                    };
                    collectUrls(el);

                    // For text elements, also capture textContent for easy identification
                    let textContent = '';
                    const tag = el.tagName;
                    if (/^(H[1-6]|A|P|SPAN|DIV|BUTTON|LABEL|LI|TD|TH|FIGCAPTION|CAPTION|BLOCKQUOTE)$/.test(tag)) {
                        textContent = (el.textContent || '').trim().slice(0, 300);
                    }

                    return { fullHtml: fullHtml.slice(0, 5000), parentHtml: parentHtml.slice(0, 8000), resources, textContent };
                } catch(e) {
                    return { fullHtml: '', parentHtml: '', resources: [] };
                }
            });
        }, selectors);

        for (let i = 0; i < issues.length; i++) {
            const data = enriched[i] || {};
            if (data.fullHtml) issues[i].context = data.fullHtml;
            if (data.parentHtml) issues[i].parentContext = data.parentHtml;
            if (data.resources && data.resources.length) issues[i].resources = data.resources;
            if (data.textContent) issues[i].textContent = data.textContent;
        }
    } catch(e) {
        process.stderr.write('enrich error: ' + e.message + '\n');
    } finally {
        if (page) try { await page.close(); } catch(e) {}
    }
    return issues;
}

async function run() {
    const input = JSON.parse(process.argv[2]);
    const urls = input.urls || [];
    const standard = input.standard || 'WCAG2AA';
    const timeout = input.timeout || 30000;

    const results = [];

    // Launch a shared browser for enrichment
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    for (const url of urls) {
        try {
            const result = await pa11y(url, {
                standard,
                timeout,
                chromeLaunchConfig: {
                    args: ['--no-sandbox', '--disable-setuid-sandbox']
                },
                log: { debug: () => {}, error: () => {}, info: () => {} }
            });
            // Enrich issues with full HTML + parent + resources
            const enrichedIssues = await enrichIssues(browser, url, result.issues || []);
            results.push({ url, status: 'ok', issues: enrichedIssues, documentTitle: result.documentTitle || '' });
        } catch (err) {
            results.push({ url, status: 'error', error: err.message, issues: [] });
        }
    }

    await browser.close();
    process.stdout.write(JSON.stringify(results));
}

run().catch(err => {
    process.stderr.write(err.message);
    process.exit(1);
});
