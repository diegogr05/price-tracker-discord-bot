# scraper.py
import aiohttp
import asyncio
import random
import re
from typing import Optional, Tuple

# User agents para rotacionar
DEFAULT_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# Regex para extrair moeda e número - ajustável
CURRENCY_REGEX = re.compile(r'([R\$US\$]|USD|R\$|₲)?\s*([0-9\.,]+)')

async def fetch_html(url: str, user_agent: Optional[str] = None, max_retries: int = 3, timeout: int = 25) -> str:
    """
    Busca o HTML do url tentando se passar por um navegador real.
    Retorna string vazia em caso de falha.
    """
    headers = {
        "User-Agent": user_agent or random.choice(DEFAULT_UAS),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }

    # backoff base para aguardar entre tentativas
    backoff_base = 1.2

    for attempt in range(1, max_retries + 1):
        try:
            # connector: limite por host (ajustável). ssl=False pode ajudar em alguns hosts/ambientes.
            conn = aiohttp.TCPConnector(limit_per_host=4, ssl=False)
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(headers=headers, connector=conn, timeout=timeout_obj) as session:
                async with session.get(url) as resp:
                    status = resp.status
                    text = await resp.text(errors='ignore')
                    # respostas 200 com conteúdo significativo
                    if status == 200 and text and len(text) > 50:
                        # detectar páginas de challenge (Cloudflare)
                        snippet = text[:400].lower()
                        if "just a moment" in snippet or "checking your browser" in snippet or "cloudflare" in snippet:
                            print(f"⚠️ fetch_html: challenge/cloudflare detected for {url} (attempt {attempt}/{max_retries})")
                        else:
                            return text
                    # lidar com códigos de status
                    if status in (403, 429):
                        print(f"⚠️ fetch_html: {url} -> status {status} (attempt {attempt}/{max_retries})")
                    elif status >= 500:
                        print(f"⚠️ fetch_html: server error {status} for {url} (attempt {attempt}/{max_retries})")
                    else:
                        # se texto curto ou inesperado, imprimir aviso (útil nos logs)
                        print(f"⚠️ fetch_html: unexpected status {status} for {url} (attempt {attempt}/{max_retries})")
        except asyncio.TimeoutError:
            print(f"⚠️ fetch_html: timeout for {url} (attempt {attempt}/{max_retries})")
        except Exception as e:
            print(f"❌ fetch_html exception for {url}: {e} (attempt {attempt}/{max_retries})")

        # espera exponencial leve + jitter antes da próxima tentativa
        await asyncio.sleep(backoff_base ** attempt + random.random() * 0.5)

    print(f"❌ fetch_html: giving up on {url}")
    return ""

def parse_price_from_text(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Busca um padrão de moeda+valor no texto.
    Retorna (valor, simbolo) ou (None, None).
    """
    if not text:
        return None, None
    # normaliza espaços no texto
    txt = text.replace('\xa0', ' ')
    m = CURRENCY_REGEX.search(txt)
    if not m:
        return None, None
    raw = m.group(2).replace('.', '').replace(',', '.')
    try:
        val = float(raw)
        curr = (m.group(1) or '').strip()
        return val, curr or None
    except Exception:
        return None, None

async def scrape_product_page(url: str) -> Tuple[str, Optional[float], Optional[str]]:
    """
    Função principal de scraping: retorna (nome, preco, moeda).
    Se não achar preço, retorna (nome, None, None).
    """
    html = await fetch_html(url)
    if not html:
        # falha ao buscar HTML
        print(f"⚠️ fetch_html returned empty for {url}")
        return "Sem título", None, None

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # 1) tentar meta og:title ou title
    name = None
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        name = og['content'].strip()
    if not name:
        t = soup.find('title')
        if t:
            name = t.get_text(strip=True)

    # 2) seletores comuns para preço
    selectors = [
        '[itemprop=price]',
        '.price',
        '.preco',
        '.product-price',
        '.valor',
        '.price--main',
        '.product-price__price',
        '.price-amount',
        '.priceValue',
    ]

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            p, c = parse_price_from_text(el.get_text(" ", strip=True))
            if p is not None:
                return name or "Sem título", p, (c or "USD")

    # 3) meta tags product:price:amount / product:price:currency
    meta_price = soup.find('meta', property='product:price:amount')
    if meta_price and meta_price.get('content'):
        try:
            raw = meta_price['content'].strip().replace(',', '')
            p = float(raw)
            meta_curr = soup.find('meta', property='product:price:currency')
            curr = meta_curr['content'].strip() if meta_curr and meta_curr.get('content') else 'USD'
            return name or "Sem título", p, curr
        except Exception:
            pass

    # 4) fallback: procurar no texto bruto da página (regex)
    full_text = soup.get_text(" ", strip=True)
    p, c = parse_price_from_text(full_text)
    if p is not None:
        return name or "Sem título", p, (c or "USD")

    # Nenhum preço encontrado
    print(f"⚠️ Nenhum preço encontrado para {url} (pode ser bloqueio/HTML alterado).")
    # opcional: você pode logar parte do HTML para debug (cuidado com tamanho)
    # print(html[:800])
    return name or "Sem título", None, None
