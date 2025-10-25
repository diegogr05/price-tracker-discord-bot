import aiohttp
from bs4 import BeautifulSoup
import json
import re
from typing import Optional, Tuple
from config import USER_AGENT

# Aceita R$, US$, USD, ₲ e números com . ou , como separador
CURRENCY_REGEX = re.compile(r'(R\$|US\$|USD|₲)?\s*([0-9]{1,3}(?:[.\s][0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:\.[0-9]{2}))')

def _normalize_number(num_str: str) -> Optional[float]:
    """
    Converte '4.399,00' -> 4399.00, '4399.00' -> 4399.0, etc.
    """
    if not num_str:
        return None
    ns = num_str.replace('\xa0', ' ').strip()
    # remove separador de milhar (ponto/espaço) e troca vírgula por ponto
    ns = ns.replace('.', '').replace(' ', '').replace(',', '.')
    try:
        return float(ns)
    except:
        return None

async def fetch_html(url: str, user_agent: Optional[str] = USER_AGENT) -> str:
    """
    Busca HTML com headers mais realistas e logs de status/bloqueio.
    """
    headers = {
        "User-Agent": user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=30, allow_redirects=True) as resp:
                status = resp.status
                if status != 200:
                    print(f"⚠️ fetch_html: {url} -> status {status}")
                html = await resp.text()
                # Sinais comuns de bloqueio via Cloudflare / página de desafio
                if status in (403, 503) or "cf-chl-bypass" in html.lower() or "attention required" in html.lower():
                    print("⚠️ Possível bloqueio/Cloudflare na página, HTML retornado não é o produto.")
                if not html.strip():
                    print("⚠️ HTML vazio retornado, possível bloqueio de scraper.")
                return html
    except Exception as e:
        print(f"❌ Erro em fetch_html({url}): {e}")
        return ""

def parse_price_from_text(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Tenta extrair (preço, moeda) de um texto livre.
    """
    if not text:
        return None, None
    m = CURRENCY_REGEX.search(text.replace('\xa0', ' '))
    if not m:
        return None, None
    currency = (m.group(1) or '').strip()
    value = _normalize_number(m.group(2))
    return value, currency if currency else None

def _extract_from_meta_or_tag(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[str]]:
    """
    Pega preço de meta/itemprop e classes comuns.
    """
    # itemprop=price com atributo content
    tag = soup.find(attrs={"itemprop": "price"})
    if tag:
        # às vezes vem em content
        content = tag.get("content")
        if content:
            val = _normalize_number(content)
            if val is not None:
                # moeda pode vir em [itemprop=priceCurrency]
                cur_tag = soup.find(attrs={"itemprop": "priceCurrency"})
                currency = cur_tag.get("content").strip() if cur_tag and cur_tag.get("content") else None
                return val, currency
        # ou no texto
        val, cur = parse_price_from_text(tag.get_text(" ", strip=True))
        if val is not None:
            return val, cur

    # classes/seletores comuns
    for sel in ('.price', '.preco', '.product-price', '.valor', '.price--main', '.product-price__price', '.price-amount'):
        el = soup.select_one(sel)
        if el:
            val, cur = parse_price_from_text(el.get_text(" ", strip=True))
            if val is not None:
                return val, cur

    # metas: product:price:amount / product:price:currency
    meta_price = soup.find('meta', attrs={"property": "product:price:amount"})
    if meta_price and meta_price.get('content'):
        val = _normalize_number(meta_price['content'])
        if val is not None:
            meta_curr = soup.find('meta', attrs={"property": "product:price:currency"})
            currency = meta_curr['content'].strip() if meta_curr and meta_curr.get('content') else None
            return val, currency

    return None, None

def _extract_from_ld_json(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[str]]:
    """
    Varre <script type="application/ld+json"> procurando Product/Offer.
    """
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            data = json.loads(s.string or s.text or "{}")
        except Exception:
            # alguns sites embutem múltiplos JSONs em lista
            try:
                data = json.loads((s.string or s.text or "").strip().split("\n", 1)[0])
            except Exception:
                continue

        # pode ser dict ou lista
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            t = str(node.get("@type", "")).lower()
            if "product" in t or "offer" in t:
                # Offer pode estar aninhado em "offers"
                offers = node.get("offers")
                if isinstance(offers, dict):
                    price = (offers.get("price") or offers.get("lowPrice") or offers.get("highPrice"))
                    cur = offers.get("priceCurrency")
                    val = _normalize_number(str(price)) if price is not None else None
                    if val is not None:
                        return val, cur
                elif isinstance(offers, list):
                    for off in offers:
                        if not isinstance(off, dict):
                            continue
                        price = (off.get("price") or off.get("lowPrice") or off.get("highPrice"))
                        cur = off.get("priceCurrency")
                        val = _normalize_number(str(price)) if price is not None else None
                        if val is not None:
                            return val, cur

                # Alguns sites guardam em "priceSpecification"
                ps = node.get("priceSpecification")
                if isinstance(ps, dict):
                    price = ps.get("price")
                    cur = ps.get("priceCurrency")
                    val = _normalize_number(str(price)) if price is not None else None
                    if val is not None:
                        return val, cur
    return None, None

async def scrape_product_page(url: str) -> Tuple[str, Optional[float], Optional[str]]:
    """
    Retorna (nome, preço, moeda) para uma URL do ComprasParaguai.
    """
    html = await fetch_html(url)
    if not html:
        print("⚠️ scrape_product_page: HTML vazio, abortando.")
        return "Sem título", None, None

    soup = BeautifulSoup(html, 'html.parser')

    # Nome do produto
    name = None
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        name = og['content'].strip()
    if not name:
        title = soup.find('title')
        if title:
            name = title.get_text(strip=True)
    if not name:
        name = "Sem título"

    # 1) Seletores e metas
    val, cur = _extract_from_meta_or_tag(soup)
    if val is not None:
        print(f"✅ Preço encontrado (tag/meta): {val} {cur or ''}")
        return name, val, cur or "USD"

    # 2) JSON-LD
    val, cur = _extract_from_ld_json(soup)
    if val is not None:
        print(f"✅ Preço encontrado (ld+json): {val} {cur or ''}")
        return name, val, cur or "USD"

    # 3) Fallback: regex no HTML bruto
    val, cur = parse_price_from_text(html)
    if val is not None:
        print(f"✅ Preço encontrado (regex fallback): {val} {cur or ''}")
        return name, val, cur or "USD"

    print(f"⚠️ Nenhum preço encontrado para {url}")
    return name, None, None
