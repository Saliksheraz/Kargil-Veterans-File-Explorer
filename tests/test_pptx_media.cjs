// Run with Playwright on NODE_PATH and ffmpeg/python on PATH.
// Optionally set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to an installed Chromium.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const repo = path.resolve(__dirname, '..');
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'pptx-browser-'));
let browser;

async function main() {
    execFileSync(process.env.PYTHON || 'python', [path.join(__dirname, 'build_pptx_browser_fixture.py'), fixture], {cwd: repo, stdio: 'inherit'});
    browser = await chromium.launch({headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
        args: ['--enable-unsafe-swiftshader']});
    for (const surface of ['document', 'modal']) {
        for (const fallback of [false, true]) {
            const page = await browser.newPage({viewport: {width: 1400, height: 1000}});
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.route('**/*', async route => {
                const url = new URL(route.request().url());
                let file;
                if (url.pathname === '/pptx-to-pdf/') {
                    return fallback ? route.fulfill({status: 500, json: {error: 'Browser fallback test'}}) :
                        route.fulfill({json: JSON.parse(fs.readFileSync(path.join(fixture, 'response.json')))});
                }
                if (url.pathname.startsWith('/static/')) file = path.join(repo, url.pathname);
                else if (url.pathname.startsWith('/media/')) file = path.join(fixture, url.pathname.slice(7));
                else file = path.join(fixture, surface === 'modal' ? 'index.html' : 'doc.html');
                if (!fs.existsSync(file)) return route.fulfill({status: 404});
                return route.fulfill({path: file});
            });
            await page.goto('http://pptx.test/');
            if (surface === 'modal') await page.evaluate(() => openFilePreviewModal('/media/fixture.pptx', 'fixture.pptx', 'test'));
            const wrapper = page.locator('.video360-embedded');
            await wrapper.waitFor();
            await page.waitForFunction(() => document.querySelector('.video360-embedded video')?.readyState >= 2);
            assert.equal(await wrapper.count(), 1, 'duplicate relationships must produce one player');
            await page.waitForFunction(() => document.querySelector('.video360-embedded .btn-mode-360').classList.contains('active'));
            const host = page.locator('.pptx-media-host').first();
            await host.evaluate(el => window.oldPlayer = el.pptxPlayer);
            const canvas = wrapper.locator('.video360-canvas-container canvas');
            const before = await canvas.screenshot();
            const rect = await canvas.boundingBox();
            await page.mouse.move(rect.x + rect.width * 0.6, rect.y + rect.height * 0.35);
            await page.mouse.down();
            await page.mouse.move(rect.x + rect.width * 0.3, rect.y + rect.height * 0.55, {steps: 12});
            await page.mouse.up();
            await page.waitForFunction(() => document.querySelector('.video360-embedded .compass-text').textContent !== '0° N');
            assert.notDeepEqual(await canvas.screenshot(), before, 'dragging must change the projected video');
            await page.mouse.wheel(0, -200);
            await wrapper.locator('.btn-reset-view').click();
            await page.waitForFunction(() => document.querySelector('.video360-embedded .compass-text').textContent === '0° N');
            const counter = fallback ? '.pptx-counter' : '.pdf-page-input';
            const readCounter = () => page.locator(counter).evaluate(el => el.value || el.textContent);
            const slide = await readCounter();
            await wrapper.focus();
            await page.keyboard.press('ArrowRight');
            await page.keyboard.press('Space');
            assert.equal(await readCounter(), slide, 'player keyboard controls must not advance slides');
            await page.waitForFunction(() => !document.querySelector('.video360-embedded video').paused);
            await wrapper.locator('.btn-mode-flat').click();
            await wrapper.locator('video').evaluate(video => video.dispatchEvent(new Event('loadedmetadata')));
            assert(await wrapper.locator('.btn-mode-flat').evaluate(el => el.classList.contains('active')), 'manual mode selection overrides auto-detection');
            await wrapper.locator('.btn-mode-360').click();
            await wrapper.locator('.btn-fullscreen').click();
            await page.waitForFunction(() => document.fullscreenElement?.classList.contains('video360-wrapper'));
            await page.evaluate(() => document.exitFullscreen());
            await page.locator(fallback ? '.pptx-next-btn' : '.pdf-next-page').click();
            await page.waitForFunction(() => document.querySelector('.video360-embedded video')?.videoWidth === 320 && document.querySelector('.video360-embedded video')?.videoHeight === 180);
            assert.equal(await wrapper.count(), 1);
            assert(await wrapper.locator('.btn-mode-flat').evaluate(el => el.classList.contains('active')), 'ordinary video starts in flat mode');
            assert(await page.evaluate(() => oldPlayer.video.paused && !oldPlayer.video.hasAttribute('src')), 'departed slide releases its video');
            await wrapper.locator('.btn-mode-360').click();
            await wrapper.locator('.video360-canvas-container canvas').waitFor();
            await page.locator(fallback ? '.pptx-prev-btn' : '.pdf-prev-page').click();
            await page.waitForFunction(() => document.querySelector('.video360-embedded video')?.videoHeight === 160);
            assert.equal(await wrapper.count(), 1, 'cached slides recreate players');
            if (surface === 'modal') {
                await page.evaluate(() => $('#filePreviewModal').modal('hide'));
                await page.waitForFunction(() => !document.querySelector('.video360-embedded'));
                assert.equal(await page.evaluate(() => document.getElementById('filePreviewContent').pptxBlobUrls.length), 0);
            }
            assert.deepEqual(errors, [], 'browser must have no JavaScript errors');
            console.log(`PASS ${surface}: ${fallback ? 'PPTX browser fallback' : 'PDF slide overlays'} — drag, keyboard, playback, modes, fullscreen, navigation, cleanup`);
            await page.close();
        }
    }

    const standalone = await browser.newPage();
    await standalone.route('**/*', route => {
        const url = new URL(route.request().url());
        const file = url.pathname.startsWith('/static/') ? path.join(repo, url.pathname) :
            url.pathname.startsWith('/media/') ? path.join(fixture, url.pathname.slice(7)) : path.join(fixture, 'video.html');
        return route.fulfill({path: file});
    });
    await standalone.goto('http://pptx.test/');
    await standalone.locator('#docViewerVideoContainer .video360-canvas-container canvas').waitFor();
    await standalone.waitForFunction(() => document.querySelector('#docViewerVideoContainer video')?.readyState >= 2);
    assert(await standalone.locator('.btn-mode-360').evaluate(el => el.classList.contains('active')));
    await standalone.locator('.btn-mode-flat').click();
    await standalone.locator('.btn-mode-360').click();
    console.log('PASS standalone 360 video: decoded playback and mode switching');
    await standalone.close();
}

main().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
    if (browser) await browser.close();
    assert.equal(path.dirname(path.resolve(fixture)), path.resolve(os.tmpdir()));
    fs.rmSync(fixture, {recursive: true, force: true});
});
