#!/usr/bin/env node

/**
 * Search Term Analyzer - SOP 3 N-gram Processor
 *
 * Extracts 1-grams and 2-grams from search terms, aggregates metrics,
 * classifies as non-converting or inefficient, and flags safe n-grams
 * that appear in high-performing terms.
 *
 * Includes Search, PMax, and Shopping terms (all campaign types except Display/Video).
 *
 * Usage:
 *   node ngram-analysis.js [--data=<dir>] [--campaign="Campaign Name"] [--output=<path>] [--config=<path>]
 *
 * Options:
 *   --data      Directory containing CSV exports (default: ./data or ../data)
 *   --campaign  Filter to a specific campaign name
 *   --output    Output JSON path (default: ../tmp/ngram-summary.json)
 *   --config    Path to config.json (default: searches up from data dir)
 */

import { readFileSync, existsSync, mkdirSync } from 'fs';
import { writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parse } from 'csv-parse/sync';

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Parse CLI args ---
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.startsWith('--')) {
        const eq = arg.indexOf('=');
        if (eq > -1) {
            acc[arg.slice(2, eq)] = arg.slice(eq + 1);
        } else {
            acc[arg.slice(2)] = true;
        }
    }
    return acc;
}, {});

// --- Resolve data directory ---
function findDataDir() {
    if (args['data']) return resolve(args['data']);
    if (existsSync(resolve(process.cwd(), 'data'))) return resolve(process.cwd(), 'data');
    if (existsSync(resolve(__dirname, '../data'))) return resolve(__dirname, '../data');
    if (existsSync(resolve(__dirname, '../../data'))) return resolve(__dirname, '../../data');
    if (existsSync(resolve(process.cwd(), 'search-terms.csv'))) return process.cwd();
    return resolve(process.cwd(), 'data');
}

const dataDir = findDataDir();

// --- Resolve config ---
function findConfig() {
    if (args['config']) {
        const p = resolve(args['config']);
        if (existsSync(p)) return JSON.parse(readFileSync(p, 'utf8'));
    }
    const candidates = [
        resolve(dataDir, '../config.json'),
        resolve(dataDir, 'config.json'),
        resolve(process.cwd(), 'config.json'),
    ];
    for (const p of candidates) {
        if (existsSync(p)) return JSON.parse(readFileSync(p, 'utf8'));
    }
    return {};
}

const appConfig = findConfig();
const configTargets = appConfig.targets || {};

const campaignFilter = args['campaign'] || null;
const defaultOutput = resolve(__dirname, '../tmp/ngram-summary.json');
const outputPath = args['output'] ? resolve(args['output']) : defaultOutput;

// --- Load config ---
const ngCfg = appConfig.ngramAnalysis || {};
const minImpressions = parseInt(ngCfg.minImpressions ?? 100, 10);
const minClicks = parseInt(ngCfg.minClicks ?? 25, 10);
const minDistinctTerms = parseInt(ngCfg.minDistinctTerms ?? 3, 10);
const nonConvertingMult = parseFloat(ngCfg.nonConvertingSpendMultiplier ?? ngCfg.nonConvertingCostMultiplier ?? 2.0);
const inefficientCPAMult = parseFloat(ngCfg.inefficientCPAMultiplier ?? 1.75);
const inefficientROASMult = parseFloat(ngCfg.inefficientROASMultiplier ?? 0.7);
const extraStopwords = (ngCfg.stopwords || ngCfg.additionalStopwords || []).map(s => s.toLowerCase());
const biddingStrategyType = String(ngCfg.biddingStrategy || ngCfg.biddingStrategyType || 'cpa').toLowerCase() === 'roas' ? 'roas' : 'cpa';
const defaultAOV = parseFloat(ngCfg.defaultAOV ?? 0);

// Currency symbol resolution
const CURRENCY_SYMBOLS = { USD: '$', EUR: '\u20ac', GBP: '\u00a3', CAD: 'CA$', AUD: 'A$', JPY: '\u00a5', CHF: 'CHF', NZD: 'NZ$', SEK: 'kr', NOK: 'kr', DKK: 'kr', PLN: 'z\u0142', BRL: 'R$', MXN: 'MX$', INR: '\u20b9', ZAR: 'R' };
const currency = (appConfig.googleAds?.currency || 'USD').toUpperCase();
const currencySymbol = CURRENCY_SYMBOLS[currency] || currency;

const staCfg = appConfig.searchTermAnalysis || {};
const excludeBranded = staCfg.excludeBrandedCampaigns ?? true;
const brandedCampaignNames = new Set(
    (staCfg.brandedCampaigns || []).map(n => String(n).toLowerCase().trim())
);

// --- Parse business.md or config targets for CPA/ROAS ---
function parseBusinessContext() {
    if (configTargets.targetCPA || configTargets.maxCPA || configTargets.targetROAS) {
        return {
            targetCPA: configTargets.targetCPA || null,
            maxCPA: configTargets.maxCPA || null,
            targetROAS: configTargets.targetROAS || null
        };
    }
    const businessCandidates = [
        resolve(dataDir, '../business.md'),
        resolve(process.cwd(), 'business.md'),
    ];
    for (const businessPath of businessCandidates) {
        if (!existsSync(businessPath)) continue;
        const content = readFileSync(businessPath, 'utf8');
        let targetCPA = null, maxCPA = null, targetROAS = null;
        const lines = content.split('\n');
        for (const line of lines) {
            const lower = line.toLowerCase();
            const dollarMatch = line.match(/\$\s*([\d,]+(?:\.\d+)?)/);
            const numMatch = line.match(/([\d,]+(?:\.\d+)?)/);
            const val = dollarMatch ? parseFloat(dollarMatch[1].replace(/,/g, '')) :
                        numMatch ? parseFloat(numMatch[1].replace(/,/g, '')) : null;
            if (val === null) continue;
            if (lower.includes('max cpa') || lower.includes('maximum cpa') || lower.includes('cpa limit')) {
                maxCPA = val;
            } else if (lower.includes('target cpa') || lower.includes('cpa target') || lower.includes('goal cpa')) {
                targetCPA = val;
            } else if (lower.includes('target roas') || lower.includes('roas target') || lower.includes('goal roas')) {
                targetROAS = val;
            }
        }
        return { targetCPA: targetCPA || maxCPA, maxCPA, targetROAS };
    }
    return { targetCPA: null, maxCPA: null, targetROAS: null };
}

// --- Load CSV helper ---
function loadCSV(filePath) {
    if (!existsSync(filePath)) return [];
    try {
        const content = readFileSync(filePath, 'utf8');
        return parse(content, { columns: true, skip_empty_lines: true, trim: true });
    } catch (e) {
        console.error(`Warning: Could not parse ${filePath}: ${e.message}`);
        return [];
    }
}

// --- Field accessor ---
function f(row, ...names) {
    for (const name of names) {
        if (row[name] !== undefined && row[name] !== '') return row[name];
    }
    return '';
}

function num(val) {
    if (val === null || val === undefined || val === '') return 0;
    const n = parseFloat(String(val).replace(/,/g, ''));
    return isNaN(n) ? 0 : n;
}

function norm(val) {
    return String(val || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

// --- Stop words ---
const DEFAULT_STOPWORDS = new Set([
    'a', 'an', 'the', 'and', 'or', 'for', 'to', 'in', 'on', 'with',
    'of', 'is', 'it', 'as', 'at', 'be', 'by', 'from', 'this', 'that',
    'was', 'are', 'i', 'my', 'me', 'we', 'our', 'you', 'your', 'its',
    'do', 'does', 'can', 'get', 'use', 'using', 'used', 'how', 'what',
    'where', 'when', 'which', 'who', 'will', 'so', 'if', 'than', 'more',
    ...extraStopwords
]);

// --- N-gram extraction ---
function tokenize(text) {
    return text.toLowerCase()
        .replace(/[^a-z0-9\s'-]/g, ' ')
        .split(/\s+/)
        .filter(t => t.length >= 2 && !DEFAULT_STOPWORDS.has(t));
}

function extractNgrams(text) {
    const tokens = tokenize(text);
    const ngrams = [];
    for (const token of tokens) {
        ngrams.push({ ngram: token, type: '1-gram' });
    }
    for (let i = 0; i < tokens.length - 1; i++) {
        ngrams.push({ ngram: `${tokens[i]} ${tokens[i + 1]}`, type: '2-gram' });
    }
    return ngrams;
}

// --- Campaign type routing ---
const CHANNEL_TYPE_CODES = {
    '2': 'SEARCH',
    '3': 'DISPLAY',
    '4': 'SHOPPING',
    '6': 'VIDEO',
    '9': 'SMART',
    '10': 'MULTI_CHANNEL'
};
const SKIP_TYPES = new Set(['DISPLAY', 'VIDEO', 'HOTEL', 'LOCAL', 'SMART']);

function getCampaignType(row, campaignTypeMap) {
    const direct = f(row, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type', 'Campaign type');
    if (direct) {
        const code = String(direct).trim();
        return (CHANNEL_TYPE_CODES[code] || direct).toUpperCase();
    }
    const campName = f(row, 'campaign.name', 'campaign_name', 'Campaign');
    const fromMap = campaignTypeMap[campName] || 'SEARCH';
    return (CHANNEL_TYPE_CODES[String(fromMap).trim()] || fromMap).toUpperCase();
}

function isBrandedCampaign(campName) {
    const normalized = norm(campName);
    if (!normalized) return false;
    if (brandedCampaignNames.size > 0) {
        return brandedCampaignNames.has(normalized);
    }
    return /branded/i.test(campName) && !/non.?branded/i.test(campName);
}

function isEligibleRow(row, campaignTypeMap) {
    const campName = f(row, 'campaign.name', 'campaign_name', 'Campaign');
    if (campaignFilter && !campName.toLowerCase().includes(campaignFilter.toLowerCase())) {
        return { eligible: false, reason: 'campaign_filter' };
    }
    if (excludeBranded && isBrandedCampaign(campName)) {
        return { eligible: false, reason: 'branded_filter' };
    }
    const campType = getCampaignType(row, campaignTypeMap);
    if (SKIP_TYPES.has(campType)) {
        return { eligible: false, reason: 'channel_skip' };
    }
    return { eligible: true, campName, campType };
}

// --- Frequency recommendation based on account spend ---
function getFrequencyRecommendation(totalAccountCost) {
    if (totalAccountCost >= 50000) return { schedule: 'monthly', reason: 'High spend account -- monthly N-gram review recommended' };
    if (totalAccountCost >= 10000) return { schedule: 'quarterly', reason: 'Mid-spend account -- quarterly N-gram review recommended' };
    return { schedule: 'biannual', reason: 'Lower spend account -- biannual N-gram review sufficient' };
}

// --- Main ---
const { targetCPA, maxCPA, targetROAS } = parseBusinessContext();
const effectiveCPA = maxCPA || targetCPA;

const searchTermsPath = resolve(dataDir, 'search-terms.csv');
const searchTerms = loadCSV(searchTermsPath);
const campaigns = loadCSV(resolve(dataDir, 'campaigns.csv'));

// Load self-learning decisions file
const decisionsCandidates = [
    resolve(dataDir, '../analysis/search-term-decisions.json'),
    resolve(process.cwd(), 'analysis/search-term-decisions.json'),
];
let decisions = { relevantTerms: [], rejectedNgrams: [] };
for (const dp of decisionsCandidates) {
    if (existsSync(dp)) {
        try {
            decisions = JSON.parse(readFileSync(dp, 'utf8'));
        } catch (e) {
            console.warn(`WARNING: Could not parse search-term-decisions.json: ${e.message}`);
        }
        break;
    }
}
const rejectedNgramSet = new Set((decisions.rejectedNgrams || []).map(t => t.toLowerCase().trim()));

if (searchTerms.length === 0) {
    console.error('ERROR: search-terms.csv not found or empty.');
    console.error(`Looked in: ${searchTermsPath}`);
    console.error('Export your search terms report from Google Ads and place it in the data/ directory.');
    process.exit(1);
}

// Build campaign type map + bidding strategy map
const campaignTypeMap = {};
const BIDDING_STRATEGY_CODES = {
    '2': 'MANUAL_CPC', '3': 'MANUAL_CPM', '6': 'TARGET_CPA', '7': 'PAGE_ONE_PROMOTED',
    '9': 'TARGET_SPEND', '10': 'TARGET_ROAS', '11': 'MAXIMIZE_CONVERSIONS',
    '12': 'MAXIMIZE_CONVERSION_VALUE', '13': 'TARGET_IMPRESSION_SHARE', '14': 'MANUAL_CPV'
};
const CPA_STRATEGIES = new Set(['TARGET_CPA', 'MAXIMIZE_CONVERSIONS', 'MANUAL_CPC', 'TARGET_SPEND']);
const ROAS_STRATEGIES = new Set(['TARGET_ROAS', 'MAXIMIZE_CONVERSION_VALUE']);
const campaignBiddingMap = {};
for (const c of campaigns) {
    const name = f(c, 'campaign.name', 'campaign_name', 'name', 'Campaign');
    const rawType = f(c, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type', 'advertising_channel_type', 'Campaign type');
    if (name) campaignTypeMap[name] = CHANNEL_TYPE_CODES[String(rawType).trim()] || rawType || 'SEARCH';

    const rawStrategy = f(c, 'campaign.bidding_strategy_type', 'campaign_bidding_strategy_type', 'bidding_strategy_type', 'Bid strategy type');
    const strategyName = (BIDDING_STRATEGY_CODES[String(rawStrategy).trim()] || String(rawStrategy)).toUpperCase();
    const targetCpaDirect = num(f(c, 'campaign.target_cpa.target_cpa_micros', 'campaign_target_cpa_target_cpa_micros', 'campaign.target_cpa.target_cpa', 'campaign_target_cpa_target_cpa'));
    const targetCpaMaxConv = num(f(c, 'campaign.maximize_conversions.target_cpa_micros', 'campaign_maximize_conversions_target_cpa_micros', 'campaign.maximize_conversions.target_cpa', 'campaign_maximize_conversions_target_cpa'));
    const targetCpaMicros = targetCpaDirect || targetCpaMaxConv;
    const targetRoasMaxConvValue = num(f(c, 'campaign.maximize_conversion_value.target_roas', 'campaign_maximize_conversion_value_target_roas'));
    const targetRoasDirect = num(f(c, 'campaign.target_roas.target_roas', 'campaign_target_roas_target_roas'));
    const campTargetRoas = targetRoasMaxConvValue || targetRoasDirect;

    if (name) {
        let strategy = biddingStrategyType;
        let target = null;
        if (ROAS_STRATEGIES.has(strategyName)) {
            strategy = 'roas';
            target = campTargetRoas > 0 ? campTargetRoas : (targetROAS || null);
        } else if (CPA_STRATEGIES.has(strategyName)) {
            strategy = 'cpa';
            target = targetCpaMicros > 0 ? targetCpaMicros : (effectiveCPA || null);
        }
        campaignBiddingMap[name] = { strategy, target, strategyName };
    }
}

// Aggregate metrics per n-gram
const ngramMap = new Map();
let totalAccountCost = 0;
let totalEligibleConversions = 0;
let totalEligibleConvValue = 0;
const eligibleRows = [];
const warnings = [];

for (const row of searchTerms) {
    const eligibility = isEligibleRow(row, campaignTypeMap);
    if (!eligibility.eligible) continue;

    const term = f(row, 'campaign_search_term_view.search_term', 'search_term', 'Search term');
    if (!term) continue;

    const clicks = num(f(row, 'clicks', 'metrics.clicks', 'Clicks'));
    const impressions = num(f(row, 'impressions', 'metrics.impressions', 'Impressions'));
    const cost = num(f(row, 'cost', 'metrics.cost', 'Cost'));
    const conversions = num(f(row, 'conversions', 'metrics.conversions', 'Conversions'));
    const convValue = num(f(row, 'conversions_value', 'metrics.conversions_value', 'Conv. value'));
    const cpa = conversions > 0 ? cost / conversions : null;
    const roas = cost > 0 && convValue > 0 ? convValue / cost : null;

    totalAccountCost += cost;
    totalEligibleConversions += conversions;
    totalEligibleConvValue += convValue;
    eligibleRows.push({
        term,
        campName: eligibility.campName,
        campType: eligibility.campType,
        clicks,
        impressions,
        cost,
        conversions,
        convValue,
        cpa,
        roas
    });

    const campName = eligibility.campName;
    const ngrams = extractNgrams(term);
    for (const { ngram, type } of ngrams) {
        if (!ngramMap.has(ngram)) {
            ngramMap.set(ngram, {
                ngram,
                type,
                impressions: 0,
                clicks: 0,
                cost: 0,
                conversions: 0,
                convValue: 0,
                distinctTerms: new Set(),
                exampleTerms: [],
                campaignMetrics: new Map()
            });
        }
        const entry = ngramMap.get(ngram);
        entry.impressions += impressions;
        entry.clicks += clicks;
        entry.cost += cost;
        entry.conversions += conversions;
        entry.convValue += convValue;
        entry.distinctTerms.add(term);
        if (entry.exampleTerms.length < 5 && !entry.exampleTerms.includes(term)) {
            entry.exampleTerms.push(term);
        }
        if (campName) {
            if (!entry.campaignMetrics.has(campName)) {
                entry.campaignMetrics.set(campName, { cost: 0, conversions: 0, convValue: 0, clicks: 0, impressions: 0 });
            }
            const cm = entry.campaignMetrics.get(campName);
            cm.cost += cost;
            cm.conversions += conversions;
            cm.convValue += convValue;
            cm.clicks += clicks;
            cm.impressions += impressions;
        }
    }
}

const inferredAOV = totalEligibleConversions > 0
    ? totalEligibleConvValue / totalEligibleConversions
    : null;
const activeAOV = (inferredAOV !== null && inferredAOV > 0)
    ? inferredAOV
    : (defaultAOV > 0 ? defaultAOV : null);

if (biddingStrategyType === 'roas' && targetROAS === null) {
    warnings.push('targetROAS is not set; inefficient ROAS bucket will remain empty.');
}
if (biddingStrategyType === 'roas' && activeAOV === null) {
    warnings.push('AOV is unavailable (no conversion value data and no defaultAOV); non-converting ROAS threshold cannot be computed.');
}
if (biddingStrategyType === 'cpa' && effectiveCPA === null) {
    warnings.push('targetCPA/maxCPA is not set; non-converting classification falls back to cost > 0 and inefficient CPA bucket will remain empty.');
}

function isHighPerformer(entry) {
    if (entry.conversions <= 0) return false;
    const campBidding = campaignBiddingMap[entry.campName];
    const strategy = campBidding ? campBidding.strategy : biddingStrategyType;
    const target = campBidding ? campBidding.target : (strategy === 'roas' ? targetROAS : effectiveCPA);

    if (strategy === 'roas') {
        if (target === null) return true;
        return entry.roas === null || entry.roas >= target;
    }
    if (target === null) return true;
    return entry.cpa !== null && entry.cpa <= target;
}

// Build high-performing terms safe list
const highPerformingTerms = new Set();
for (const entry of eligibleRows) {
    if (!isHighPerformer(entry)) continue;
    const tokens = tokenize(entry.term);
    for (const token of tokens) highPerformingTerms.add(token);
    for (let i = 0; i < tokens.length - 1; i++) {
        highPerformingTerms.add(`${tokens[i]} ${tokens[i + 1]}`);
    }
}

function buildCampaignBreakdown(campaignMetrics) {
    const breakdown = [];
    let dominantCamp = null;
    let maxCost = -1;
    for (const [camp, m] of campaignMetrics.entries()) {
        const bidding = campaignBiddingMap[camp] || { strategy: biddingStrategyType, target: null };
        breakdown.push({
            campaign: camp,
            strategy: bidding.strategy,
            target: bidding.target !== null ? Math.round(bidding.target * 100) / 100 : null,
            cost: Math.round(m.cost * 100) / 100,
            conversions: Math.round(m.conversions * 100) / 100,
            clicks: m.clicks,
            impressions: m.impressions
        });
        if (m.cost > maxCost) {
            maxCost = m.cost;
            dominantCamp = camp;
        }
    }
    breakdown.sort((a, b) => b.cost - a.cost);
    return { breakdown, dominantCamp };
}

// Filter, classify, and flag n-grams
const nonConverting = [];
const inefficient = [];
const flagged = [];

for (const [ngram, data] of ngramMap) {
    const distinctCount = data.distinctTerms.size;

    if (data.impressions < minImpressions) continue;
    if (data.clicks < minClicks) continue;
    if (distinctCount < minDistinctTerms) continue;

    const cpa = data.conversions > 0 ? data.cost / data.conversions : null;
    const roas = data.cost > 0 && data.convValue > 0 ? data.convValue / data.cost : null;

    const { breakdown: campBreakdown, dominantCamp } = buildCampaignBreakdown(data.campaignMetrics);
    const domBidding = campaignBiddingMap[dominantCamp] || { strategy: biddingStrategyType, target: null };
    const domStrategy = domBidding.strategy;
    const domTarget = domBidding.target || (domStrategy === 'roas' ? targetROAS : effectiveCPA);

    const entry = {
        ngram,
        type: data.type,
        impressions: Math.round(data.impressions),
        clicks: Math.round(data.clicks),
        cost: Math.round(data.cost * 100) / 100,
        conversions: Math.round(data.conversions * 100) / 100,
        cpa: cpa !== null ? Math.round(cpa * 100) / 100 : null,
        roas: roas !== null ? Math.round(roas * 100) / 100 : null,
        distinctTerms: distinctCount,
        exampleTerms: data.exampleTerms,
        appearsInHighPerforming: highPerformingTerms.has(ngram),
        dominantCampaign: dominantCamp,
        dominantStrategy: domStrategy,
        dominantTarget: domTarget !== null ? Math.round(domTarget * 100) / 100 : null,
        campaignBreakdown: campBreakdown
    };

    if (entry.appearsInHighPerforming) {
        flagged.push({ ...entry, safeListConflict: true });
        continue;
    }

    if (domStrategy === 'roas') {
        if (data.conversions === 0 && activeAOV !== null && data.cost > activeAOV * nonConvertingMult) {
            nonConverting.push({ ...entry, classification: 'non_converting', suggestedList: 'ngramNonConverting' });
        } else if (data.conversions > 0 && domTarget !== null && roas !== null && roas < domTarget * inefficientROASMult) {
            inefficient.push({ ...entry, classification: 'inefficient', suggestedList: 'ngramInefficient' });
        }
    } else {
        if (data.conversions === 0 && domTarget !== null && data.cost > domTarget * nonConvertingMult) {
            nonConverting.push({ ...entry, classification: 'non_converting', suggestedList: 'ngramNonConverting' });
        } else if (data.conversions === 0 && domTarget === null && data.cost > 0) {
            nonConverting.push({ ...entry, classification: 'non_converting', suggestedList: 'ngramNonConverting' });
        } else if (data.conversions > 0 && domTarget !== null && cpa !== null && cpa > domTarget * inefficientCPAMult) {
            inefficient.push({ ...entry, classification: 'inefficient', suggestedList: 'ngramInefficient' });
        }
    }
}

// Filter out rejected n-grams (self-learning)
let rejectedNgramsFiltered = 0;
function filterRejected(arr) {
    if (rejectedNgramSet.size === 0) return arr;
    const filtered = arr.filter(entry => {
        if (rejectedNgramSet.has(entry.ngram.toLowerCase())) {
            rejectedNgramsFiltered++;
            return false;
        }
        return true;
    });
    return filtered;
}
const filteredNonConverting = filterRejected(nonConverting);
const filteredInefficient = filterRejected(inefficient);

filteredNonConverting.sort((a, b) => b.cost - a.cost);
filteredInefficient.sort((a, b) => b.cost - a.cost);
flagged.sort((a, b) => b.cost - a.cost);

const frequencyRec = getFrequencyRecommendation(totalAccountCost);

const sharedLists = staCfg.sharedNegativeLists || {
    primary: 'Search Term Exclusions',
    ngramNonConverting: 'Non-Converting N-grams',
    ngramInefficient: 'Inefficient N-grams'
};

const summary = {
    meta: {
        generatedAt: new Date().toISOString(),
        totalInputTerms: searchTerms.length,
        eligibleTerms: eligibleRows.length,
        campaignFilter: campaignFilter || null,
        totalAccountCost: Math.round(totalAccountCost * 100) / 100,
        currency,
        currencySymbol,
        targetCPA,
        maxCPA,
        targetROAS,
        activeBiddingStrategy: biddingStrategyType,
        aovUsed: activeAOV !== null ? Math.round(activeAOV * 100) / 100 : null,
        thresholds: {
            minImpressions,
            minClicks,
            minDistinctTerms,
            nonConvertingCostMultiplier: nonConvertingMult,
            inefficientCPAMultiplier: inefficientCPAMult,
            inefficientROASMultiplier: inefficientROASMult
        },
        counts: {
            nonConverting: filteredNonConverting.length,
            inefficient: filteredInefficient.length,
            flaggedSafeList: flagged.length,
            totalNgramsCandidates: filteredNonConverting.length + filteredInefficient.length,
            rejectedNgramsFiltered
        },
        frequencyRecommendation: frequencyRec,
        sharedLists,
        warnings
    },
    non_converting: filteredNonConverting,
    inefficient: filteredInefficient,
    safe_list_conflicts: flagged.slice(0, 20)
};

// Ensure output directory exists
const outputDir = dirname(outputPath);
if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
}

writeFileSync(outputPath, JSON.stringify(summary, null, 2), 'utf8');

console.log(`N-gram summary written to: ${outputPath}`);
console.log(`  Eligible terms: ${eligibleRows.length} (of ${searchTerms.length} input rows)`);
console.log(`  Total account cost: ${currencySymbol}${totalAccountCost.toFixed(2)}`);
console.log(`  Active bidding strategy: ${biddingStrategyType}`);
console.log(`  Non-converting n-grams: ${filteredNonConverting.length}`);
console.log(`  Inefficient n-grams: ${filteredInefficient.length}`);
if (rejectedNgramsFiltered > 0) console.log(`  Rejected n-grams filtered (decisions file): ${rejectedNgramsFiltered}`);
console.log(`  Safe list conflicts (skipped): ${flagged.length}`);
console.log(`  Frequency recommendation: ${frequencyRec.schedule}`);
