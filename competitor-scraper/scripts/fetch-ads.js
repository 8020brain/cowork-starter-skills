#!/usr/bin/env node

/**
 * DataForSEO Competitor Ads Fetcher
 *
 * Fetches competitor Google Ads using DataForSEO API and outputs to CSV.
 *
 * Usage:
 *   node fetch-ads.js \
 *     --domain=chase.com \
 *     --location=2840 \
 *     --output=output/chase.com.csv
 *
 * Requires scripts/.env with:
 *   DATAFORSEO_LOGIN=your_login
 *   DATAFORSEO_PASSWORD=your_password
 */

import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

// Load environment variables from scripts/.env (same directory as this script)
const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, '.env') });

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

const domain = args['domain'];
const locationCode = parseInt(args['location']) || 2840;
const outputPath = args['output'];
const depth = parseInt(args['depth']) || 40;

// Validate required arguments
if (!domain || !outputPath) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  node fetch-ads.js \\');
    console.error('    --domain=chase.com \\');
    console.error('    --location=2840 \\');
    console.error('    --output=output/chase.com.csv');
    process.exit(1);
}

// Validate credentials
const login = process.env.DATAFORSEO_LOGIN;
const password = process.env.DATAFORSEO_PASSWORD;

if (!login || !password) {
    console.error('Error: Missing DataForSEO credentials');
    console.error('Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in scripts/.env');
    process.exit(1);
}

// Fetch ads from DataForSEO API
async function fetchAds(targetDomain, location, adDepth) {
    const auth = Buffer.from(`${login}:${password}`).toString('base64');

    const requestBody = [{
        target: targetDomain,
        location_code: location,
        depth: adDepth,
        platform: 'google_search',
        format: 'all'
    }];

    const response = await fetch('https://api.dataforseo.com/v3/serp/google/ads_search/live/advanced', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${auth}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API request failed: ${response.status} ${response.statusText}\n${errorText}`);
    }

    const data = await response.json();

    if (data.status_code !== 20000) {
        throw new Error(`API error: ${data.status_message || 'Unknown error'}`);
    }

    return data;
}

// Extract ad data from API response
function extractAds(apiResponse, targetDomain) {
    const ads = [];

    if (!apiResponse.tasks || apiResponse.tasks.length === 0) {
        return ads;
    }

    const task = apiResponse.tasks[0];

    if (!task.result || task.result.length === 0) {
        return ads;
    }

    for (const result of task.result) {
        if (!result.items || result.items.length === 0) {
            continue;
        }

        for (const item of result.items) {
            // Extract preview image details (it's an array)
            let previewImageUrl = '';
            let previewImageWidth = '';
            let previewImageHeight = '';

            if (item.preview_image && Array.isArray(item.preview_image) && item.preview_image.length > 0) {
                const preview = item.preview_image[0];
                previewImageUrl = preview.url || '';
                previewImageWidth = preview.width || '';
                previewImageHeight = preview.height || '';
            }

            ads.push({
                domain: targetDomain,
                creative_id: item.creative_id || '',
                advertiser_id: item.advertiser_id || '',
                advertiser_name: item.title || '',
                verified: item.verified ? 'true' : 'false',
                format: item.format || 'text',
                first_shown: item.first_shown || '',
                last_shown: item.last_shown || '',
                transparency_url: item.url || '',
                preview_url: item.preview_url || '',
                preview_image_url: previewImageUrl,
                preview_image_width: previewImageWidth,
                preview_image_height: previewImageHeight
            });
        }
    }

    return ads;
}

// Convert ads array to CSV
function toCSV(ads) {
    if (ads.length === 0) {
        return 'domain,creative_id,advertiser_id,advertiser_name,verified,format,first_shown,last_shown,transparency_url,preview_url,preview_image_url,preview_image_width,preview_image_height\n';
    }

    const headers = Object.keys(ads[0]);
    const rows = [headers.join(',')];

    for (const ad of ads) {
        const values = headers.map(header => {
            let value = ad[header];
            if (value !== null && value !== undefined) {
                value = String(value);
                // Quote if contains comma, quote, or newline
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
        // Fetch ads from API
        console.error(`Fetching ads for ${domain}...`);
        const apiResponse = await fetchAds(domain, locationCode, depth);

        // Extract ad data
        const ads = extractAds(apiResponse, domain);

        // Ensure output directory exists
        const outputDir = dirname(outputPath);
        mkdirSync(outputDir, { recursive: true });

        // Write CSV
        const csvContent = toCSV(ads);
        writeFileSync(outputPath, csvContent, 'utf8');

        // Output summary
        console.log(`File: ${outputPath}`);
        console.log(`Ads: ${ads.length}`);

    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

main();
