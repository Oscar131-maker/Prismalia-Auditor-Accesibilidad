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

const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

async function enrichIssuesOnPage(page, issues) {
    if (!issues || !issues.length) return issues;
    try {
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
    }
    return issues;
}

const fs = require('fs');
const path = require('path');

const browserArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--no-first-run',
    '--disable-extensions',
    '--disable-blink-features=AutomationControlled'
];

function getChromiumPath() {
    if (process.env.PUPPETEER_EXECUTABLE_PATH && fs.existsSync(process.env.PUPPETEER_EXECUTABLE_PATH)) {
        return process.env.PUPPETEER_EXECUTABLE_PATH;
    }
    const candidates = [
        path.join(process.env.LOCALAPPDATA || '', 'ms-playwright', 'chromium-1200', 'chrome-win64', 'chrome.exe'),
        '/root/.cache/ms-playwright/chromium-1200/chrome-linux/chrome',
        '/home/pwuser/.cache/ms-playwright/chromium-1200/chrome-linux/chrome',
        '/ms-playwright/chromium-1200/chrome-linux/chrome'
    ];
    for (const c of candidates) {
        if (c && fs.existsSync(c)) return c;
    }
    return undefined;
}

async function launchBrowser() {
    const launchOptions = {
        headless: true,
        args: browserArgs
    };
    const execPath = getChromiumPath();
    if (execPath) {
        launchOptions.executablePath = execPath;
    }
    return puppeteer.launch(launchOptions);
}

async function navigateAndBypassChallenge(page, url, timeout = 30000) {
    try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
    } catch(e) {
        // Redirections might interrupt initial navigation, handled below
    }

    // Wait for SiteGround Robot Challenge Screen (PoW captcha) only if currently on challenge
    const start = Date.now();
    while (Date.now() - start < 8000) {
        try {
            const curUrl = page.url() || '';
            const title = (await page.title()) || '';
            const isChallengeScreen = curUrl.includes('sgcaptcha') ||
                                      curUrl.includes('challenge') ||
                                      title.toLowerCase().includes('challenge') ||
                                      title.toLowerCase().includes('robot');
            if (!isChallengeScreen) {
                break;
            }
            await new Promise(r => setTimeout(r, 600));
        } catch(e) {
            // Execution context destroyed during redirect
            await new Promise(r => setTimeout(r, 600));
        }
    }
}

async function run() {
    const input = JSON.parse(process.argv[2]);
    const urls = input.urls || [];
    const standard = input.standard || 'WCAG2AA';
    const timeout = input.timeout || 30000;
    const results = [];
    let browser;

    try {
        browser = await launchBrowser();
        for (const url of urls) {
            let page;
            try {
                if (!browser.connected) {
                    browser = await launchBrowser();
                }
                page = await browser.newPage();
                await navigateAndBypassChallenge(page, url, timeout);

                let docTitle = '';
                try {
                    docTitle = (await page.title()) || '';
                } catch(e) {}

                const result = await pa11y(url, {
                    standard,
                    timeout,
                    browser,
                    page,
                    ignoreUrl: true,
                    log: { debug: () => {}, error: () => {}, info: () => {} }
                });

                const enrichedIssues = await enrichIssuesOnPage(page, result.issues || []);
                results.push({
                    url,
                    status: 'ok',
                    issues: enrichedIssues,
                    documentTitle: result.documentTitle || docTitle
                });
            } catch (err) {
                results.push({ url, status: 'error', error: err.message, issues: [] });
            } finally {
                if (page) {
                    try { await page.close(); } catch(e) {}
                }
            }
        }
    } finally {
        if (browser) {
            try {
                await browser.close();
            } catch (err) {}
        }
    }

    process.stdout.write(JSON.stringify(results));
}

run().catch(err => {
    process.stderr.write(err.message);
    process.exit(1);
});
