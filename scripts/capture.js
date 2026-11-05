#!/usr/bin/env node
/**
 * Deterministic final screenshots of the standalone viewer using headless
 * Chrome + ANGLE/Metal. Renders at 2x device scale for sharp 2560px output.
 *
 * Usage: node scripts/capture.js [all|scenes|ui|detail|mobile]
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import puppeteer from 'puppeteer-core';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const renders = path.join(root, 'renders');
fs.mkdirSync(renders, { recursive: true });
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const html = 'file://' + path.join(root, '7-eleven-store-3d.html');
const preset = process.argv[2] || 'all';

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  protocolTimeout: 240000,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--allow-file-access-from-files',
    '--enable-webgl',
    '--ignore-gpu-blocklist',
    '--enable-unsafe-swiftshader',
    '--use-angle=metal',
    '--hide-scrollbars',
    '--force-color-profile=srgb',
  ],
});

async function makePage({ cssWidth, cssHeight, dpr = 2, query = '', wait = 1500, mobile = false }) {
  const page = await browser.newPage();
  await page.setViewport({
    width: cssWidth, height: cssHeight, deviceScaleFactor: dpr,
    isMobile: mobile, hasTouch: mobile,
  });
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('[console:error]', msg.text());
  });
  await page.goto(`${html}?${query}`, { waitUntil: 'load', timeout: 120000 });
  await page.waitForFunction('window.__SEVEN_READY__ === true', { timeout: 120000 });
  await new Promise((r) => setTimeout(r, wait));
  return page;
}

async function shoot(page, name, width, height) {
  const out = path.join(renders, name);
  await page.screenshot({ path: out, type: 'png', captureBeyondViewport: false });
  console.log('wrote', name, `${width}x${height}`);
}

async function sceneShot(mode, name) {
  const page = await makePage({
    cssWidth: 1280, cssHeight: 720, dpr: 2,
    query: `capture=1&ui=0&intro=0&auto=0&mode=${mode}&dpr=2`,
    wait: 1800,
  });
  await page.evaluate(() => window.__SEVEN__.freeze());
  console.log('stats', mode, await page.evaluate(() => window.__SEVEN__.stats()));
  await shoot(page, name, 2560, 1440);
  await page.close();
}

async function duskShot() {
  const page = await makePage({
    cssWidth: 1280, cssHeight: 720, dpr: 2,
    query: 'capture=1&ui=0&intro=0&auto=0&mode=night&dpr=2',
    wait: 1500,
  });
  await page.evaluate(() => {
    window.__SEVEN__.freeze();
    window.__SEVEN__.setTime(0.5);
  });
  await new Promise((r) => setTimeout(r, 1300));
  await shoot(page, 'seven-eleven-dusk.png', 2560, 1440);
  await page.close();
}

async function interiorShot() {
  const page = await makePage({
    cssWidth: 1280, cssHeight: 720, dpr: 2,
    query: 'ui=0&intro=0&auto=0&mode=night&dpr=2',
    wait: 1500,
  });
  await page.evaluate(() => window.__SEVEN__.enterStore());
  await new Promise((r) => setTimeout(r, 2800));
  await page.evaluate(() => document.body.classList.add('capture'));
  await new Promise((r) => setTimeout(r, 200));
  await shoot(page, 'seven-eleven-interior.png', 2560, 1440);
  await page.close();
}

async function uiShot() {
  const page = await makePage({
    cssWidth: 1280, cssHeight: 800, dpr: 2,
    query: 'intro=0&auto=0&mode=night&dpr=2',
    wait: 2300,
  });
  await shoot(page, 'seven-eleven-viewer.png', 2560, 1600);
  await page.close();
}

async function detailShot() {
  const page = await makePage({
    cssWidth: 800, cssHeight: 600, dpr: 2,
    query: 'capture=1&ui=0&intro=0&auto=0&mode=night&dpr=2',
    wait: 1400,
  });
  await page.evaluate(() => {
    const s = window.__SEVEN__;
    s.freeze();
    s.setView([0, 3.1, 10.5], [0.8, 2.0, 4.8], 46);
  });
  await new Promise((r) => setTimeout(r, 800));
  await shoot(page, 'seven-eleven-detail.png', 1600, 1200);
  await page.evaluate(() => {
    const s = window.__SEVEN__;
    s.setView([-2.3, 2.3, 8.2], [-3.6, 1.4, 2.7], 48);
  });
  await new Promise((r) => setTimeout(r, 600));
  await shoot(page, 'seven-eleven-detail-slurpee.png', 1600, 1200);
  await page.evaluate(() => {
    const s = window.__SEVEN__;
    s.setView([-7.8, 2.2, 12.5], [-3.5, 1.15, 6.0], 50);
  });
  await new Promise((r) => setTimeout(r, 600));
  await shoot(page, 'seven-eleven-detail-street.png', 1600, 1200);
  await page.evaluate(() => {
    const s = window.__SEVEN__;
    s.setView([-2.4, 1.9, 8.2], [-1.1, 1.85, 4.8], 30);
  });
  await new Promise((r) => setTimeout(r, 500));
  await shoot(page, 'seven-eleven-detail-payment.png', 1600, 1200);
  await page.close();
}

async function mobileShot() {
  const page = await makePage({
    cssWidth: 390, cssHeight: 844, dpr: 2, mobile: true,
    query: 'intro=0&auto=0&mode=night&dpr=2',
    wait: 2100,
  });
  await shoot(page, 'seven-eleven-mobile.png', 780, 1688);
  await page.close();
}

try {
  if (preset === 'all' || preset === 'scenes') {
    await sceneShot('night', 'seven-eleven-night-hero.png');
    await sceneShot('day', 'seven-eleven-day-hero.png');
    await duskShot();
    await interiorShot();
  }
  if (preset === 'all' || preset === 'ui') await uiShot();
  if (preset === 'all' || preset === 'detail') await detailShot();
  if (preset === 'all' || preset === 'mobile') await mobileShot();
} finally {
  await browser.close();
}
