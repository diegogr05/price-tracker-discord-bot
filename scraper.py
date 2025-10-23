import aiohttp
from bs4 import BeautifulSoup
import re
from config import USER_AGENT

CURRENCY_REGEX = re.compile(r'([R\$US\$]|USD|R\$|₲)?\s*([0-9\.,]+)')

async def fetch_html(url, user_agent=USER_AGENT):
    headers = {"User-Agent": user_agent}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=25) as resp:
            return await resp.text()

def parse_price_from_text(text):
    m = CURRENCY_REGEX.search(text.replace('\xa0',' '))
    if not m:
        return None, None
    raw = m.group(2).replace('.', '').replace(',', '.')
    try:
        return float(raw), (m.group(1) or '').strip()
    except:
        return None, None

async def scrape_product_page(url):
    html = await fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    name = None
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        name = og['content'].strip()
    if not name:
        title = soup.find('title')
        if title:
            name = title.get_text(strip=True)

    selectors = ['[itemprop=price]', '.price', '.preco', '.product-price', '.valor', '.price--main', '.product-price__price', '.price-amount']
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            p, c = parse_price_from_text(el.get_text())
            if p is not None:
                return name or "Sem título", p, c or "USD"

    meta_price = soup.find('meta', property='product:price:amount')
    if meta_price and meta_price.get('content'):
        try:
            p = float(meta_price['content'].replace(',', ''))
            meta_curr = soup.find('meta', property='product:price:currency')
            curr = meta_curr['content'] if meta_curr else 'USD'
            return name or "Sem título", p, curr
        except:
            pass

    p, c = parse_price_from_text(soup.get_text(" ", strip=True))
    if p is not None:
        return name or "Sem título", p, c or "USD"

    return name or "Sem título", None, None
