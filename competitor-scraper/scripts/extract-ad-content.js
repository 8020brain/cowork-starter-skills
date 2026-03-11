#!/usr/bin/env node

/**
 * Extract Ad Content from Images using Gemini Flash
 *
 * Uses Google's Gemini Flash model to analyze ad images and extract
 * structured content (headlines, descriptions, display URLs, sitelinks)
 *
 * Usage:
 *   node extract-ad-content.js \
 *     --input=output/.temp/ad-images/chase.com.csv \
 *     --output=output/chase.com.csv
 *
 * Requires scripts/.env with:
 *   GEMINI_API_KEY=your_api_key
 */

import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';
import { GoogleGenerativeAI } from '@google/generative-ai';

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

const inputFile = args['input'];
const outputPath = args['output'];
const batchSize = parseInt(args['batch-size']) || 5;
const delayMs = parseInt(args['delay']) || 1000;
const limit = parseInt(args['limit']) || 0;

// Validate required arguments
if (!inputFile || !outputPath) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  node extract-ad-content.js \\');
    console.error('    --input=output/.temp/ad-images/chase.com.csv \\');
    console.error('    --output=output/chase.com.csv');
    console.error('');
    console.error('Options:');
    console.error('  --batch-size=5   Process N images concurrently (default: 5)');
    console.error('  --delay=1000     Delay between batches in ms (default: 1000)');
    console.error('  --limit=10       Limit number of ads to process (default: all)');
    process.exit(1);
}

// Validate Gemini API key
const apiKey = process.env.GEMINI_API_KEY;

if (!apiKey || apiKey === 'your_api_key') {
    console.error('Error: Missing Gemini API key');
    console.error('Set GEMINI_API_KEY in scripts/.env');
    console.error('Get a key from: https://aistudio.google.com/apikey');
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

// Sleep helper
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Fetch image as base64
async function fetchImageAsBase64(imageUrl) {
    try {
        const response = await fetch(imageUrl);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const arrayBuffer = await response.arrayBuffer();
        const buffer = Buffer.from(arrayBuffer);
        const base64 = buffer.toString('base64');

        const contentType = response.headers.get('content-type') || 'image/png';

        return { base64, mimeType: contentType };
    } catch (error) {
        throw new Error(`Failed to fetch image: ${error.message}`);
    }
}

// Extract ad content using Gemini
async function extractAdContent(model, imageUrl) {
    try {
        const { base64, mimeType } = await fetchImageAsBase64(imageUrl);

        const prompt = `Analyze this Google Search Ad image and extract the ad content.
Return ONLY valid JSON with this exact structure (no markdown, no code blocks):
{
  "headline": "the main headline text",
  "headline2": "second headline if present, otherwise empty string",
  "headline3": "third headline if present, otherwise empty string",
  "description": "the full description text",
  "description2": "second description if present, otherwise empty string",
  "display_url": "the displayed URL path",
  "sitelinks": [
    {"title": "sitelink title", "description": "sitelink description if any"}
  ],
  "callouts": ["callout1", "callout2"],
  "structured_snippets": ["snippet1", "snippet2"]
}

If any field is not visible in the ad, use an empty string or empty array.
Extract ALL visible text content accurately.`;

        const result = await model.generateContent([
            { text: prompt },
            {
                inlineData: {
                    mimeType: mimeType,
                    data: base64
                }
            }
        ]);

        const response = await result.response;
        const text = response.text();

        // Parse JSON response (handle markdown code blocks)
        let jsonText = text;
        const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (jsonMatch) {
            jsonText = jsonMatch[1].trim();
        }

        jsonText = jsonText.trim();

        const adContent = JSON.parse(jsonText);

        return {
            success: true,
            content: adContent
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

// Convert results to CSV
function toCSV(results) {
    if (results.length === 0) {
        return 'domain,creative_id,advertiser_name,format,first_shown,last_shown,headline,headline2,headline3,description,description2,display_url,sitelinks,callouts,structured_snippets,transparency_url,image_url,extraction_status\n';
    }

    const headers = Object.keys(results[0]);
    const rows = [headers.join(',')];

    for (const result of results) {
        const values = headers.map(header => {
            let value = result[header];
            if (value !== null && value !== undefined) {
                if (Array.isArray(value)) {
                    value = JSON.stringify(value);
                }
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

// Process a batch of ads
async function processBatch(model, ads, startIdx) {
    const results = await Promise.all(
        ads.map(async (ad, idx) => {
            const globalIdx = startIdx + idx + 1;

            if (!ad.image_url) {
                console.error(`  [${globalIdx}] Skipping ${ad.creative_id} - no image URL`);
                return {
                    ...ad,
                    headline: '',
                    headline2: '',
                    headline3: '',
                    description: '',
                    description2: '',
                    display_url: '',
                    sitelinks: [],
                    callouts: [],
                    structured_snippets: [],
                    extraction_status: 'skipped_no_image'
                };
            }

            console.error(`  [${globalIdx}] Processing ${ad.creative_id}...`);

            const extraction = await extractAdContent(model, ad.image_url);

            if (extraction.success) {
                console.error(`    Extracted content`);
                return {
                    domain: ad.domain || '',
                    creative_id: ad.creative_id || '',
                    advertiser_name: ad.advertiser_name || '',
                    format: ad.format || '',
                    first_shown: ad.first_shown || '',
                    last_shown: ad.last_shown || '',
                    headline: extraction.content.headline || '',
                    headline2: extraction.content.headline2 || '',
                    headline3: extraction.content.headline3 || '',
                    description: extraction.content.description || '',
                    description2: extraction.content.description2 || '',
                    display_url: extraction.content.display_url || '',
                    sitelinks: extraction.content.sitelinks || [],
                    callouts: extraction.content.callouts || [],
                    structured_snippets: extraction.content.structured_snippets || [],
                    transparency_url: ad.transparency_url || '',
                    image_url: ad.image_url || '',
                    extraction_status: 'success'
                };
            } else {
                console.error(`    Failed: ${extraction.error}`);
                return {
                    domain: ad.domain || '',
                    creative_id: ad.creative_id || '',
                    advertiser_name: ad.advertiser_name || '',
                    format: ad.format || '',
                    first_shown: ad.first_shown || '',
                    last_shown: ad.last_shown || '',
                    headline: '',
                    headline2: '',
                    headline3: '',
                    description: '',
                    description2: '',
                    display_url: '',
                    sitelinks: [],
                    callouts: [],
                    structured_snippets: [],
                    transparency_url: ad.transparency_url || '',
                    image_url: ad.image_url || '',
                    extraction_status: `error: ${extraction.error}`
                };
            }
        })
    );

    return results;
}

// Main execution
async function main() {
    try {
        // Initialize Gemini
        console.error('Initializing Gemini...');
        const genAI = new GoogleGenerativeAI(apiKey);
        const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });

        // Load input data
        console.error(`Loading ads from ${inputFile}...`);
        const content = readFileSync(resolve(process.cwd(), inputFile), 'utf8');
        let ads = parseCSV(content);

        if (ads.length === 0) {
            console.error('No ads found in input file');
            process.exit(1);
        }

        console.error(`Found ${ads.length} ads to process`);

        // Apply limit if specified
        if (limit > 0 && ads.length > limit) {
            console.error(`Limiting to ${limit} ads`);
            ads = ads.slice(0, limit);
        }

        // Filter to only ads with image URLs
        const adsWithImages = ads.filter(ad => ad.image_url);
        console.error(`${adsWithImages.length} ads have image URLs`);

        // Process in batches
        const allResults = [];
        const totalBatches = Math.ceil(ads.length / batchSize);

        for (let i = 0; i < ads.length; i += batchSize) {
            const batch = ads.slice(i, i + batchSize);
            const batchNum = Math.floor(i / batchSize) + 1;

            console.error(`\nBatch ${batchNum}/${totalBatches}:`);

            const batchResults = await processBatch(model, batch, i);
            allResults.push(...batchResults);

            // Delay between batches (except for last batch)
            if (i + batchSize < ads.length) {
                await sleep(delayMs);
            }
        }

        // Ensure output directory exists
        const outputDir = dirname(resolve(process.cwd(), outputPath));
        mkdirSync(outputDir, { recursive: true });

        // Write results
        const csvContent = toCSV(allResults);
        writeFileSync(resolve(process.cwd(), outputPath), csvContent, 'utf8');

        // Summary
        const successful = allResults.filter(r => r.extraction_status === 'success').length;
        const skipped = allResults.filter(r => r.extraction_status === 'skipped_no_image').length;
        const failed = allResults.filter(r => r.extraction_status.startsWith('error')).length;

        console.log(`\nResults:`);
        console.log(`  Total: ${allResults.length}`);
        console.log(`  Successful: ${successful}`);
        console.log(`  Skipped (no image): ${skipped}`);
        console.log(`  Failed: ${failed}`);
        console.log(`  Output: ${outputPath}`);

    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

main();
