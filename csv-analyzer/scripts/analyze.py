#!/usr/bin/env python3
"""
CSV Analyzer - Cowork Skill
Analyzes any CSV file and generates a self-contained HTML report with
embedded charts, statistics, and insights.

Auto-detects data type (Google Ads, cross-channel marketing, P&L/financial,
sales, survey, etc.) and adapts the analysis accordingly.

Specialized modes:
  - Cross-Channel Marketing Report (multi-platform campaign data)
  - CFO Financial Dashboard (P&L and financial data)
  - Google Ads (campaign/ad group performance)
  - Generic (any tabular data)

Usage:
    python3 analyze.py /path/to/data.csv
    python3 analyze.py /path/to/data.csv --output /path/to/report.html
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import base64
import io
import sys
import glob
import html
import re

# -- Style config --
sns.set_style('whitegrid')
plt.rcParams.update({
    'figure.dpi': 150,
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 11,
    'figure.facecolor': '#FFFFFF',
    'axes.facecolor': '#FAFAFA',
    'savefig.facecolor': '#FFFFFF',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Colour palette for charts - mode-specific primaries
COLORS = ['#2563EB', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
          '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1']

# Specialized mode colours
MODE_COLORS = {
    'marketing': ['#D64C00', '#2563eb', '#16a34a', '#7c3aed', '#F59E0B', '#EF4444'],
    'financial': ['#D64C00', '#2563eb', '#16a34a', '#7c3aed', '#F59E0B', '#EF4444'],
}


# ---------------------------------------------------------------------------
# File finding helpers
# ---------------------------------------------------------------------------

def find_csv_file(file_path):
    """Robustly find a CSV file, handling spaces and fuzzy matching."""
    path = Path(file_path).expanduser()
    if path.exists():
        return str(path)

    parent = path.parent
    if parent.exists():
        search_pattern = f"{parent}/*.csv"
        matching_files = glob.glob(search_pattern)
        name_lower = path.stem.lower().replace('-', ' ')
        for candidate in matching_files:
            candidate_name = Path(candidate).stem.lower().replace('-', ' ')
            if name_lower in candidate_name or candidate_name in name_lower:
                print(f"Found file: {candidate}")
                return candidate

    raise FileNotFoundError(f"Could not find CSV file: {file_path}")


def detect_google_ads_format(file_path):
    """Detect Google Ads export header rows to skip. Returns int."""
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if 'report' in first_line.lower():
            second_line = f.readline().strip()
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
            if any(m in second_line for m in months):
                return 2, first_line, second_line
    return 0, None, None


# ---------------------------------------------------------------------------
# Data detection - enhanced with marketing and financial modes
# ---------------------------------------------------------------------------

def detect_data_type(df):
    """Classify the dataset into a broad data type for tailored analysis."""
    cols_lower = [c.lower() for c in df.columns]
    col_str = ' '.join(cols_lower)

    # Google Ads - check FIRST using Google Ads-specific column names that
    # never appear in generic marketing data.
    ads_specific = ['ad group', 'impr.', 'conv.', 'ad group status', 'ad group type']
    ads_general = ['campaign', 'clicks', 'impressions', 'cpc', 'ctr', 'cost', 'conversions']
    has_ads_specific = sum(1 for s in ads_specific if s in col_str) >= 1
    has_ads_general = sum(1 for s in ads_general if s in col_str) >= 2
    if has_ads_specific and has_ads_general:
        return 'google_ads'

    # Cross-Channel Marketing - needs an actual column NAMED channel/platform/source/medium.
    # We match against individual column names (not the joined string) to avoid false
    # positives from words like "platform" appearing inside other column names.
    channel_col_names = {'channel', 'platform', 'source', 'medium', 'network',
                         'campaign_type', 'ad_platform', 'traffic_source',
                         'ad platform', 'traffic source', 'campaign type'}
    has_channel = any(c in channel_col_names for c in cols_lower)
    marketing_signals = ['spend', 'cost', 'clicks', 'impressions', 'conversions',
                         'cpa', 'roas', 'ctr', 'revenue', 'leads', 'cpc',
                         'cost_per', 'conversion_rate', 'return_on']
    has_marketing = sum(1 for s in marketing_signals if s in col_str) >= 2
    if has_channel and has_marketing:
        return 'marketing'

    # CFO Financial / P&L
    revenue_signals = ['revenue', 'sales', 'income', 'top_line', 'total_revenue',
                       'gross_revenue', 'net_revenue']
    expense_signals = ['expense', 'cost', 'cogs', 'cost_of_goods', 'payroll',
                       'rent', 'utilities', 'operating_expense', 'opex',
                       'marketing_expense', 'sga']
    profit_signals = ['profit', 'net_income', 'operating_income', 'ebitda',
                      'gross_profit', 'net_profit', 'bottom_line']
    margin_signals = ['margin', 'gross_margin', 'operating_margin', 'net_margin',
                      'profit_margin']
    fin_score = 0
    if sum(1 for s in revenue_signals if s in col_str) >= 1:
        fin_score += 1
    if sum(1 for s in expense_signals if s in col_str) >= 1:
        fin_score += 1
    if sum(1 for s in profit_signals if s in col_str) >= 1:
        fin_score += 1
    if sum(1 for s in margin_signals if s in col_str) >= 1:
        fin_score += 1
    if fin_score >= 2:
        return 'financial'

    # Sales / e-commerce
    sales_signals = ['revenue', 'order', 'product', 'quantity', 'price', 'sku',
                     'transaction', 'purchase', 'item']
    if sum(1 for s in sales_signals if s in col_str) >= 2:
        return 'sales'

    # Survey
    survey_signals = ['response', 'rating', 'score', 'satisfaction',
                      'agree', 'disagree', 'survey']
    if sum(1 for s in survey_signals if s in col_str) >= 2:
        return 'survey'

    return 'generic'


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

def clean_numeric_columns(df):
    """Clean currency symbols, commas, percentages from object columns."""
    for col in df.columns:
        if df[col].dtype != 'object':
            continue
        sample = df[col].dropna().astype(str).head(100)
        # Columns that look numeric with commas / currency
        if sample.str.match(r'^[\s$£€]*-?[\d,]+\.?\d*\s*%?$').mean() > 0.5:
            cleaned = (df[col].astype(str)
                       .str.replace(',', '', regex=False)
                       .str.replace('$', '', regex=False)
                       .str.replace('£', '', regex=False)
                       .str.replace('€', '', regex=False)
                       .str.replace('%', '', regex=False)
                       .str.replace('--', '', regex=False)
                       .str.strip())
            converted = pd.to_numeric(cleaned, errors='coerce')
            if converted.notna().mean() > 0.5:
                df[col] = converted


def detect_date_columns(df):
    """Try to parse object columns that look like dates."""
    date_cols = []
    for col in df.columns:
        if df[col].dtype == 'object' and ('date' in col.lower() or 'time' in col.lower()
                                           or 'month' in col.lower() or 'week' in col.lower()
                                           or 'period' in col.lower() or 'year' in col.lower()):
            try:
                parsed = pd.to_datetime(df[col], errors='coerce')
                if parsed.notna().mean() > 0.5:
                    df[col] = parsed
                    date_cols.append(col)
            except Exception:
                pass
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
    return date_cols


def find_time_column(df, date_cols):
    """Find the best column to use as a time axis (date col or month/week string)."""
    if date_cols:
        return date_cols[0]
    # Look for month/week/period columns that aren't datetime but are ordered
    for col in df.columns:
        cl = col.lower()
        if cl in ('month', 'week', 'period', 'quarter', 'date', 'year'):
            return col
    return None


def find_column(df, candidates, partial=True):
    """Find the first column matching any of the candidate names (case-insensitive)."""
    cols_lower = {c.lower().replace(' ', '_'): c for c in df.columns}
    for cand in candidates:
        cand_clean = cand.lower().replace(' ', '_')
        if cand_clean in cols_lower:
            return cols_lower[cand_clean]
        if partial:
            for cl, orig in cols_lower.items():
                if cand_clean in cl or cl in cand_clean:
                    return orig
    return None


# ---------------------------------------------------------------------------
# Chart helpers (return base64 PNG strings)
# ---------------------------------------------------------------------------

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def make_correlation_heatmap(df, numeric_cols):
    if len(numeric_cols) < 2:
        return None
    corr = df[numeric_cols].corr()
    fig, ax = plt.subplots(figsize=(max(8, len(numeric_cols)*0.9),
                                    max(6, len(numeric_cols)*0.7)))
    sns.heatmap(corr, annot=True, fmt='.2f', cmap='RdBu_r', center=0,
                square=True, linewidths=0.5, ax=ax,
                cbar_kws={'shrink': 0.8})
    ax.set_title('Correlation Heatmap')
    return fig_to_base64(fig)


def make_distribution_plots(df, numeric_cols):
    cols = numeric_cols[:6]
    n = len(cols)
    if n == 0:
        return None
    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5*ncols, 4*nrows))
    if n == 1:
        axes = [axes]
    else:
        axes = axes.flatten()
    for i, col in enumerate(cols):
        data = df[col].dropna()
        axes[i].hist(data, bins=min(30, max(10, len(data)//20)),
                     color=COLORS[i % len(COLORS)], edgecolor='white', alpha=0.85)
        axes[i].set_title(col)
        axes[i].set_ylabel('Frequency')
        axes[i].grid(True, alpha=0.3)
    for j in range(len(cols), len(axes)):
        axes[j].set_visible(False)
    fig.suptitle('Numeric Distributions', fontsize=14, fontweight='bold', y=1.02)
    fig.tight_layout()
    return fig_to_base64(fig)


def make_categorical_plots(df, cat_cols):
    cols = cat_cols[:4]
    if not cols:
        return None
    n = len(cols)
    fig, axes = plt.subplots(1, n, figsize=(5*n, max(5, 3)))
    if n == 1:
        axes = [axes]
    for i, col in enumerate(cols):
        vc = df[col].value_counts().head(10)
        axes[i].barh(range(len(vc)), vc.values, color=COLORS[i % len(COLORS)])
        axes[i].set_yticks(range(len(vc)))
        labels = [str(v)[:30] for v in vc.index]
        axes[i].set_yticklabels(labels, fontsize=9)
        axes[i].set_title(f'Top values: {col}', fontsize=11)
        axes[i].set_xlabel('Count')
        axes[i].invert_yaxis()
        axes[i].grid(True, alpha=0.3, axis='x')
    fig.tight_layout()
    return fig_to_base64(fig)


def make_timeseries_plots(df, date_col, numeric_cols):
    cols = numeric_cols[:4]
    if not cols:
        return None
    n = len(cols)
    fig, axes = plt.subplots(n, 1, figsize=(12, 3.5*n))
    if n == 1:
        axes = [axes]
    for i, col in enumerate(cols):
        daily = df.groupby(date_col)[col].mean()
        axes[i].plot(daily.index, daily.values, color=COLORS[i % len(COLORS)],
                     linewidth=2)
        axes[i].set_title(f'{col} over time (daily average)')
        axes[i].set_ylabel(col)
        axes[i].grid(True, alpha=0.3)
    fig.tight_layout()
    return fig_to_base64(fig)


def make_google_ads_charts(df, enabled_df):
    """Generate Google Ads-specific charts. Returns list of (title, b64)."""
    charts = []

    # Top ad groups by spend
    if 'Cost' in enabled_df.columns and 'Ad group' in enabled_df.columns:
        top_spend = enabled_df.nlargest(15, 'Cost')
        if len(top_spend) > 0:
            fig, ax = plt.subplots(figsize=(12, max(6, len(top_spend)*0.45)))
            has_conv = top_spend.get('Conversions', pd.Series([0]*len(top_spend)))
            colors = ['#10B981' if c > 0 else '#EF4444' for c in has_conv]
            ax.barh(range(len(top_spend)), top_spend['Cost'], color=colors)
            ax.set_yticks(range(len(top_spend)))
            labels = [str(n)[:40] for n in top_spend['Ad group']]
            ax.set_yticklabels(labels, fontsize=9)
            ax.set_xlabel('Cost')
            ax.set_title('Top Ad Groups by Spend (green = has conversions, red = none)',
                         fontsize=13, fontweight='bold')
            ax.invert_yaxis()
            ax.grid(True, alpha=0.3, axis='x')
            fig.tight_layout()
            charts.append(('Top Ad Groups by Spend', fig_to_base64(fig)))

    # Campaign performance
    if 'Campaign' in enabled_df.columns and 'Cost' in enabled_df.columns:
        agg_cols = {}
        for c in ['Cost', 'Clicks', 'Conversions', 'Conv. value', 'Impr.']:
            if c in enabled_df.columns:
                agg_cols[c] = 'sum'
        if agg_cols:
            camp = enabled_df.groupby('Campaign').agg(agg_cols)
            if 'Conv. value' in camp.columns and 'Cost' in camp.columns:
                camp['ROAS'] = camp['Conv. value'] / camp['Cost'].replace(0, np.nan)
            metrics = [c for c in ['Cost', 'Conversions', 'ROAS'] if c in camp.columns]
            if metrics:
                n = len(metrics)
                fig, axes = plt.subplots(1, n, figsize=(5*n, 5))
                if n == 1:
                    axes = [axes]
                for i, m in enumerate(metrics):
                    camp[m].plot(kind='bar', ax=axes[i], color=COLORS[i])
                    axes[i].set_title(m, fontsize=12, fontweight='bold')
                    axes[i].tick_params(axis='x', rotation=45)
                    axes[i].grid(True, alpha=0.3, axis='y')
                    if m == 'ROAS':
                        axes[i].axhline(y=1.0, color='red', linestyle='--',
                                        linewidth=1, label='Break-even')
                        axes[i].legend(fontsize=9)
                fig.suptitle('Performance by Campaign', fontsize=14, fontweight='bold')
                fig.tight_layout()
                charts.append(('Campaign Performance', fig_to_base64(fig)))

    # Cost vs Conversions scatter
    if all(c in enabled_df.columns for c in ['Cost', 'Conversions']):
        scatter_data = enabled_df[enabled_df['Cost'] > 0].copy()
        if len(scatter_data) > 0:
            fig, ax = plt.subplots(figsize=(10, 7))
            size_col = scatter_data.get('Conv. value', scatter_data['Cost'])
            sizes = np.clip(size_col.fillna(1) * 2, 20, 500)
            scatter = ax.scatter(scatter_data['Cost'], scatter_data['Conversions'],
                                 s=sizes, alpha=0.6, c=COLORS[0],
                                 edgecolors='white', linewidth=0.5)
            # Label top performers
            if 'Ad group' in scatter_data.columns:
                for _, row in scatter_data.nlargest(5, 'Conversions').iterrows():
                    ax.annotate(str(row['Ad group'])[:25],
                                (row['Cost'], row['Conversions']),
                                xytext=(8, 8), textcoords='offset points',
                                fontsize=8, alpha=0.8,
                                bbox=dict(boxstyle='round,pad=0.3',
                                          facecolor='#FEF3C7', alpha=0.6))
            ax.set_xlabel('Cost')
            ax.set_ylabel('Conversions')
            ax.set_title('Cost vs Conversions', fontsize=13, fontweight='bold')
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            charts.append(('Cost vs Conversions', fig_to_base64(fig)))

    return charts


# ---------------------------------------------------------------------------
# Cross-Channel Marketing charts and analysis
# ---------------------------------------------------------------------------

def make_channel_comparison_chart(df, channel_col, metrics):
    """Grouped bar chart comparing key metrics across channels."""
    mc = MODE_COLORS['marketing']
    available_metrics = [m for m in metrics if m in df.columns]
    if not available_metrics or not channel_col:
        return None

    channel_data = df.groupby(channel_col)[available_metrics].sum().reset_index()
    n_metrics = len(available_metrics)
    n_channels = len(channel_data)

    fig, axes = plt.subplots(1, n_metrics, figsize=(5 * n_metrics, 5))
    if n_metrics == 1:
        axes = [axes]

    for i, metric in enumerate(available_metrics):
        vals = channel_data[metric].values
        labels = [str(v)[:15] for v in channel_data[channel_col].values]
        bars = axes[i].bar(range(n_channels), vals, color=mc[:n_channels])
        axes[i].set_xticks(range(n_channels))
        axes[i].set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        axes[i].set_title(metric, fontsize=12, fontweight='bold')
        axes[i].grid(True, alpha=0.3, axis='y')
        # Add value labels on bars
        for bar, val in zip(bars, vals):
            try:
                if float(val) > 0:
                    label = f'{float(val):,.0f}' if float(val) > 10 else f'{float(val):,.2f}'
                    axes[i].text(bar.get_x() + bar.get_width() / 2., bar.get_height(),
                                 label, ha='center', va='bottom', fontsize=8, fontweight='bold')
            except (ValueError, TypeError):
                pass

    fig.suptitle('Channel Comparison', fontsize=14, fontweight='bold')
    fig.tight_layout()
    return fig_to_base64(fig)


def make_channel_trend_chart(df, channel_col, time_col, metric_col):
    """Line chart showing each channel's trajectory over time."""
    mc = MODE_COLORS['marketing']
    if not all(c and c in df.columns for c in [channel_col, metric_col]):
        return None
    if time_col not in df.columns:
        return None

    channels = df[channel_col].unique()
    fig, ax = plt.subplots(figsize=(12, 6))

    for i, ch in enumerate(channels):
        ch_data = df[df[channel_col] == ch].sort_values(time_col)
        ax.plot(ch_data[time_col], ch_data[metric_col],
                color=mc[i % len(mc)], linewidth=2.5, marker='o',
                markersize=6, label=str(ch)[:20])
        # Annotate trend direction on last point
        if len(ch_data) >= 2:
            last_val = ch_data[metric_col].iloc[-1]
            prev_val = ch_data[metric_col].iloc[-2]
            if prev_val > 0:
                pct_change = ((last_val - prev_val) / prev_val) * 100
                arrow = "^" if pct_change > 0 else "v"
                color = '#16a34a' if pct_change > 0 else '#EF4444'
                ax.annotate(f'{arrow} {pct_change:+.1f}%',
                            (ch_data[time_col].iloc[-1], last_val),
                            xytext=(10, 5), textcoords='offset points',
                            fontsize=9, fontweight='bold', color=color)

    ax.set_title(f'{metric_col} by Channel Over Time', fontsize=13, fontweight='bold')
    ax.set_ylabel(metric_col)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    fig.tight_layout()
    return fig_to_base64(fig)


def detect_anomalies(df, channel_col, time_col, metric_cols):
    """Find values exceeding 2 standard deviations from the channel mean."""
    anomalies = []
    for metric in metric_cols:
        if metric not in df.columns:
            continue
        for ch in df[channel_col].unique():
            ch_data = df[df[channel_col] == ch].sort_values(time_col)
            if len(ch_data) < 3:
                continue
            vals = ch_data[metric].values
            mean = np.mean(vals)
            std = np.std(vals)
            if std == 0:
                continue
            for idx, row in ch_data.iterrows():
                val = row[metric]
                z_score = abs((val - mean) / std)
                if z_score > 2:
                    direction = 'spike' if val > mean else 'drop'
                    anomalies.append({
                        'channel': str(ch),
                        'period': str(row[time_col]),
                        'metric': metric,
                        'value': val,
                        'expected_range': f'{mean - 2*std:,.1f} to {mean + 2*std:,.1f}',
                        'z_score': z_score,
                        'direction': direction,
                    })
    return anomalies


def build_budget_reallocation(df, channel_col, spend_col, conv_col):
    """Calculate efficiency ratios and recommend budget moves."""
    if not all(c and c in df.columns for c in [channel_col, spend_col, conv_col]):
        return None

    channel_perf = df.groupby(channel_col).agg({
        spend_col: 'sum',
        conv_col: 'sum',
    }).reset_index()

    channel_perf['CPA'] = channel_perf[spend_col] / channel_perf[conv_col].replace(0, np.nan)
    channel_perf = channel_perf.dropna(subset=['CPA'])
    channel_perf = channel_perf.sort_values('CPA')

    if len(channel_perf) < 2:
        return None

    best = channel_perf.iloc[0]
    worst = channel_perf.iloc[-1]
    realloc_amount = worst[spend_col] * 0.2  # Move 20% of worst performer's budget
    projected_extra_conv = realloc_amount / best['CPA']

    return {
        'table': channel_perf,
        'best_channel': str(best[channel_col]),
        'worst_channel': str(worst[channel_col]),
        'best_cpa': best['CPA'],
        'worst_cpa': worst['CPA'],
        'move_amount': realloc_amount,
        'projected_extra_conv': projected_extra_conv,
        'spend_col': spend_col,
        'conv_col': conv_col,
    }


def generate_marketing_summary(df, channel_col, spend_col, conv_col, realloc):
    """Generate a 3-paragraph executive summary for client email."""
    total_spend = df[spend_col].sum() if spend_col and spend_col in df.columns else 0
    total_conv = df[conv_col].sum() if conv_col and conv_col in df.columns else 0
    blended_cpa = total_spend / total_conv if total_conv > 0 else 0

    # Find ROAS column if present
    roas_col = find_column(df, ['roas', 'return_on_ad_spend'])
    blended_roas = df[roas_col].mean() if roas_col and roas_col in df.columns else None

    n_channels = df[channel_col].nunique() if channel_col and channel_col in df.columns else 0

    para1 = (f"Across {n_channels} channels, total spend was ${total_spend:,.0f} "
             f"generating {total_conv:,.0f} conversions at a blended CPA of ${blended_cpa:,.2f}.")
    if blended_roas is not None:
        para1 += f" Average ROAS across channels was {blended_roas:.2f}x."

    if realloc:
        para2 = (f"The standout finding is the efficiency gap between {realloc['best_channel']} "
                 f"(CPA: ${realloc['best_cpa']:,.2f}) and {realloc['worst_channel']} "
                 f"(CPA: ${realloc['worst_cpa']:,.2f}). Reallocating ${realloc['move_amount']:,.0f}/mo "
                 f"from {realloc['worst_channel']} to {realloc['best_channel']} could yield "
                 f"an additional {realloc['projected_extra_conv']:,.0f} conversions at a lower cost.")
    else:
        para2 = "Channel efficiency appears relatively balanced, with no single channel significantly underperforming the others."

    para3 = ("Recommended next steps: (1) Implement the budget reallocation above for the next 30 days and measure impact. "
             "(2) Investigate any anomalies flagged in this report. "
             "(3) Review creative performance on declining channels to identify refresh opportunities.")

    return f"{para1}\n\n{para2}\n\n{para3}"


# ---------------------------------------------------------------------------
# CFO Financial Dashboard charts and analysis
# ---------------------------------------------------------------------------

def make_revenue_profit_chart(df, time_col, revenue_col, profit_col):
    """Dual-axis chart: revenue bars + profit line with growth rate annotations."""
    mc = MODE_COLORS['financial']
    if not all(c and c in df.columns for c in [revenue_col, profit_col]):
        return None

    data = df.sort_values(time_col) if time_col and time_col in df.columns else df.copy()
    if time_col and time_col in data.columns:
        labels = [str(v)[:10] for v in data[time_col].values]
    else:
        labels = [str(i) for i in range(len(data))]

    fig, ax1 = plt.subplots(figsize=(12, 6))
    x = range(len(data))

    # Revenue bars
    bars = ax1.bar(x, data[revenue_col].values, color=mc[0], alpha=0.7, label='Revenue', width=0.6)
    ax1.set_ylabel('Revenue', color=mc[0], fontsize=12)
    ax1.tick_params(axis='y', labelcolor=mc[0])

    # Annotate revenue growth rates
    rev_vals = data[revenue_col].values
    for i in range(1, len(rev_vals)):
        if rev_vals[i - 1] > 0:
            growth = ((rev_vals[i] - rev_vals[i - 1]) / rev_vals[i - 1]) * 100
            color = '#16a34a' if growth >= 0 else '#EF4444'
            ax1.text(i, rev_vals[i], f'{growth:+.1f}%',
                     ha='center', va='bottom', fontsize=7, color=color, fontweight='bold')

    # Profit line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(x, data[profit_col].values, color=mc[1], linewidth=2.5,
             marker='o', markersize=6, label='Net Profit')
    ax2.set_ylabel('Net Profit', color=mc[1], fontsize=12)
    ax2.tick_params(axis='y', labelcolor=mc[1])

    # Annotate profit growth rates
    prof_vals = data[profit_col].values
    for i in range(1, len(prof_vals)):
        if prof_vals[i - 1] != 0:
            growth = ((prof_vals[i] - prof_vals[i - 1]) / prof_vals[i - 1]) * 100
            color = '#16a34a' if growth >= 0 else '#EF4444'
            ax2.text(i, prof_vals[i], f'{growth:+.1f}%',
                     ha='center', va='bottom', fontsize=7, color=color, fontweight='bold')

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax1.set_title('Revenue & Profit Trends', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)

    fig.tight_layout()
    return fig_to_base64(fig)


def make_expense_breakdown_chart(df, time_col, expense_cols, revenue_col):
    """Stacked area chart of expense categories as % of revenue."""
    mc = MODE_COLORS['financial']
    if not expense_cols or not revenue_col or revenue_col not in df.columns:
        return None

    valid_cols = [c for c in expense_cols if c in df.columns]
    if not valid_cols:
        return None

    data = df.sort_values(time_col) if time_col and time_col in df.columns else df.copy()
    if time_col and time_col in data.columns:
        labels = [str(v)[:10] for v in data[time_col].values]
    else:
        labels = [str(i) for i in range(len(data))]

    # Calculate as % of revenue
    pct_data = pd.DataFrame()
    for col in valid_cols:
        pct_data[col] = (data[col].values / data[revenue_col].replace(0, np.nan).values) * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(data))
    ax.stackplot(x, *[pct_data[c].fillna(0).values for c in valid_cols],
                 labels=[str(c)[:20] for c in valid_cols],
                 colors=mc[:len(valid_cols)], alpha=0.8)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('% of Revenue')
    ax.set_title('Expense Categories as % of Revenue', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    fig.tight_layout()
    return fig_to_base64(fig)


def make_margin_trends_chart(df, time_col, margin_cols):
    """Three-line chart showing gross, operating, and net margin over time."""
    mc = MODE_COLORS['financial']
    valid_cols = [c for c in margin_cols if c in df.columns]
    if not valid_cols:
        return None

    data = df.sort_values(time_col) if time_col and time_col in df.columns else df.copy()
    if time_col and time_col in data.columns:
        labels = [str(v)[:10] for v in data[time_col].values]
    else:
        labels = [str(i) for i in range(len(data))]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(data))

    margin_names = {'gross_margin': 'Gross Margin', 'operating_margin': 'Operating Margin',
                    'net_margin': 'Net Margin'}

    for i, col in enumerate(valid_cols):
        vals = data[col].values
        display_name = margin_names.get(col.lower().replace(' ', '_'), col)
        ax.plot(x, vals, color=mc[i % len(mc)], linewidth=2.5, marker='o',
                markersize=5, label=display_name)
        # Annotate start and end values
        if len(vals) > 0:
            ax.annotate(f'{vals[0]:.1f}%', (0, vals[0]),
                        xytext=(-30, 10), textcoords='offset points',
                        fontsize=8, color=mc[i % len(mc)], fontweight='bold')
            ax.annotate(f'{vals[-1]:.1f}%', (len(vals) - 1, vals[-1]),
                        xytext=(5, 10), textcoords='offset points',
                        fontsize=8, color=mc[i % len(mc)], fontweight='bold')

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Margin %')
    ax.set_title('Margin Trends', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # Add healthy/concerning bands
    ax.axhspan(10, ax.get_ylim()[1], alpha=0.05, color='#16a34a')
    ax.axhspan(5, 10, alpha=0.05, color='#F59E0B')
    ax.axhspan(ax.get_ylim()[0], 5, alpha=0.05, color='#EF4444')

    fig.tight_layout()
    return fig_to_base64(fig)


def make_cash_flow_chart(df, time_col, cash_col):
    """Running cash balance chart with projected runway."""
    if not cash_col or cash_col not in df.columns:
        return None

    data = df.sort_values(time_col) if time_col and time_col in df.columns else df.copy()
    if time_col and time_col in data.columns:
        labels = [str(v)[:10] for v in data[time_col].values]
    else:
        labels = [str(i) for i in range(len(data))]

    vals = data[cash_col].values
    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(data))

    # Colour the line green if trending up, red if trending down
    if len(vals) >= 2:
        trend_up = vals[-1] >= vals[0]
    else:
        trend_up = True

    color = '#16a34a' if trend_up else '#EF4444'
    ax.fill_between(x, vals, alpha=0.15, color=color)
    ax.plot(x, vals, color=color, linewidth=2.5, marker='o', markersize=5)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Cash Balance')
    ax.set_title('Cash Flow Trend', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig_to_base64(fig)


def calculate_financial_health(df, margin_cols, revenue_col):
    """Determine traffic-light status based on margins and revenue trends."""
    # Find net margin column (prefer net > operating > gross)
    net_margin_col = None
    for candidate in ['net_margin', 'net margin', 'operating_margin', 'operating margin',
                      'gross_margin', 'gross margin']:
        col = find_column(df, [candidate], partial=True)
        if col:
            net_margin_col = col
            break

    if not net_margin_col and margin_cols:
        net_margin_col = margin_cols[-1]  # Use last margin col (likely most "net")

    status = 'green'
    reasons = []

    if net_margin_col and net_margin_col in df.columns:
        margins = df[net_margin_col].dropna().values
        if len(margins) >= 2:
            latest = margins[-1]
            # Check margin level
            if latest < 5:
                status = 'red'
                reasons.append(f'Net margin is {latest:.1f}%, below 5% threshold')
            elif latest < 10:
                if status != 'red':
                    status = 'amber'
                reasons.append(f'Net margin is {latest:.1f}%, in the 5-10% caution zone')

            # Check margin trend (last 3+ periods)
            if len(margins) >= 3:
                recent = margins[-3:]
                declining = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))
                if declining:
                    status = 'red' if len(margins) >= 4 else 'amber'
                    reasons.append(f'Margins declining for {len(recent)} consecutive periods')
        elif len(margins) == 1:
            latest = margins[0]
            if latest < 5:
                status = 'red'
                reasons.append(f'Net margin is {latest:.1f}%')
            elif latest < 10:
                status = 'amber'
                reasons.append(f'Net margin is {latest:.1f}%')

    if revenue_col and revenue_col in df.columns:
        rev = df[revenue_col].dropna().values
        if len(rev) >= 2:
            rev_growth = ((rev[-1] - rev[0]) / rev[0]) * 100 if rev[0] > 0 else 0
            if rev_growth < 0:
                if status != 'red':
                    status = 'amber'
                reasons.append(f'Revenue declining ({rev_growth:+.1f}% over period)')
            else:
                reasons.append(f'Revenue growing ({rev_growth:+.1f}% over period)')

    if not reasons:
        reasons = ['Insufficient data to assess financial health']
        status = 'amber'

    status_labels = {
        'green': 'HEALTHY',
        'amber': 'WATCH CLOSELY',
        'red': 'ACTION NEEDED',
    }

    return {
        'status': status,
        'label': status_labels[status],
        'reasons': reasons,
    }


def generate_financial_actions(df, revenue_col, expense_cols, margin_cols, health):
    """Generate 3 prioritized action items with projected financial impact."""
    actions = []

    # Action 1: Fastest-growing expense category
    if expense_cols and revenue_col and revenue_col in df.columns:
        growth_rates = {}
        for col in expense_cols:
            if col in df.columns:
                vals = df[col].dropna().values
                if len(vals) >= 2 and vals[0] > 0:
                    growth = ((vals[-1] - vals[0]) / vals[0]) * 100
                    growth_rates[col] = growth

        if growth_rates:
            fastest = max(growth_rates, key=growth_rates.get)
            rate = growth_rates[fastest]
            monthly_val = df[fastest].iloc[-1] if fastest in df.columns else 0
            saving_pct = 15
            annual_saving = monthly_val * (saving_pct / 100) * 12
            actions.append(
                f"Review and renegotiate {fastest} (${monthly_val:,.0f}/mo, growing at {rate:+.1f}%). "
                f"A {saving_pct}% reduction would save ~${annual_saving:,.0f}/year."
            )

    # Action 2: Margin improvement
    if margin_cols:
        last_margin_col = margin_cols[-1]
        if last_margin_col in df.columns:
            current_margin = df[last_margin_col].iloc[-1]
            target_margin = current_margin + 2
            rev_latest = df[revenue_col].iloc[-1] if revenue_col and revenue_col in df.columns else 0
            impact = rev_latest * 0.02 if rev_latest > 0 else 0
            actions.append(
                f"Target a {target_margin:.1f}% margin (up from {current_margin:.1f}%) "
                f"by addressing the fastest-growing cost categories above. "
                f"Each 2-point margin improvement adds ~${impact:,.0f}/mo to the bottom line."
            )

    # Action 3: Revenue growth or diversification
    if revenue_col and revenue_col in df.columns:
        rev = df[revenue_col].dropna().values
        if len(rev) >= 2:
            avg_growth = ((rev[-1] - rev[0]) / rev[0]) * 100 / max(len(rev) - 1, 1)
            if avg_growth < 5:
                actions.append(
                    f"Revenue growth averaging {avg_growth:.1f}%/period is below healthy levels. "
                    f"Prioritize customer acquisition or pricing strategy review. "
                    f"A 10% revenue increase at current margins would add ~${rev[-1] * 0.10:,.0f}/mo."
                )
            else:
                actions.append(
                    f"Revenue growth is solid at {avg_growth:.1f}%/period. "
                    f"Focus on maintaining this trajectory while protecting margins. "
                    f"Sustained growth at this rate projects ${rev[-1] * (1 + avg_growth/100)**3:,.0f}/mo within 3 periods."
                )

    while len(actions) < 3:
        actions.append("Implement monthly financial review cadence to track progress against these recommendations.")

    return actions[:3]


def generate_financial_narrative(df, revenue_col, profit_col, margin_cols, health, actions):
    """Plain-English narrative explaining what the numbers mean."""
    parts = []

    # Where we are now
    if revenue_col and revenue_col in df.columns:
        latest_rev = df[revenue_col].iloc[-1]
        parts.append(
            f"The business is currently generating ${latest_rev:,.0f} in revenue per period."
        )
    if profit_col and profit_col in df.columns:
        latest_profit = df[profit_col].iloc[-1]
        if latest_profit > 0:
            parts.append(f"After all expenses, ${latest_profit:,.0f} drops to the bottom line.")
        else:
            parts.append(f"The business is currently operating at a ${abs(latest_profit):,.0f} loss.")

    # Direction
    status_narratives = {
        'green': "The overall financial trajectory is positive.",
        'amber': "There are signals that need attention, though the situation is not critical yet.",
        'red': "The financial data is showing concerning trends that need immediate action.",
    }
    parts.append(status_narratives.get(health['status'], ''))
    for reason in health['reasons']:
        parts.append(f"Specifically: {reason}.")

    # What to do about it
    parts.append(
        "The three action items above are prioritized by potential financial impact. "
        "Start with the first one this month, and review progress at the next monthly check-in."
    )

    return ' '.join(parts)


# ---------------------------------------------------------------------------
# HTML report generator
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSV Analysis Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #FAFAF8;
    color: #1a1a1a;
    line-height: 1.6;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.25rem;
    color: #111;
    border-bottom: 3px solid #2563EB;
    padding-bottom: 0.5rem;
  }}
  h1.mode-marketing {{
    border-bottom-color: #D64C00;
  }}
  h1.mode-financial {{
    border-bottom-color: #2563eb;
  }}
  .subtitle {{
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 2rem;
  }}
  h2 {{
    font-size: 1.3rem;
    color: #1e3a5f;
    margin: 2rem 0 1rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #e0e0e0;
  }}
  .card {{
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 2px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }}
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }}
  .metric {{
    background: #fff;
    border: 1px solid #e0e0e0;
    border-left: 3px solid #2563EB;
    border-radius: 2px;
    padding: 1rem;
  }}
  .metric.mode-marketing {{
    border-left-color: #D64C00;
  }}
  .metric.mode-financial {{
    border-left-color: #2563eb;
  }}
  .metric .label {{
    font-size: 0.8rem;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .metric .value {{
    font-size: 1.5rem;
    font-weight: 700;
    color: #111;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }}
  th {{
    text-align: left;
    padding: 0.6rem 0.8rem;
    background: #f4f4f2;
    border-bottom: 2px solid #d0d0d0;
    color: #333;
    font-weight: 600;
  }}
  td {{
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #eee;
  }}
  tr:hover td {{ background: #f9f9f7; }}
  .chart-container {{
    text-align: center;
    margin: 1.5rem 0;
  }}
  .chart-container img {{
    max-width: 100%;
    height: auto;
    border-radius: 2px;
  }}
  .insight {{
    background: #EFF6FF;
    border-left: 3px solid #2563EB;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    font-size: 0.95rem;
  }}
  .missing-warn {{
    background: #FEF3C7;
    border-left: 3px solid #F59E0B;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
  }}
  .executive-summary {{
    background: #f8f6f3;
    border-left: 3px solid #D64C00;
    padding: 1.5rem;
    margin: 1.5rem 0;
    font-size: 1.05rem;
    line-height: 1.7;
    white-space: pre-wrap;
  }}
  .executive-summary.financial {{
    border-left-color: #2563eb;
  }}
  .health-indicator {{
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.5rem;
    margin: 1rem 0;
    border-radius: 2px;
  }}
  .health-indicator.green {{
    background: #f0fdf4;
    border: 2px solid #16a34a;
  }}
  .health-indicator.amber {{
    background: #fffbeb;
    border: 2px solid #F59E0B;
  }}
  .health-indicator.red {{
    background: #fef2f2;
    border: 2px solid #EF4444;
  }}
  .health-dot {{
    width: 24px;
    height: 24px;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .health-dot.green {{ background: #16a34a; }}
  .health-dot.amber {{ background: #F59E0B; }}
  .health-dot.red {{ background: #EF4444; }}
  .health-label {{
    font-size: 1.3rem;
    font-weight: 700;
  }}
  .health-label.green {{ color: #16a34a; }}
  .health-label.amber {{ color: #b45309; }}
  .health-label.red {{ color: #EF4444; }}
  .health-reasons {{
    font-size: 0.9rem;
    color: #555;
    margin-top: 0.25rem;
  }}
  .action-item {{
    background: #fff;
    border: 1px solid #e0e0e0;
    border-left: 3px solid #D64C00;
    padding: 1rem 1.25rem;
    margin: 0.75rem 0;
    border-radius: 2px;
  }}
  .action-number {{
    display: inline-block;
    background: #D64C00;
    color: #fff;
    width: 24px;
    height: 24px;
    text-align: center;
    line-height: 24px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 0.85rem;
    margin-right: 0.5rem;
  }}
  .anomaly-row {{
    background: #FEF3C7;
  }}
  .anomaly-spike {{
    color: #16a34a;
    font-weight: 700;
  }}
  .anomaly-drop {{
    color: #EF4444;
    font-weight: 700;
  }}
  .footer {{
    text-align: center;
    color: #999;
    font-size: 0.8rem;
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #eee;
  }}
  .tag {{
    display: inline-block;
    background: #EFF6FF;
    color: #2563EB;
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 2px;
    font-weight: 600;
    margin-right: 0.25rem;
  }}
  .tag.mode-marketing {{
    background: #FFF3ED;
    color: #D64C00;
  }}
  .tag.mode-financial {{
    background: #EFF6FF;
    color: #2563eb;
  }}
  @media print {{
    body {{
      padding: 1rem;
      font-size: 10pt;
    }}
    .chart-container img {{
      max-width: 100%;
      page-break-inside: avoid;
    }}
    .card, .executive-summary, .health-indicator, .action-item {{
      page-break-inside: avoid;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    h2 {{
      page-break-after: avoid;
    }}
    .footer {{
      display: none;
    }}
  }}
</style>
</head>
<body>
{content}
<div class="footer">
  Generated by CSV Analyzer &middot; {timestamp}
</div>
</body>
</html>"""


def esc(text):
    return html.escape(str(text))


def fmt_number(n, decimals=0):
    if pd.isna(n):
        return '-'
    if isinstance(n, float):
        return f'{n:,.{decimals}f}'
    return f'{int(n):,}'


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_csv(file_path, output_path=None):
    """Run full analysis on a CSV file and generate an HTML report."""

    resolved = find_csv_file(file_path)
    print(f"Analyzing: {resolved}")

    # Detect Google Ads header
    skiprows, report_name, date_range = detect_google_ads_format(resolved)
    if skiprows:
        print(f"  Detected Google Ads export: {report_name}")
        print(f"  Date range: {date_range}")

    # Load
    df = pd.read_csv(resolved, skiprows=skiprows)
    original_rows = len(df)

    # Remove total/summary rows common in Google Ads exports
    for col in df.columns[:3]:
        if df[col].dtype == 'object':
            mask = df[col].astype(str).str.startswith('Total:')
            if mask.any():
                df = df[~mask]
                break

    # Clean
    clean_numeric_columns(df)
    date_cols = detect_date_columns(df)
    data_type = detect_data_type(df)
    print(f"  Data type detected: {data_type}")
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} columns")

    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    cat_cols = [c for c in df.select_dtypes(include='object').columns
                if 'id' not in c.lower() and df[c].nunique() < len(df) * 0.8]

    time_col = find_time_column(df, date_cols)

    # -- Build HTML content --
    parts = []

    # Title and mode badge
    source_name = Path(resolved).stem
    type_labels = {
        'marketing': 'Cross-Channel Marketing Report',
        'financial': 'Financial Health Dashboard',
        'google_ads': 'Google Ads Analysis',
        'sales': 'Sales / E-Commerce Analysis',
        'survey': 'Survey Analysis',
        'generic': 'General Analysis',
    }
    mode_class = {
        'marketing': 'mode-marketing',
        'financial': 'mode-financial',
    }
    mc = mode_class.get(data_type, '')

    parts.append(f'<h1 class="{mc}">{esc(type_labels.get(data_type, "General Analysis"))}</h1>')
    parts.append(f'<p class="subtitle">'
                 f'<span class="tag {mc}">{esc(type_labels.get(data_type, "General"))}</span> '
                 f'{esc(source_name)} &middot; {esc(resolved)}</p>')

    # ===================================================================
    # MODE: Cross-Channel Marketing
    # ===================================================================
    if data_type == 'marketing':
        channel_col = find_column(df, ['channel', 'platform', 'source', 'medium', 'network',
                                        'campaign_type', 'ad_platform', 'traffic_source'])
        spend_col = find_column(df, ['spend', 'cost', 'budget', 'ad_spend', 'total_spend'])
        conv_col = find_column(df, ['conversions', 'leads', 'signups', 'purchases',
                                      'sales', 'acquisitions'])
        cpa_col = find_column(df, ['cpa', 'cost_per_acquisition', 'cost_per_lead',
                                     'cost_per_conversion', 'cost_per'])
        roas_col = find_column(df, ['roas', 'return_on_ad_spend', 'return_on'])
        ctr_col = find_column(df, ['ctr', 'click_through_rate', 'clickthrough'])
        clicks_col = find_column(df, ['clicks', 'total_clicks'])
        impr_col = find_column(df, ['impressions', 'impr', 'views', 'reach'])
        rev_col = find_column(df, ['revenue', 'total_revenue', 'conv_value',
                                     'conversion_value'])

        # Overview metrics
        parts.append('<div class="metrics-grid">')
        n_channels = df[channel_col].nunique() if channel_col else 0
        parts.append(f'<div class="metric mode-marketing"><div class="label">Channels</div>'
                     f'<div class="value">{n_channels}</div></div>')
        parts.append(f'<div class="metric mode-marketing"><div class="label">Data Points</div>'
                     f'<div class="value">{fmt_number(len(df))}</div></div>')
        if spend_col and spend_col in df.columns:
            parts.append(f'<div class="metric mode-marketing"><div class="label">Total Spend</div>'
                         f'<div class="value">${fmt_number(df[spend_col].sum(), 0)}</div></div>')
        if conv_col and conv_col in df.columns:
            parts.append(f'<div class="metric mode-marketing"><div class="label">Total Conversions</div>'
                         f'<div class="value">{fmt_number(df[conv_col].sum(), 0)}</div></div>')
        if spend_col and conv_col and spend_col in df.columns and conv_col in df.columns:
            total_cpa = df[spend_col].sum() / df[conv_col].sum() if df[conv_col].sum() > 0 else 0
            parts.append(f'<div class="metric mode-marketing"><div class="label">Blended CPA</div>'
                         f'<div class="value">${fmt_number(total_cpa, 2)}</div></div>')
        if roas_col and roas_col in df.columns:
            avg_roas = df[roas_col].mean()
            parts.append(f'<div class="metric mode-marketing"><div class="label">Avg ROAS</div>'
                         f'<div class="value">{fmt_number(avg_roas, 2)}x</div></div>')
        parts.append('</div>')

        # 1. Channel Comparison
        comparison_metrics = [m for m in [spend_col, conv_col, cpa_col, roas_col, ctr_col]
                              if m and m in df.columns]
        parts.append('<h2>Channel Comparison</h2>')
        comp_b64 = make_channel_comparison_chart(df, channel_col, comparison_metrics)
        if comp_b64:
            parts.append(f'<div class="chart-container">'
                         f'<img src="data:image/png;base64,{comp_b64}" alt="Channel Comparison">'
                         f'</div>')

        # 2. Budget Reallocation
        parts.append('<h2>Budget Reallocation Recommendation</h2>')
        realloc = build_budget_reallocation(df, channel_col, spend_col, conv_col)
        if realloc:
            parts.append('<div class="card">')
            parts.append(f'<p><strong>Most efficient channel:</strong> {esc(realloc["best_channel"])} '
                         f'(CPA: ${realloc["best_cpa"]:,.2f})</p>')
            parts.append(f'<p><strong>Least efficient channel:</strong> {esc(realloc["worst_channel"])} '
                         f'(CPA: ${realloc["worst_cpa"]:,.2f})</p>')
            parts.append(f'<div class="action-item">'
                         f'<span class="action-number">$</span> '
                         f'Move ${realloc["move_amount"]:,.0f}/mo from {esc(realloc["worst_channel"])} '
                         f'to {esc(realloc["best_channel"])}: projected '
                         f'+{realloc["projected_extra_conv"]:,.0f} additional conversions '
                         f'at ${realloc["best_cpa"]:,.2f} CPA</div>')
            # Before/after table
            tbl = realloc['table']
            parts.append('<table>')
            parts.append(f'<tr><th>Channel</th><th>Current {esc(realloc["spend_col"])}</th>'
                         f'<th>{esc(realloc["conv_col"])}</th><th>CPA</th></tr>')
            for _, row in tbl.iterrows():
                parts.append(f'<tr><td>{esc(str(row[channel_col]))}</td>'
                             f'<td>${row[realloc["spend_col"]]:,.0f}</td>'
                             f'<td>{row[realloc["conv_col"]]:,.0f}</td>'
                             f'<td>${row["CPA"]:,.2f}</td></tr>')
            parts.append('</table>')
            parts.append('</div>')
        else:
            parts.append('<div class="card"><p>Insufficient data to calculate budget reallocation. '
                         'Need channel, spend, and conversion columns.</p></div>')

        # 3. Trend Analysis
        if time_col and channel_col:
            trend_metric = spend_col or conv_col
            if trend_metric:
                parts.append('<h2>Trend Analysis</h2>')
                # Generate trend charts for key metrics
                for metric in [spend_col, conv_col, cpa_col]:
                    if metric and metric in df.columns:
                        trend_b64 = make_channel_trend_chart(df, channel_col, time_col, metric)
                        if trend_b64:
                            parts.append(f'<div class="chart-container">'
                                         f'<img src="data:image/png;base64,{trend_b64}" '
                                         f'alt="{esc(metric)} Trend">'
                                         f'</div>')

        # 4. Anomaly Detection
        anomaly_metrics = [m for m in [spend_col, conv_col, cpa_col, roas_col]
                           if m and m in df.columns]
        if channel_col and time_col and anomaly_metrics:
            anomalies = detect_anomalies(df, channel_col, time_col, anomaly_metrics)
            parts.append('<h2>Anomaly Detection</h2>')
            if anomalies:
                parts.append(f'<div class="card"><p>{len(anomalies)} anomalies detected '
                             f'(values &gt; 2 standard deviations from channel mean):</p>')
                parts.append('<table>')
                parts.append('<tr><th>Channel</th><th>Period</th><th>Metric</th>'
                             '<th>Value</th><th>Expected Range</th><th>Type</th></tr>')
                for a in anomalies[:20]:
                    dir_class = 'anomaly-spike' if a['direction'] == 'spike' else 'anomaly-drop'
                    dir_label = a['direction'].upper()
                    parts.append(f'<tr class="anomaly-row">'
                                 f'<td>{esc(a["channel"])}</td>'
                                 f'<td>{esc(a["period"])}</td>'
                                 f'<td>{esc(a["metric"])}</td>'
                                 f'<td>{a["value"]:,.2f}</td>'
                                 f'<td>{esc(a["expected_range"])}</td>'
                                 f'<td class="{dir_class}">{dir_label}</td></tr>')
                parts.append('</table></div>')
            else:
                parts.append('<div class="card"><p>No significant anomalies detected. '
                             'All values within 2 standard deviations of their channel means.</p></div>')

        # 5. Executive Summary
        parts.append('<h2>Executive Summary</h2>')
        summary = generate_marketing_summary(df, channel_col, spend_col, conv_col, realloc)
        parts.append(f'<div class="executive-summary">{esc(summary)}</div>')

    # ===================================================================
    # MODE: CFO Financial Dashboard
    # ===================================================================
    elif data_type == 'financial':
        revenue_col = find_column(df, ['revenue', 'sales', 'total_revenue', 'gross_revenue',
                                         'net_revenue', 'income', 'total_sales'])
        profit_col = find_column(df, ['net_income', 'net_profit', 'profit', 'operating_income',
                                        'ebitda', 'gross_profit', 'bottom_line'])
        cogs_col = find_column(df, ['cogs', 'cost_of_goods', 'cost_of_sales',
                                      'direct_costs', 'cost_of_revenue'])
        cash_col = find_column(df, ['cash_balance', 'cash', 'bank_balance',
                                      'cash_position', 'ending_cash', 'total_cash'])

        # Find all expense columns
        expense_candidates = ['payroll', 'rent', 'utilities', 'marketing', 'marketing_expense',
                              'sga', 'operating_expense', 'opex', 'admin', 'insurance',
                              'depreciation', 'interest', 'taxes', 'other_expenses',
                              'salaries', 'wages', 'benefits', 'software', 'travel',
                              'professional_services', 'supplies']
        expense_cols = []
        for cand in expense_candidates:
            col = find_column(df, [cand], partial=True)
            if col and col in df.columns and col not in expense_cols:
                # Exclude revenue/profit cols from expenses
                if col != revenue_col and col != profit_col and col != cash_col:
                    expense_cols.append(col)

        # If we found a COGS column but no expense_cols, try finding any remaining numeric cols
        # that aren't revenue/profit/cash/cogs as potential expense categories
        if not expense_cols and cogs_col:
            for col in numeric_cols:
                if col not in [revenue_col, profit_col, cash_col, cogs_col]:
                    expense_cols.append(col)

        # Find margin columns
        margin_candidates = ['gross_margin', 'operating_margin', 'net_margin',
                             'profit_margin', 'margin']
        margin_cols = []
        for cand in margin_candidates:
            col = find_column(df, [cand], partial=True)
            if col and col in df.columns and col not in margin_cols:
                margin_cols.append(col)

        # Calculate margins if not present but we have the data
        if not margin_cols and revenue_col and revenue_col in df.columns:
            if cogs_col and cogs_col in df.columns:
                df['Gross Margin %'] = ((df[revenue_col] - df[cogs_col]) /
                                        df[revenue_col].replace(0, np.nan)) * 100
                margin_cols.append('Gross Margin %')
            if profit_col and profit_col in df.columns:
                df['Net Margin %'] = (df[profit_col] /
                                      df[revenue_col].replace(0, np.nan)) * 100
                margin_cols.append('Net Margin %')

        # 1. Financial Health Indicator
        health = calculate_financial_health(df, margin_cols, revenue_col)
        parts.append('<h2>Financial Health</h2>')
        parts.append(f'<div class="health-indicator {health["status"]}">')
        parts.append(f'  <div class="health-dot {health["status"]}"></div>')
        parts.append(f'  <div>')
        parts.append(f'    <div class="health-label {health["status"]}">{esc(health["label"])}</div>')
        parts.append(f'    <div class="health-reasons">{esc("; ".join(health["reasons"]))}</div>')
        parts.append(f'  </div>')
        parts.append(f'</div>')

        # Overview metrics
        parts.append('<div class="metrics-grid">')
        parts.append(f'<div class="metric mode-financial"><div class="label">Periods</div>'
                     f'<div class="value">{fmt_number(len(df))}</div></div>')
        if revenue_col and revenue_col in df.columns:
            parts.append(f'<div class="metric mode-financial"><div class="label">Latest Revenue</div>'
                         f'<div class="value">${fmt_number(df[revenue_col].iloc[-1], 0)}</div></div>')
        if profit_col and profit_col in df.columns:
            parts.append(f'<div class="metric mode-financial"><div class="label">Latest Profit</div>'
                         f'<div class="value">${fmt_number(df[profit_col].iloc[-1], 0)}</div></div>')
        if margin_cols:
            last_margin = margin_cols[-1]
            if last_margin in df.columns:
                parts.append(f'<div class="metric mode-financial"><div class="label">{esc(last_margin)}</div>'
                             f'<div class="value">{fmt_number(df[last_margin].iloc[-1], 1)}%</div></div>')
        if cash_col and cash_col in df.columns:
            parts.append(f'<div class="metric mode-financial"><div class="label">Cash Position</div>'
                         f'<div class="value">${fmt_number(df[cash_col].iloc[-1], 0)}</div></div>')
        parts.append('</div>')

        # 2. Revenue & Profit Trends
        if revenue_col and profit_col:
            parts.append('<h2>Revenue & Profit Trends</h2>')
            rev_profit_b64 = make_revenue_profit_chart(df, time_col, revenue_col, profit_col)
            if rev_profit_b64:
                parts.append(f'<div class="chart-container">'
                             f'<img src="data:image/png;base64,{rev_profit_b64}" '
                             f'alt="Revenue & Profit Trends">'
                             f'</div>')

        # 3. Expense Analysis
        if expense_cols:
            parts.append('<h2>Expense Analysis</h2>')
            expense_b64 = make_expense_breakdown_chart(df, time_col, expense_cols, revenue_col)
            if expense_b64:
                parts.append(f'<div class="chart-container">'
                             f'<img src="data:image/png;base64,{expense_b64}" '
                             f'alt="Expense Breakdown">'
                             f'</div>')

            # Growth rate table
            parts.append('<div class="card"><strong>Expense Category Growth Rates</strong>')
            parts.append('<table><tr><th>Category</th><th>Latest</th>'
                         '<th>Growth Rate</th><th>% of Revenue</th></tr>')
            growth_data = []
            for col in expense_cols:
                if col in df.columns:
                    vals = df[col].dropna().values
                    latest = vals[-1] if len(vals) > 0 else 0
                    growth = ((vals[-1] - vals[0]) / vals[0]) * 100 if len(vals) >= 2 and vals[0] > 0 else 0
                    rev_pct = (latest / df[revenue_col].iloc[-1]) * 100 if revenue_col and revenue_col in df.columns and df[revenue_col].iloc[-1] > 0 else 0
                    growth_data.append((col, latest, growth, rev_pct))

            growth_data.sort(key=lambda x: -x[2])
            for col, latest, growth, rev_pct in growth_data:
                growth_color = '#EF4444' if growth > 10 else '#333'
                parts.append(f'<tr><td>{esc(col)}</td><td>${latest:,.0f}</td>'
                             f'<td style="color:{growth_color}">{growth:+.1f}%</td>'
                             f'<td>{rev_pct:.1f}%</td></tr>')
            parts.append('</table></div>')

        # 4. Margin Trends
        if margin_cols:
            parts.append('<h2>Margin Trends</h2>')
            margin_b64 = make_margin_trends_chart(df, time_col, margin_cols)
            if margin_b64:
                parts.append(f'<div class="chart-container">'
                             f'<img src="data:image/png;base64,{margin_b64}" '
                             f'alt="Margin Trends">'
                             f'</div>')

            # Margin change table
            parts.append('<div class="card"><strong>Margin Summary</strong>')
            parts.append('<table><tr><th>Margin</th><th>Start</th><th>End</th><th>Change</th></tr>')
            for col in margin_cols:
                if col in df.columns:
                    vals = df[col].dropna().values
                    if len(vals) >= 2:
                        change = vals[-1] - vals[0]
                        change_color = '#16a34a' if change >= 0 else '#EF4444'
                        parts.append(f'<tr><td>{esc(col)}</td>'
                                     f'<td>{vals[0]:.1f}%</td>'
                                     f'<td>{vals[-1]:.1f}%</td>'
                                     f'<td style="color:{change_color}">{change:+.1f}pp</td></tr>')
            parts.append('</table></div>')

        # 5. Cash Flow
        if cash_col and cash_col in df.columns:
            parts.append('<h2>Cash Flow Health</h2>')
            cash_b64 = make_cash_flow_chart(df, time_col, cash_col)
            if cash_b64:
                parts.append(f'<div class="chart-container">'
                             f'<img src="data:image/png;base64,{cash_b64}" '
                             f'alt="Cash Flow">'
                             f'</div>')

            # Runway calculation
            cash_vals = df[cash_col].dropna().values
            if len(cash_vals) >= 2:
                monthly_change = np.mean(np.diff(cash_vals))
                current_cash = cash_vals[-1]
                if monthly_change < 0 and current_cash > 0:
                    runway_months = current_cash / abs(monthly_change)
                    runway_color = '#16a34a' if runway_months > 12 else ('#F59E0B' if runway_months > 6 else '#EF4444')
                    parts.append(f'<div class="card"><p>Average monthly cash change: '
                                 f'<strong style="color:{"#EF4444" if monthly_change < 0 else "#16a34a"}">'
                                 f'${monthly_change:+,.0f}</strong></p>'
                                 f'<p>Projected runway at current burn rate: '
                                 f'<strong style="color:{runway_color}">{runway_months:.0f} months</strong></p></div>')
                else:
                    parts.append(f'<div class="card"><p>Average monthly cash change: '
                                 f'<strong style="color:#16a34a">${monthly_change:+,.0f}</strong></p>'
                                 f'<p>Cash position is <strong style="color:#16a34a">building</strong>.</p></div>')

        # 6. Action Items
        parts.append('<h2>Recommended Actions</h2>')
        actions = generate_financial_actions(df, revenue_col, expense_cols, margin_cols, health)
        for i, action in enumerate(actions, 1):
            parts.append(f'<div class="action-item">'
                         f'<span class="action-number">{i}</span> {esc(action)}</div>')

        # 7. Narrative
        parts.append('<h2>The Story Behind the Numbers</h2>')
        narrative = generate_financial_narrative(df, revenue_col, profit_col, margin_cols, health, actions)
        parts.append(f'<div class="executive-summary financial">{esc(narrative)}</div>')

    # ===================================================================
    # MODE: Google Ads
    # ===================================================================
    elif data_type == 'google_ads':
        # Overview metrics
        missing_total = df.isnull().sum().sum()
        missing_pct = (missing_total / (df.shape[0] * df.shape[1])) * 100 if df.size else 0
        parts.append('<div class="metrics-grid">')
        parts.append(f'<div class="metric"><div class="label">Rows</div>'
                     f'<div class="value">{fmt_number(df.shape[0])}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Columns</div>'
                     f'<div class="value">{df.shape[1]}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Numeric Columns</div>'
                     f'<div class="value">{len(numeric_cols)}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Missing Values</div>'
                     f'<div class="value">{fmt_number(missing_total)} ({missing_pct:.1f}%)</div></div>')
        parts.append('</div>')

    # ===================================================================
    # MODE: Generic (also shared sections for Google Ads)
    # ===================================================================
    if data_type in ('generic', 'sales', 'survey'):
        # Overview metrics
        missing_total = df.isnull().sum().sum()
        missing_pct = (missing_total / (df.shape[0] * df.shape[1])) * 100 if df.size else 0
        parts.append('<div class="metrics-grid">')
        parts.append(f'<div class="metric"><div class="label">Rows</div>'
                     f'<div class="value">{fmt_number(df.shape[0])}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Columns</div>'
                     f'<div class="value">{df.shape[1]}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Numeric Columns</div>'
                     f'<div class="value">{len(numeric_cols)}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Categorical Columns</div>'
                     f'<div class="value">{len(cat_cols)}</div></div>')
        if date_cols:
            parts.append(f'<div class="metric"><div class="label">Date Columns</div>'
                         f'<div class="value">{len(date_cols)}</div></div>')
        parts.append(f'<div class="metric"><div class="label">Missing Values</div>'
                     f'<div class="value">{fmt_number(missing_total)} ({missing_pct:.1f}%)</div></div>')
        parts.append('</div>')

    # -- Shared sections for non-marketing, non-financial modes --
    if data_type not in ('marketing', 'financial'):
        # Column types table
        parts.append('<h2>Column Types</h2>')
        parts.append('<div class="card"><table>')
        parts.append('<tr><th>Column</th><th>Type</th><th>Non-null</th><th>Unique</th><th>Sample</th></tr>')
        for col in df.columns:
            non_null = df[col].notna().sum()
            nuniq = df[col].nunique()
            sample_val = df[col].dropna().iloc[0] if df[col].notna().any() else '-'
            sample_str = str(sample_val)[:50]
            parts.append(f'<tr><td>{esc(col)}</td><td>{esc(str(df[col].dtype))}</td>'
                         f'<td>{fmt_number(non_null)}</td><td>{fmt_number(nuniq)}</td>'
                         f'<td>{esc(sample_str)}</td></tr>')
        parts.append('</table></div>')

        # Missing data detail
        if df.isnull().sum().sum() > 0:
            parts.append('<h2>Missing Data</h2>')
            cols_with_missing = [(c, df[c].isnull().sum()) for c in df.columns if df[c].isnull().sum() > 0]
            cols_with_missing.sort(key=lambda x: -x[1])
            parts.append('<div class="card"><table>')
            parts.append('<tr><th>Column</th><th>Missing</th><th>% Missing</th></tr>')
            for col, cnt in cols_with_missing:
                pct = cnt / len(df) * 100
                parts.append(f'<tr><td>{esc(col)}</td><td>{fmt_number(cnt)}</td>'
                             f'<td>{pct:.1f}%</td></tr>')
            parts.append('</table></div>')

        # Numeric summary statistics
        if numeric_cols:
            parts.append('<h2>Numeric Summary Statistics</h2>')
            desc = df[numeric_cols].describe().T
            parts.append('<div class="card"><table>')
            parts.append('<tr><th>Column</th><th>Mean</th><th>Std</th><th>Min</th>'
                         '<th>25%</th><th>Median</th><th>75%</th><th>Max</th></tr>')
            for col in desc.index:
                row = desc.loc[col]
                parts.append(f'<tr><td>{esc(col)}</td>'
                             f'<td>{fmt_number(row["mean"], 2)}</td>'
                             f'<td>{fmt_number(row["std"], 2)}</td>'
                             f'<td>{fmt_number(row["min"], 2)}</td>'
                             f'<td>{fmt_number(row["25%"], 2)}</td>'
                             f'<td>{fmt_number(row["50%"], 2)}</td>'
                             f'<td>{fmt_number(row["75%"], 2)}</td>'
                             f'<td>{fmt_number(row["max"], 2)}</td></tr>')
            parts.append('</table></div>')

        # Categorical value counts
        if cat_cols:
            parts.append('<h2>Categorical Distributions</h2>')
            for col in cat_cols[:5]:
                vc = df[col].value_counts().head(10)
                parts.append(f'<div class="card"><strong>{esc(col)}</strong> '
                             f'({df[col].nunique()} unique values)<table>')
                parts.append('<tr><th>Value</th><th>Count</th><th>%</th></tr>')
                for val, cnt in vc.items():
                    pct = cnt / len(df) * 100
                    parts.append(f'<tr><td>{esc(str(val)[:60])}</td>'
                                 f'<td>{fmt_number(cnt)}</td><td>{pct:.1f}%</td></tr>')
                parts.append('</table></div>')

        # Date range info
        if date_cols:
            parts.append('<h2>Date Range</h2>')
            parts.append('<div class="card">')
            for dc in date_cols:
                dmin = df[dc].min()
                dmax = df[dc].max()
                span = (dmax - dmin).days if pd.notna(dmin) and pd.notna(dmax) else 0
                parts.append(f'<p><strong>{esc(dc)}</strong>: {dmin} to {dmax} ({span} days)</p>')
            parts.append('</div>')

        # -- Charts --
        parts.append('<h2>Visualizations</h2>')
        chart_count = 0

        # Google Ads-specific charts
        if data_type == 'google_ads':
            status_col = None
            for c in df.columns:
                if 'status' in c.lower():
                    status_col = c
                    break
            if status_col:
                enabled_df = df[df[status_col].astype(str).str.strip() == 'Enabled']
            else:
                enabled_df = df

            ads_charts = make_google_ads_charts(df, enabled_df)
            for title, b64 in ads_charts:
                parts.append(f'<div class="chart-container">'
                             f'<img src="data:image/png;base64,{b64}" alt="{esc(title)}">'
                             f'</div>')
                chart_count += 1

            # Google Ads insights
            if len(enabled_df) > 0:
                parts.append('<h2>Key Insights</h2>')
                total_cost = enabled_df.get('Cost', pd.Series([0])).sum()
                total_conv = enabled_df.get('Conversions', pd.Series([0])).sum()
                total_value = enabled_df.get('Conv. value', pd.Series([0])).sum()

                if total_cost > 0:
                    parts.append(f'<div class="insight">Total spend across '
                                 f'{len(enabled_df)} enabled items: '
                                 f'{fmt_number(total_cost, 2)}</div>')
                if total_conv > 0 and total_cost > 0:
                    cpa = total_cost / total_conv
                    parts.append(f'<div class="insight">Average cost per conversion: '
                                 f'{fmt_number(cpa, 2)}</div>')
                if total_value > 0 and total_cost > 0:
                    roas = total_value / total_cost
                    status = "profitable" if roas > 1 else "unprofitable"
                    parts.append(f'<div class="insight">Overall ROAS: '
                                 f'{roas:.2f}x ({status})</div>')
                zero_conv = len(enabled_df[enabled_df.get('Conversions', pd.Series([1])) == 0])
                if zero_conv > 0:
                    parts.append(f'<div class="missing-warn">{zero_conv} enabled items '
                                 f'with zero conversions</div>')

        # Distribution charts (all non-specialized data types)
        dist_b64 = make_distribution_plots(df, numeric_cols)
        if dist_b64:
            parts.append(f'<div class="chart-container">'
                         f'<img src="data:image/png;base64,{dist_b64}" alt="Distributions">'
                         f'</div>')
            chart_count += 1

        # Correlation heatmap
        corr_b64 = make_correlation_heatmap(df, numeric_cols)
        if corr_b64:
            parts.append(f'<div class="chart-container">'
                         f'<img src="data:image/png;base64,{corr_b64}" alt="Correlations">'
                         f'</div>')
            chart_count += 1

        # Categorical charts
        cat_b64 = make_categorical_plots(df, cat_cols)
        if cat_b64:
            parts.append(f'<div class="chart-container">'
                         f'<img src="data:image/png;base64,{cat_b64}" alt="Categories">'
                         f'</div>')
            chart_count += 1

        # Time series charts
        if date_cols and numeric_cols:
            ts_b64 = make_timeseries_plots(df, date_cols[0], numeric_cols)
            if ts_b64:
                parts.append(f'<div class="chart-container">'
                             f'<img src="data:image/png;base64,{ts_b64}" alt="Time Series">'
                             f'</div>')
                chart_count += 1

        # General insights (non-Google-Ads)
        if data_type != 'google_ads' and numeric_cols:
            parts.append('<h2>Key Insights</h2>')
            for col in numeric_cols[:5]:
                data = df[col].dropna()
                if len(data) == 0:
                    continue
                mean_val = data.mean()
                median_val = data.median()
                skew = data.skew()
                skew_desc = 'right-skewed' if skew > 1 else ('left-skewed' if skew < -1 else 'roughly symmetric')
                parts.append(f'<div class="insight"><strong>{esc(col)}</strong>: '
                             f'mean={fmt_number(mean_val, 2)}, '
                             f'median={fmt_number(median_val, 2)}, '
                             f'distribution is {skew_desc} (skew={skew:.2f})</div>')

    # Data sample (all modes)
    parts.append('<h2>Data Sample (first 10 rows)</h2>')
    parts.append('<div class="card" style="overflow-x:auto;"><table>')
    parts.append('<tr>' + ''.join(f'<th>{esc(c)}</th>' for c in df.columns) + '</tr>')
    for _, row in df.head(10).iterrows():
        cells = ''.join(f'<td>{esc(str(v)[:50])}</td>' for v in row)
        parts.append(f'<tr>{cells}</tr>')
    parts.append('</table></div>')

    # Assemble HTML
    content = '\n'.join(parts)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report_html = HTML_TEMPLATE.format(content=content, timestamp=timestamp)

    # Output
    if output_path is None:
        skill_dir = Path(__file__).parent.parent
        output_dir = skill_dir / 'output'
        output_dir.mkdir(exist_ok=True)
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', source_name)
        output_path = output_dir / f'{safe_name}_report.html'

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_html, encoding='utf-8')

    print(f"\nReport generated: {output_path}")
    print(f"  Mode: {type_labels.get(data_type, 'generic')}")
    print(f"  {df.shape[0]} rows, {df.shape[1]} columns")
    return str(output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 analyze.py <csv_file> [--output <report.html>]")
        sys.exit(1)

    csv_path = sys.argv[1]
    out_path = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    report = analyze_csv(csv_path, out_path)
    print(f"\nDone. Open in browser: {report}")
