import aiohttp
from bs4 import BeautifulSoup
import re
from config import USER_AGENT

CURRENCY_REGEX = re.compile(r'([R\$US\$]|USD|R\$|₲)?\s*([0-9\.,]+)')

async def fetch_html(url, user_agent=USER_AGENT):
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "DNT": "1"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=25) as resp:
                if resp.status != 200:
                    print(f"⚠️ Erro ao acessar {url}: status {resp.status}")
                    return ""
                return await resp.text()
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return ""

def parse_price_from_text(text):
    m = CURRENCY_REGEX.search(text.replace('\xa0', ' '))
    if not m:
        return None, None
    raw = m.group(2).replace('.', '').replace(',', '.')
    try:
        return float(raw), (m.group(1) or '').strip()
    except:
        return None, None

async def scrape_product_page(url):
    html = await fetch_html(url)
    if not html:
        return "Sem título", None, None

    soup = BeautifulSoup(html, 'html.parser')

    # Extrair nome do produto
    name = None
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        name = og['content'].strip()
    if not name:
        title = soup.find('title')
        if title:
            name = title.get_text(strip=True)

    # Seletores comuns para preços
    selectors = [
        '[itemprop=price]',
        '.price',
        '.preco',
        '.product-price',
        '.valor',
        '.price--main',
        '.product-price__price',
        '.price-amount'
    ]

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            p, c = parse_price_from_text(el.get_text())
            if p is not None:
                return name or "Sem título", p, c or "USD"

    # Caso tenha metadados de preço
    meta_price = soup.find('meta', property='product:price:amount')
    if meta_price and meta_price.get('content'):
        try:
            p = float(meta_price['content'].replace(',', ''))
            meta_curr = soup.find('meta', property='product:price:currency')
            curr = meta_curr['content'] if meta_curr else 'USD'
            return name or "Sem título", p, curr
        except:
            pass

    # Último recurso: procurar texto bruto
    p, c = parse_price_from_text(soup.get_text(" ", strip=True))
    if p is not None:
        return name or "Sem título", p, c or "USD"

    return name or "Sem título", None, None
