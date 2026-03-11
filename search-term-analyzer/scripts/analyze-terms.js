#!/usr/bin/env node

/**
 * Search Term Analyzer - SOP 1 Data Processor
 *
 * Compresses search-terms.csv (100k+ rows) into a compact JSON summary
 * that Claude can analyze without overflowing the context window.
 *
 * Buckets:
 *   - promotion_candidates: Converting terms not yet in keywords
 *   - irrelevant_candidates: Non-converting, high-cost
 *   - manual_review_unknown_status: Terms requiring status resolution (no negatives source)
 *   - inefficient_candidates: Converting but above CPA/below ROAS thresholds
 *   - monitor: Low-volume terms worth watching
 *   - pmax_shopping_summary: PMax/Shopping terms (SOP 3 only, not SOP 1/2)
 *
 * Output caps: top 150 irrelevants by cost, all promotions, top 30 monitor
 *
 * Usage:
 *   node analyze-terms.js [--data=<dir>] [--campaign="Campaign Name"] [--output=<path>] [--config=<path>]
 *
 * Options:
 *   --data      Directory containing CSV exports (default: ./data or ../data)
 *   --campaign  Filter to a specific campaign name
 *   --output    Output JSON path (default: ../tmp/analysis-summary.json)
 *   --config    Path to config.json (default: searches up from data dir)
 */

import { readFileSync, existsSync, statSync, mkdirSync } from 'fs';
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

const campaignFilter = args['campaign'] || null;
const exportFlag = true;
const defaultOutput = resolve(__dirname, '../tmp/analysis-summary.json');
const outputPath = args['output'] ? resolve(args['output']) : defaultOutput;

// --- Load config ---
const sta = appConfig.searchTermAnalysis || {};
const targets = appConfig.targets || {};
const minCostForNeg = parseFloat(sta.minSpendToFlag ?? sta.minCostForNegativeConsideration ?? 20);
const conversionLagDays = parseInt(sta.conversionLagDays ?? 14, 10);
const excludeBranded = sta.excludeBrandedCampaigns ?? true;
const brandedCampaignNames = new Set(
    (sta.brandedCampaigns || []).map(n => n.toLowerCase().trim())
);
const biddingStrategyType = (sta.biddingStrategy || 'cpa').toLowerCase();
const inefficientCPAMultiplier = parseFloat(sta.inefficientCPAMultiplier ?? 1.5);
const inefficientROASMultiplier = parseFloat(sta.inefficientROASMultiplier ?? 0.7);
const minCostForInefficient = parseFloat(sta.minSpendForInefficient ?? 50);
const minClicksForInefficient = parseInt(sta.minClicksForInefficient ?? 3, 10);
const neverExcludeTerms = new Set((sta.protectedTerms?.neverExclude || []).map(t => norm(t)));
const alwaysIncludeTerms = new Set((sta.protectedTerms?.alwaysInclude || []).map(t => norm(t)));

// Currency
const CURRENCY_SYMBOLS = { USD: '$', EUR: '\u20ac', GBP: '\u00a3', CAD: 'CA$', AUD: 'A$', JPY: '\u00a5', CHF: 'CHF', NZD: 'NZ$', SEK: 'kr', NOK: 'kr', DKK: 'kr', PLN: 'z\u0142', BRL: 'R$', MXN: 'MX$', INR: '\u20b9', ZAR: 'R' };
const currency = (appConfig.googleAds?.currency || 'USD').toUpperCase();
const currencySymbol = CURRENCY_SYMBOLS[currency] || currency;

// --- Parse business context for CPA/ROAS targets ---
function parseBusinessContext() {
    if (targets.targetCPA || targets.maxCPA || targets.targetROAS) {
        return { targetCPA: targets.targetCPA || null, maxCPA: targets.maxCPA || null, targetROAS: targets.targetROAS || null };
    }
    const businessCandidates = [resolve(dataDir, '../business.md'), resolve(process.cwd(), 'business.md')];
    for (const businessPath of businessCandidates) {
        if (!existsSync(businessPath)) continue;
        const content = readFileSync(businessPath, 'utf8');
        let targetCPA = null, maxCPA = null, targetROAS = null;
        for (const line of content.split('\n')) {
            const lower = line.toLowerCase();
            const dollarMatch = line.match(/\$\s*([\d,]+(?:\.\d+)?)/);
            const numMatch = line.match(/([\d,]+(?:\.\d+)?)/);
            const val = dollarMatch ? parseFloat(dollarMatch[1].replace(/,/g, '')) : numMatch ? parseFloat(numMatch[1].replace(/,/g, '')) : null;
            if (val === null) continue;
            if (lower.includes('max cpa') || lower.includes('maximum cpa') || lower.includes('cpa limit')) maxCPA = val;
            else if (lower.includes('target cpa') || lower.includes('cpa target') || lower.includes('goal cpa')) targetCPA = val;
            else if (lower.includes('target roas') || lower.includes('roas target') || lower.includes('goal roas')) targetROAS = val;
        }
        return { targetCPA: targetCPA || maxCPA, maxCPA, targetROAS };
    }
    return { targetCPA: null, maxCPA: null, targetROAS: null };
}

function loadCSV(filePath) {
    if (!existsSync(filePath)) return [];
    try {
        return parse(readFileSync(filePath, 'utf8'), { columns: true, skip_empty_lines: true, trim: true });
    } catch (e) {
        console.error(`Warning: Could not parse ${filePath}: ${e.message}`);
        return [];
    }
}

function f(row, ...names) {
    for (const name of names) { if (row[name] !== undefined && row[name] !== '') return row[name]; }
    return '';
}

function num(val) {
    if (val === null || val === undefined || val === '') return 0;
    const n = parseFloat(String(val).replace(/,/g, ''));
    return isNaN(n) ? 0 : n;
}

function norm(val) { return String(val || '').trim().toLowerCase().replace(/\s+/g, ' '); }
function key3(campaign, adGroup, term) { return `${norm(campaign)}|||${norm(adGroup)}|||${norm(term)}`; }

function loadNegativeStatus() {
    const empty = { available: false, source: null, accountTerms: new Set(), campaignTerms: new Set(), adGroupTerms: new Set(), linkAwareShared: false, warnings: [] };

    function buildFromRows(rows, sourceLabel) {
        const accountTerms = new Set(), campaignTerms = new Set(), adGroupTerms = new Set();
        for (const row of rows) {
            const term = norm(f(row, 'Keyword', 'keyword', 'criteria', 'negative_keyword', 'campaign_negative_keyword.keyword.text', 'ad_group_criterion.keyword.text', 'campaign_criterion.keyword.text', 'shared_criterion.keyword.text'));
            if (!term) continue;
            const campaign = norm(f(row, 'Campaign', 'campaign', 'campaign.name'));
            const adGroup = norm(f(row, 'Ad Group', 'ad_group', 'ad_group.name'));
            if (campaign && adGroup) adGroupTerms.add(`${campaign}|||${adGroup}|||${term}`);
            else if (campaign) campaignTerms.add(`${campaign}|||${term}`);
            else accountTerms.add(term);
        }
        return { available: true, source: sourceLabel, accountTerms, campaignTerms, adGroupTerms, linkAwareShared: false, warnings: [] };
    }

    for (const p of [resolve(dataDir, 'negative-keywords.csv'), resolve(dataDir, 'negatives.csv')]) {
        if (existsSync(p)) return buildFromRows(loadCSV(p), p);
    }

    const campaignNegPath = resolve(dataDir, 'negative-keywords-campaign.csv');
    const adGroupNegPath = resolve(dataDir, 'negative-keywords-adgroup.csv');
    const sharedNegPath = resolve(dataDir, 'negative-keywords-shared.csv');
    const sharedLinksPath = resolve(dataDir, 'negative-keywords-shared-links.csv');
    const hasCN = existsSync(campaignNegPath), hasAN = existsSync(adGroupNegPath), hasSN = existsSync(sharedNegPath), hasSL = existsSync(sharedLinksPath);

    if (!hasCN && !hasAN && !hasSN) return empty;

    const accountTerms = new Set(), campaignTerms = new Set(), adGroupTerms = new Set(), warnings = [], sources = [];

    if (hasCN) {
        sources.push(campaignNegPath);
        for (const row of loadCSV(campaignNegPath)) {
            const term = norm(f(row, 'campaign_criterion.keyword.text', 'Keyword', 'keyword', 'criteria'));
            const campaign = norm(f(row, 'campaign.name', 'Campaign', 'campaign'));
            if (!term) continue;
            if (campaign) campaignTerms.add(`${campaign}|||${term}`); else accountTerms.add(term);
        }
    }

    if (hasAN) {
        sources.push(adGroupNegPath);
        for (const row of loadCSV(adGroupNegPath)) {
            const term = norm(f(row, 'ad_group_criterion.keyword.text', 'Keyword', 'keyword', 'criteria'));
            const campaign = norm(f(row, 'campaign.name', 'Campaign', 'campaign'));
            const adGroup = norm(f(row, 'ad_group.name', 'Ad Group', 'ad_group'));
            if (!term) continue;
            if (campaign && adGroup) adGroupTerms.add(`${campaign}|||${adGroup}|||${term}`);
            else if (campaign) campaignTerms.add(`${campaign}|||${term}`);
            else accountTerms.add(term);
        }
    }

    let linkAwareShared = false;
    if (hasSN) {
        sources.push(sharedNegPath);
        const sharedTermsBySet = new Map(), looseSharedTerms = new Set();
        for (const row of loadCSV(sharedNegPath)) {
            const term = norm(f(row, 'shared_criterion.keyword.text', 'Keyword', 'keyword', 'criteria'));
            if (!term) continue;
            const setKey = norm(f(row, 'shared_set.resource_name')) || norm(f(row, 'shared_set.name', 'Shared Set', 'shared_set'));
            if (!setKey) { looseSharedTerms.add(term); continue; }
            if (!sharedTermsBySet.has(setKey)) sharedTermsBySet.set(setKey, new Set());
            sharedTermsBySet.get(setKey).add(term);
        }

        if (hasSL) {
            sources.push(sharedLinksPath);
            linkAwareShared = true;
            const campaignBySet = new Map();
            for (const row of loadCSV(sharedLinksPath)) {
                const campaign = norm(f(row, 'campaign.name', 'Campaign', 'campaign'));
                const setKey = norm(f(row, 'shared_set.resource_name')) || norm(f(row, 'shared_set.name', 'Shared Set', 'shared_set'));
                if (!campaign || !setKey) continue;
                if (!campaignBySet.has(setKey)) campaignBySet.set(setKey, new Set());
                campaignBySet.get(setKey).add(campaign);
            }
            for (const [setKey, terms] of sharedTermsBySet.entries()) {
                const cfs = campaignBySet.get(setKey);
                if (!cfs || cfs.size === 0) { warnings.push(`Shared set has no campaign links: ${setKey}`); for (const t of terms) accountTerms.add(t); continue; }
                for (const c of cfs) for (const t of terms) campaignTerms.add(`${c}|||${t}`);
            }
        } else {
            warnings.push('Shared negative links file missing; shared terms treated as account-level.');
            for (const terms of sharedTermsBySet.values()) for (const t of terms) accountTerms.add(t);
        }
        for (const t of looseSharedTerms) accountTerms.add(t);
    }

    return { available: true, source: sources.join(', '), accountTerms, campaignTerms, adGroupTerms, linkAwareShared, warnings };
}

function isTermExcluded(negatives, campaign, adGroup, term) {
    const t = norm(term), c = norm(campaign), a = norm(adGroup);
    if (!t) return false;
    return negatives.adGroupTerms.has(`${c}|||${a}|||${t}`) || negatives.campaignTerms.has(`${c}|||${t}`) || negatives.accountTerms.has(t);
}

const CHANNEL_TYPE_CODES = { '2': 'SEARCH', '3': 'DISPLAY', '4': 'SHOPPING', '6': 'VIDEO', '9': 'SMART', '10': 'MULTI_CHANNEL' };
const SKIP_TYPES = new Set(['DISPLAY', 'VIDEO', 'HOTEL', 'LOCAL', 'SMART']);
const PMAX_TYPES = new Set(['MULTI_CHANNEL', 'PERFORMANCE_MAX']);
const SHOPPING_TYPES = new Set(['SHOPPING']);

function getCampaignType(row, campaignTypeMap) {
    const direct = f(row, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type', 'Campaign type');
    if (direct) return (CHANNEL_TYPE_CODES[String(direct).trim()] || direct).toUpperCase();
    const campName = f(row, 'campaign.name', 'campaign_name', 'Campaign');
    const fromMap = campaignTypeMap[campName] || 'SEARCH';
    return (CHANNEL_TYPE_CODES[String(fromMap).trim()] || fromMap).toUpperCase();
}

// --- Main ---
const { targetCPA, maxCPA, targetROAS } = parseBusinessContext();
const effectiveCPA = maxCPA || targetCPA;

const searchTermsPath = resolve(dataDir, 'search-terms.csv');
const searchTerms = loadCSV(searchTermsPath);
const keywords = loadCSV(resolve(dataDir, 'keywords.csv'));
const campaigns = loadCSV(resolve(dataDir, 'campaigns.csv'));
const negatives = loadNegativeStatus();

// Self-learning decisions
let decisions = { relevantTerms: [], rejectedNgrams: [] };
for (const dp of [resolve(dataDir, '../analysis/search-term-decisions.json'), resolve(process.cwd(), 'analysis/search-term-decisions.json')]) {
    if (existsSync(dp)) { try { decisions = JSON.parse(readFileSync(dp, 'utf8')); } catch (e) { console.warn(`WARNING: Could not parse decisions: ${e.message}`); } break; }
}
const knownRelevantSet = new Set((decisions.relevantTerms || []).map(t => t.toLowerCase().trim()));

if (searchTerms.length === 0) {
    console.error('ERROR: search-terms.csv not found or empty.');
    console.error(`Looked in: ${searchTermsPath}`);
    console.error('Export your search terms report from Google Ads and place it in the data/ directory.');
    process.exit(1);
}

let dataAgeDays = 0;
if (existsSync(searchTermsPath)) dataAgeDays = Math.round((Date.now() - statSync(searchTermsPath).mtimeMs) / (1000 * 60 * 60 * 24));

// Build campaign type + bidding maps
const campaignTypeMap = {};
const BIDDING_STRATEGY_CODES = { '2': 'MANUAL_CPC', '3': 'MANUAL_CPM', '6': 'TARGET_CPA', '7': 'PAGE_ONE_PROMOTED', '9': 'TARGET_SPEND', '10': 'TARGET_ROAS', '11': 'MAXIMIZE_CONVERSIONS', '12': 'MAXIMIZE_CONVERSION_VALUE', '13': 'TARGET_IMPRESSION_SHARE', '14': 'MANUAL_CPV' };
const CPA_STRATEGIES = new Set(['TARGET_CPA', 'MAXIMIZE_CONVERSIONS', 'MANUAL_CPC', 'TARGET_SPEND']);
const ROAS_STRATEGIES = new Set(['TARGET_ROAS', 'MAXIMIZE_CONVERSION_VALUE']);
const campaignBiddingMap = {};
for (const c of campaigns) {
    const name = f(c, 'campaign.name', 'campaign_name', 'name', 'Campaign');
    const rawType = f(c, 'campaign.advertising_channel_type', 'campaign_advertising_channel_type', 'advertising_channel_type', 'Campaign type');
    if (name) campaignTypeMap[name] = CHANNEL_TYPE_CODES[String(rawType).trim()] || rawType || 'SEARCH';
    const rawStrategy = f(c, 'campaign.bidding_strategy_type', 'campaign_bidding_strategy_type', 'bidding_strategy_type', 'Bid strategy type');
    const strategyName = (BIDDING_STRATEGY_CODES[String(rawStrategy).trim()] || String(rawStrategy)).toUpperCase();
    const targetCpaMicros = num(f(c, 'campaign.target_cpa.target_cpa_micros', 'campaign_target_cpa_target_cpa_micros', 'campaign.target_cpa.target_cpa', 'campaign_target_cpa_target_cpa')) || num(f(c, 'campaign.maximize_conversions.target_cpa_micros', 'campaign_maximize_conversions_target_cpa_micros'));
    const campTargetRoas = num(f(c, 'campaign.maximize_conversion_value.target_roas', 'campaign_maximize_conversion_value_target_roas')) || num(f(c, 'campaign.target_roas.target_roas', 'campaign_target_roas_target_roas'));
    if (name) {
        let strategy = biddingStrategyType, target = null;
        if (ROAS_STRATEGIES.has(strategyName)) { strategy = 'roas'; target = campTargetRoas > 0 ? campTargetRoas : (targetROAS || null); }
        else if (CPA_STRATEGIES.has(strategyName)) { strategy = 'cpa'; target = targetCpaMicros > 0 ? targetCpaMicros : (effectiveCPA || null); }
        campaignBiddingMap[name] = { strategy, target, strategyName };
    }
}

// Build existing keywords set
const existingKeywords = new Set(), existingKeywordsByAdGroup = new Set();
for (const kw of keywords) {
    const campaign = f(kw, 'campaign.name', 'campaign_name', 'Campaign');
    const adGroup = f(kw, 'ad_group.name', 'ad_group_name', 'Ad group');
    const text = f(kw, 'ad_group_criterion.keyword.text', 'keyword.text', 'keyword_text', 'criteria', 'keyword', 'Keyword').toLowerCase().trim();
    if (!text) continue;
    existingKeywords.add(text);
    if (campaign && adGroup) existingKeywordsByAdGroup.add(key3(campaign, adGroup, text));
}

const typeBreakdown = { SEARCH: 0, MULTI_CHANNEL: 0, SHOPPING: 0, skipped: 0 };
const promotionCandidates = [], irrelevantCandidates = [], manualReviewUnknownStatus = [], inefficientCandidates = [], monitor = [];
const pmaxShoppingCampaigns = new Set();
let pmaxShoppingCount = 0, pmaxShoppingCost = 0;
const pmaxMonitor = [], filteredSearchRows = [];

for (const row of searchTerms) {
    const campName = f(row, 'campaign.name', 'campaign_name', 'Campaign');
    if (campaignFilter && !campName.toLowerCase().includes(campaignFilter.toLowerCase())) continue;
    const isBranded = brandedCampaignNames.size > 0 ? brandedCampaignNames.has(campName.toLowerCase().trim()) : /branded/i.test(campName) && !/non.?branded/i.test(campName);
    if (excludeBranded && isBranded) continue;
    const campType = getCampaignType(row, campaignTypeMap);
    const networkType = f(row, 'segments.ad_network_type', 'ad_network_type', 'Network') || 'SEARCH';
    if (SKIP_TYPES.has(campType)) { typeBreakdown.skipped++; continue; }
    if (PMAX_TYPES.has(campType) || SHOPPING_TYPES.has(campType)) {
        const key = PMAX_TYPES.has(campType) ? 'MULTI_CHANNEL' : 'SHOPPING';
        typeBreakdown[key]++;
        const cost = num(f(row, 'metrics.cost', 'cost', 'Cost'));
        const conversions = num(f(row, 'metrics.conversions', 'conversions', 'Conversions'));
        pmaxShoppingCount++; pmaxShoppingCost += cost;
        if (campName) pmaxShoppingCampaigns.add(campName);
        if (PMAX_TYPES.has(campType) && conversions === 0) {
            const term = f(row, 'campaign_search_term_view.search_term', 'search_term', 'Search term');
            const impressions = num(f(row, 'metrics.impressions', 'impressions', 'Impressions'));
            if (term && impressions >= 50) pmaxMonitor.push({ term, campaign: campName, cost: Math.round(cost * 100) / 100, impressions, clicks: num(f(row, 'metrics.clicks', 'clicks', 'Clicks')) });
        }
        continue;
    }
    typeBreakdown.SEARCH++;
    const term = f(row, 'campaign_search_term_view.search_term', 'search_term', 'Search term');
    if (!term) continue;
    const adGroup = f(row, 'ad_group.name', 'ad_group_name', 'Ad group');
    filteredSearchRows.push({ row, campName, adGroup, term, campType, networkType });
}

// Aggregate metrics
const aggregated = new Map();
for (const item of filteredSearchRows) {
    const row = item.row;
    const aKey = key3(item.campName, item.adGroup, item.term);
    const clicks = num(f(row, 'clicks', 'metrics.clicks', 'Clicks'));
    const impressions = num(f(row, 'impressions', 'metrics.impressions', 'Impressions'));
    const cost = num(f(row, 'cost', 'metrics.cost', 'Cost'));
    const conversions = num(f(row, 'conversions', 'metrics.conversions', 'Conversions'));
    const convValue = num(f(row, 'conversions_value', 'metrics.conversions_value', 'Conv. value'));
    if (aggregated.has(aKey)) {
        const a = aggregated.get(aKey); a.clicks += clicks; a.impressions += impressions; a.cost += cost; a.conversions += conversions; a.convValue += convValue;
    } else {
        aggregated.set(aKey, { term: item.term, campName: item.campName, adGroup: item.adGroup, campType: item.campType, networkType: item.networkType, clicks, impressions, cost, conversions, convValue });
    }
}

// Bucket aggregated terms
for (const [aKey, agg] of aggregated.entries()) {
    const { term, campName, adGroup, campType, networkType, clicks, impressions, conversions, convValue } = agg;
    const cost = agg.cost;
    const cpa = conversions > 0 ? cost / conversions : null;
    const roas = cost > 0 && convValue > 0 ? convValue / cost : null;
    const alreadyKeyword = existingKeywords.has(norm(term));
    const addedInAdGroup = existingKeywordsByAdGroup.has(key3(campName, adGroup, term));
    const excluded = negatives.available ? isTermExcluded(negatives, campName, adGroup, term) : null;
    let status = 'unknown', statusResolution = 'no_negative_data';
    if (addedInAdGroup) { status = 'added_in_ad_group'; statusResolution = 'added_by_keyword_lookup'; }
    else if (negatives.available) { status = excluded ? 'excluded' : 'none'; statusResolution = 'negative_lookup'; }

    const campBidding = campaignBiddingMap[campName] || { strategy: biddingStrategyType, target: null };
    const termStrategy = campBidding.strategy;
    const termTarget = campBidding.target || (termStrategy === 'roas' ? targetROAS : effectiveCPA);

    const termData = { term, campaign: campName, adGroup, campaignType: campType, networkType, conversions: Math.round(conversions * 100) / 100, cost: Math.round(cost * 100) / 100, cpa: cpa !== null ? Math.round(cpa * 100) / 100 : null, roas: roas !== null ? Math.round(roas * 100) / 100 : null, clicks, impressions, alreadyKeyword, status, status_resolution: statusResolution, biddingStrategy: termStrategy, campaignTarget: termTarget !== null ? Math.round(termTarget * 100) / 100 : null };

    if (status === 'unknown') {
        if (!neverExcludeTerms.has(norm(term)) && (conversions > 0 || cost >= minCostForNeg || impressions >= 50)) manualReviewUnknownStatus.push({ ...termData, note: 'manual_status_resolution_required' });
        continue;
    }
    if (status !== 'none') continue;
    if (alwaysIncludeTerms.has(norm(term)) && !addedInAdGroup) { promotionCandidates.push({ ...termData, note: 'always_include_protected' }); continue; }

    if (conversions > 0) {
        let isInefficient = false, inefficientNote = '';
        const meetsMinimums = cost >= minCostForInefficient && clicks >= minClicksForInefficient;
        if (termStrategy === 'roas' && termTarget) { const cut = termTarget * inefficientROASMultiplier; isInefficient = meetsMinimums && roas !== null && roas < cut; inefficientNote = `inefficient_roas_${roas !== null ? roas.toFixed(2) : '?'}_below_${cut.toFixed(2)}`; }
        else if (termStrategy === 'cpa' && termTarget) { const cut = termTarget * inefficientCPAMultiplier; isInefficient = meetsMinimums && cpa > cut; inefficientNote = `inefficient_cpa_above_${inefficientCPAMultiplier}x_target`; }
        const withinTarget = termStrategy === 'roas' ? (termTarget === null || (roas !== null && roas >= termTarget)) : (termTarget === null || cpa <= termTarget);
        if (!addedInAdGroup && isInefficient) inefficientCandidates.push({ ...termData, note: inefficientNote });
        else if (!addedInAdGroup && (withinTarget || termTarget === null)) promotionCandidates.push(termData);
        else if (!addedInAdGroup) monitor.push({ ...termData, note: 'converting_above_target' });
    } else if (cost >= minCostForNeg) {
        if (!neverExcludeTerms.has(norm(term))) irrelevantCandidates.push(termData);
    } else if (impressions >= 50) { monitor.push(termData); }
}

// Self-learning filter
const preFilterCount = irrelevantCandidates.length;
const filteredIrrelevants = knownRelevantSet.size > 0 ? irrelevantCandidates.filter(t => !knownRelevantSet.has(t.term.toLowerCase())) : irrelevantCandidates;
const knownRelevantFiltered = preFilterCount - filteredIrrelevants.length;

filteredIrrelevants.sort((a, b) => b.cost - a.cost);
const cappedIrrelevants = filteredIrrelevants.slice(0, 150);
inefficientCandidates.sort((a, b) => b.cost - a.cost);
const cappedInefficient = inefficientCandidates.slice(0, 100);
promotionCandidates.sort((a, b) => b.conversions - a.conversions);
monitor.sort((a, b) => b.impressions - a.impressions);
const cappedMonitor = monitor.slice(0, 30);
manualReviewUnknownStatus.sort((a, b) => b.cost - a.cost);
const cappedManualReview = manualReviewUnknownStatus.slice(0, 100);

const summary = {
    meta: {
        generatedAt: new Date().toISOString(), totalInputTerms: searchTerms.length, campaignFilter: campaignFilter || null,
        dataAgeDays, conversionLagDays, currency, currencySymbol, targetCPA, maxCPA, targetROAS,
        thresholds: { minCostForNeg, conversionLagDays, excludeBranded, biddingStrategyType, inefficientCPAMultiplier, inefficientCPACutoff: biddingStrategyType === 'cpa' && effectiveCPA ? effectiveCPA * inefficientCPAMultiplier : null, inefficientROASMultiplier, inefficientROASCutoff: biddingStrategyType === 'roas' && targetROAS ? targetROAS * inefficientROASMultiplier : null, minCostForInefficient, minClicksForInefficient },
        negativeStatus: { available: negatives.available, source: negatives.source, linkAwareShared: negatives.linkAwareShared || false, warnings: negatives.warnings || [] },
        campaignTypeBreakdown: typeBreakdown,
        counts: { promotionCandidates: promotionCandidates.length, irrelevantCandidates: filteredIrrelevants.length, irrelevantCapped: cappedIrrelevants.length, knownRelevantFiltered, manualReviewUnknownStatus: manualReviewUnknownStatus.length, manualReviewUnknownStatusCapped: cappedManualReview.length, inefficientCandidates: inefficientCandidates.length, inefficientCapped: cappedInefficient.length, monitor: monitor.length, monitorCapped: cappedMonitor.length, pmaxShopping: pmaxShoppingCount }
    },
    promotion_candidates: promotionCandidates,
    inefficient_candidates: cappedInefficient,
    irrelevant_candidates: cappedIrrelevants,
    manual_review_unknown_status: cappedManualReview,
    monitor: cappedMonitor,
    pmax_shopping_summary: { termCount: pmaxShoppingCount, totalCost: Math.round(pmaxShoppingCost * 100) / 100, campaigns: Array.from(pmaxShoppingCampaigns) },
    pmax_monitor: pmaxMonitor.sort((a, b) => b.impressions - a.impressions).slice(0, 50)
};

const outputDir = dirname(outputPath);
if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });
writeFileSync(outputPath, JSON.stringify(summary, null, 2), 'utf8');

console.log(`Analysis summary written to: ${outputPath}`);
console.log(`  Terms processed: ${searchTerms.length}`);
console.log(`  Promotion candidates: ${promotionCandidates.length}`);
const ineffLabel = biddingStrategyType === 'roas' ? `ROAS < ${targetROAS ? (targetROAS * inefficientROASMultiplier).toFixed(2) : '?'}` : `CPA > ${currencySymbol}${effectiveCPA ? effectiveCPA * inefficientCPAMultiplier : '?'}`;
console.log(`  Inefficient candidates: ${cappedInefficient.length} (of ${inefficientCandidates.length} total, ${ineffLabel}, cost >= ${currencySymbol}${minCostForInefficient}, clicks >= ${minClicksForInefficient})`);
console.log(`  Irrelevant candidates: ${cappedIrrelevants.length} (of ${filteredIrrelevants.length} total, capped at 150)${knownRelevantFiltered > 0 ? ` [${knownRelevantFiltered} filtered by decisions file]` : ''}`);
console.log(`  Unknown status (manual review): ${cappedManualReview.length} (of ${manualReviewUnknownStatus.length} total)`);
console.log(`  Monitor: ${cappedMonitor.length} (of ${monitor.length} total, capped at 30)`);
console.log(`  PMax/Shopping terms: ${pmaxShoppingCount} (excluded from SOP 1/2)`);
console.log(`  PMax monitor (0-conv, 50+ impr): ${pmaxMonitor.length}`);

// --- Export CSVs ---
if (exportFlag) {
    const exportDir = resolve(dataDir, '../exports');
    if (!existsSync(exportDir)) mkdirSync(exportDir, { recursive: true });
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const ts = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}_${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;
    const rawPrimary = sta.sharedNegativeLists?.primary || 'Search Term Exclusions';
    const sharedListName = Array.isArray(rawPrimary) ? rawPrimary[0] : rawPrimary;
    const matchType = sta.negativeMatchType || 'Phrase';

    if (cappedIrrelevants.length > 0) {
        const rows = cappedIrrelevants.map(t => `"${sharedListName}","${t.term}","${matchType}"`);
        writeFileSync(resolve(exportDir, `${ts}_account_negatives.csv`), ['Shared Set,Keyword,Match Type', ...rows].join('\n'), 'utf8');
        console.log(`  Exported: exports/${ts}_account_negatives.csv (${cappedIrrelevants.length} terms)`);
    } else { console.log(`  Account negatives: skipped (0 confirmed irrelevant terms)`); }

    if (pmaxMonitor.length > 0) {
        const pmaxCampName = Array.from(pmaxShoppingCampaigns).find(n => /performance max/i.test(n)) || Array.from(pmaxShoppingCampaigns)[0] || 'Performance Max';
        const rows = pmaxMonitor.map(t => `"${pmaxCampName}","${t.term}","${matchType}"`);
        writeFileSync(resolve(exportDir, `${ts}_pmax_monitor_negatives.csv`), ['Campaign,Keyword,Match Type', ...rows].join('\n'), 'utf8');
        console.log(`  Exported: exports/${ts}_pmax_monitor_negatives.csv (${pmaxMonitor.length} terms -- review before importing)`);
    }
}
