import requests
import csv
import os
import time
from datetime import datetime, timedelta

API_KEY = os.environ.get('POLYGON_API_KEY')

STOCKS = [
    ('AAPL',  'Apple'),
    ('AMD',   'AMD'),
    ('AMZN',  'Amazon'),
    ('GOOG',  'Alphabet'),
    ('META',  'Meta'),
    ('MSFT',  'Microsoft'),
    ('MU',    'Micron'),
    ('NBIS',  'Neurabases'),
    ('NFLX',  'Netflix'),
    ('NVDA',  'NVIDIA'),
    ('QQQ',   'Nasdaq ETF'),
    ('SNDK',  'SanDisk'),
    ('TSLA',  'Tesla'),
]

def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]['h']
        low  = candles[i]['l']
        prev = candles[i-1]['c']
        tr = max(high - low, abs(high - prev), abs(low - prev))
        trs.append(tr)
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr

def fetch_candles(ticker, retries=5):
    to_date   = datetime.utcnow().strftime('%Y-%m-%d')
    from_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    url = (
        f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/'
        f'{from_date}/{to_date}'
        f'?adjusted=true&sort=asc&limit=30&apiKey={API_KEY}'
    )
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)  # 30s, 60s, 90s...
                print(f'{ticker}: rate limited, waiting {wait}s...')
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            results = data.get('results', [])
            if len(results) < 2:
                print(f'{ticker}: not enough data ({len(results)} candles)')
                return None
            return results
        except Exception as e:
            print(f'{ticker} attempt {attempt+1} failed: {e}')
            time.sleep(5)
    return None

def compare_ranges(y_high, y_low, p_high, p_low):
    r1 = y_high - y_low
    r2 = p_high - p_low
    diff = r1 - r2
    is_inside = y_high <= p_high and y_low >= p_low
    if is_inside:
        return 'Inside Day'
    elif diff > 0:
        return 'Expanding'
    else:
        return 'Contracting'

today = datetime.utcnow().strftime('%Y-%m-%d')
rows = []

for ticker, company in STOCKS:
    print(f'Fetching {ticker}...')
    candles = fetch_candles(ticker)

    if not candles:
        rows.append({
            'Date': today,
            'Ticker': ticker,
            'Company': company,
            'Yesterday High': '',
            'Yesterday Low': '',
            'Yesterday Range': '',
            '2 Days Ago High': '',
            '2 Days Ago Low': '',
            '2 Days Ago Range': '',
            'Range Status': 'No data',
            'ATR(14)': '',
        })
    else:
        n = len(candles)
        y  = candles[n-1]
        p  = candles[n-2]
        atr = calc_atr(candles)
        status = compare_ranges(y['h'], y['l'], p['h'], p['l'])
        rows.append({
            'Date': today,
            'Ticker': ticker,
            'Company': company,
            'Yesterday High': round(y['h'], 2),
            'Yesterday Low':  round(y['l'], 2),
            'Yesterday Range': round(y['h'] - y['l'], 2),
            '2 Days Ago High': round(p['h'], 2),
            '2 Days Ago Low':  round(p['l'], 2),
            '2 Days Ago Range': round(p['h'] - p['l'], 2),
            'Range Status': status,
            'ATR(14)': round(atr, 2) if atr else '',
        })

    time.sleep(13)  # 13s delay = ~5 requests/min, safely under free tier limit

# Write CSV
fields = [
    'Date', 'Ticker', 'Company',
    'Yesterday High', 'Yesterday Low', 'Yesterday Range',
    '2 Days Ago High', '2 Days Ago Low', '2 Days Ago Range',
    'Range Status', 'ATR(14)'
]

with open('latest.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f'Done! latest.csv written with {len(rows)} rows.')
