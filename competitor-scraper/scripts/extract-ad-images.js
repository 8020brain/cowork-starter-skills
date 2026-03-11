#!/usr/bin/env node

/**
 * Extract Ad Image URLs from Google Ads Transparency Pages
 *
 * Visits transparency URLs and extracts the actual ad image URLs.
 * Google renders ads as server-side images, not DOM text, so this
 * step is needed before content extraction.
 *
 * Usage:
 *   node extract-ad-images.js \
 *     --input=output/.temp/transparency_urls/chase.com.csv \
 *     --output=output/.temp/ad-images/chase.com.csv
 *
 * Or process all CSVs in a directory:
 *   node extract-ad-images.js \
 *     --input-dir=output/.temp/transparency_urls \
 *     --output=output/.temp/ad-images/all.csv
 */

import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'fs';
import { dirname, resolve, basename } from 'path';
import { fileURLToPath } from 'url';
import puppeteer from 'puppeteer';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) {
            acc[key] = value;
        }
    } else if (arg.startsWith('--')) {
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

const inputFile = args['input'];
const inputDir = args['input-dir'];
const outputPath = args['output'];
const delayMs = parseInt(args['delay']) || 2000;
const limit = parseInt(args['limit']) || 0;

// Validate required arguments
if ((!inputFile && !inputDir) || !outputPath) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  node extract-ad-images.js \\');
    console.error('    --input=output/.temp/transparency_urls/chase.com.csv \\');
    console.error('    --output=output/.temp/ad-images/chase.com.csv');
    console.error('');
    console.error('Or:');
    console.error('  node extract-ad-images.js \\');
    console.error('    --input-dir=output/.temp/transparency_urls \\');
    console.error('    --output=output/.temp/ad-images/all.csv');
    console.error('');
    console.error('Options:');
    console.error('  --delay=2000    Delay between requests in ms (default: 2000)');
    console.error('  --limit=10      Limit number of ads to process (default: all)');
    process.exit(1);
}

// Parse CSV file
function parseCSV(content) {
    const lines = content.trim().split('\n');
    if (lines.length < 2) return [];

    const headers = parseCSVLine(lines[0]);
    const rows = [];

    for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i]);
        const row = {};
        headers.forEach((header, idx) => {
            row[header] = values[idx] || '';
        });
        rows.push(row);
    }

    return rows;
}

// Parse a single CSV line (handles quoted fields)
function parseCSVLine(line) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        const nextChar = line[i + 1];

        if (inQuotes) {
            if (char === '"' && nextChar === '"') {
                current += '"';
                i++;
            } else if (char === '"') {
                inQuotes = false;
            } else {
                current += char;
            }
        } else {
            if (char === '"') {
                inQuotes = true;
            } else if (char === ',') {
                values.push(current);
                current = '';
            } else {
                current += char;
            }
        }
    }
    values.push(current);

    return values;
}

// Get all CSV files from a directory
function getCSVFiles(dir) {
    const files = readdirSync(dir);
    return files
        .filter(f => f.endsWith('.csv') && !f.includes('ad-images') && !f.includes('enriched'))
        .map(f => resolve(dir, f));
}

// Load ads from input files
function loadAds() {
    let allAds = [];

    if (inputFile) {
        const content = readFileSync(resolve(process.cwd(), inputFile), 'utf8');
        const ads = parseCSV(content);
        allAds = allAds.concat(ads);
    } else if (inputDir) {
        const csvFiles = getCSVFiles(resolve(process.cwd(), inputDir));
        for (const file of csvFiles) {
            console.error(`Loading ${basename(file)}...`);
            const content = readFileSync(file, 'utf8');
            const ads = parseCSV(content);
            allAds = allAds.concat(ads);
        }
    }

    return allAds;
}

// Extract transparency URL from ad data
function getTransparencyUrl(ad) {
    return ad.transparency_url || ad.url || ad.preview_url || '';
}

// Sleep helper
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Extract ad image URL from transparency page
async function extractImageUrl(page, transparencyUrl) {
    try {
        await page.goto(transparencyUrl, {
            waitUntil: 'networkidle2',
            timeout: 30000
        });

        // Wait for the ad image to load
        await sleep(2000);

        // Try to find the ad image - Google renders ads as images
        const imageUrl = await page.evaluate(() => {
            const selectors = [
                'img[src*="tpc.googlesyndication.com"]',
                'img[src*="simgad"]',
                '.creative-preview img',
                '[data-creative-preview] img',
                'img[alt*="Ad"]',
                'img[alt*="creative"]'
            ];

            for (const selector of selectors) {
                const img = document.querySelector(selector);
                if (img && img.src) {
                    return img.src;
                }
            }

            // Fallback: find any large image that looks like an ad
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.naturalWidth > 200 && img.src &&
                    (img.src.includes('googlesyndication') || img.src.includes('simgad'))) {
                    return img.src;
                }
            }

            return null;
        });

        return imageUrl;
    } catch (error) {
        console.error(`  Error extracting from ${transparencyUrl}: ${error.message}`);
        return null;
    }
}

// Convert results to CSV
function toCSV(results) {
    if (results.length === 0) {
        return 'domain,creative_id,advertiser_name,transparency_url,image_url,format,first_shown,last_shown\n';
    }

    const headers = Object.keys(results[0]);
    const rows = [headers.join(',')];

    for (const result of results) {
        const values = headers.map(header => {
            let value = result[header];
            if (value !== null && value !== undefined) {
                value = String(value);
                if (value.includes(',') || value.includes('"') || value.includes('\n')) {
                    value = `"${value.replace(/"/g, '""')}"`;
                }
            } else {
                value = '';
            }
            return value;
        });
        rows.push(values.join(','));
    }

    return rows.join('\n');
}

// Main execution
async function main() {
    try {
        // Load ads from input files
        console.error('Loading ads from input files...');
        let ads = loadAds();

        if (ads.length === 0) {
            console.error('No ads found in input files');
            process.exit(1);
        }

        console.error(`Found ${ads.length} ads to process`);

        // Apply limit if specified
        if (limit > 0 && ads.length > limit) {
            console.error(`Limiting to ${limit} ads`);
            ads = ads.slice(0, limit);
        }

        // Launch browser
        console.error('Launching browser...');
        const browser = await puppeteer.launch({
            headless: 'new',
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        });

        const page = await browser.newPage();

        await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
        await page.setViewport({ width: 1280, height: 800 });

        const results = [];
        let processed = 0;
        let successful = 0;

        for (const ad of ads) {
            processed++;
            const transparencyUrl = getTransparencyUrl(ad);

            if (!transparencyUrl || !transparencyUrl.includes('adstransparency.google.com')) {
                console.error(`  [${processed}/${ads.length}] Skipping - no valid transparency URL`);
                continue;
            }

            console.error(`  [${processed}/${ads.length}] Processing ${ad.creative_id || 'unknown'}...`);

            const imageUrl = await extractImageUrl(page, transparencyUrl);

            results.push({
                domain: ad.domain || '',
                creative_id: ad.creative_id || '',
                advertiser_name: ad.advertiser_name || ad.title || '',
                transparency_url: transparencyUrl,
                image_url: imageUrl || '',
                format: ad.format || 'text',
                first_shown: ad.first_shown || '',
                last_shown: ad.last_shown || ''
            });

            if (imageUrl) {
                successful++;
                console.error(`    Found image URL`);
            } else {
                console.error(`    No image found`);
            }

            // Rate limiting
            if (processed < ads.length) {
                await sleep(delayMs);
            }
        }

        await browser.close();

        // Ensure output directory exists
        const outputDir = dirname(resolve(process.cwd(), outputPath));
        mkdirSync(outputDir, { recursive: true });

        // Write results
        const csvContent = toCSV(results);
        writeFileSync(resolve(process.cwd(), outputPath), csvContent, 'utf8');

        console.log(`\nResults:`);
        console.log(`  Processed: ${processed}`);
        console.log(`  Images found: ${successful}`);
        console.log(`  Output: ${outputPath}`);

    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

main();
