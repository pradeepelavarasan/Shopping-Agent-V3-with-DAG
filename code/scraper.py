import asyncio
import random
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def handle_amazon_interstitials(page):
    """Detects and clicks 'Continue shopping' or similar bot-check buttons."""
    try:
        await asyncio.sleep(random.uniform(2.0, 4.0))
        continue_btn = await page.query_selector('text="Continue shopping"')
        if not continue_btn:
            continue_btn = await page.query_selector('a:has-text("Continue shopping")')
        
        if continue_btn:
            print("[scraper] Detected 'Continue shopping' interstitial. Clicking to proceed...")
            await continue_btn.click()
            await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception as e:
        print(f"[scraper] Interstitial handler exception (ignored): {e}")

# Global lock to serialize Amazon page requests and avoid simultaneous connections triggering bot detection
_scrape_lock = asyncio.Lock()

async def playwright_fetch(url: str) -> str:
    """Stealthily fetches a URL page content using Playwright to evade anti-bot checks."""
    async with _scrape_lock:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            print(f"[scraper] Fetching URL: {url} (Attempt {attempt}/{max_retries})")
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=False,
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                        viewport={"width": 1280, "height": 800}
                    )
                    page = await context.new_page()
                    await Stealth().apply_stealth_async(page)
                    
                    # Initial human delay
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await handle_amazon_interstitials(page)
                    
                    # Delay to allow dynamic scripts to load
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    
                    # Extract title and text content
                    title = await page.title()
                    if "Sorry" in title or "Robot" in title or "CAPTCHA" in title or "Robot Check" in title:
                        await browser.close()
                        raise RuntimeError("Amazon bot detection triggered. Could not fetch page.")
                        
                    body_text = await page.inner_text("body")
                    
                    # Extract Amazon product links to prevent the model from inventing mock URLs
                    links = []
                    try:
                        links = await page.evaluate("""() => {
                            let results = Array.from(document.querySelectorAll('div[data-component-type="s-search-result"]'));
                            return results.map(item => {
                                let asin = item.getAttribute('data-asin') || "";
                                let titleEl = item.querySelector('h2');
                                let title = titleEl ? titleEl.innerText.trim() : "";
                                let linkEl = item.querySelector('h2 a') || item.querySelector('a.a-link-normal');
                                let href = linkEl ? linkEl.href : "";
                                let imgEl = item.querySelector('.s-image');
                                let imgSrc = imgEl ? imgEl.src : "";
                                return {
                                    asin: asin,
                                    title: title,
                                    href: href,
                                    imgSrc: imgSrc
                                };
                            }).filter(x => x.asin && x.href);
                        }""")
                    except Exception as le:
                        print(f"[scraper] Link extraction exception (ignored): {le}")
                    
                    await browser.close()
                    
                    link_lines = []
                    seen_asins = set()
                    for l in links:
                        asin = l['asin'].upper()
                        if asin not in seen_asins:
                            seen_asins.add(asin)
                            href = l['href']
                            if not href.startswith('http'):
                                from urllib.parse import urljoin
                                href = urljoin(url, href)
                            title_text = l['title'].replace('\n', ' ') if l['title'] else "Product Link"
                            link_lines.append(f"- ASIN: {asin} | Title: {title_text} | URL: {href} | Image: {l['imgSrc']}")
                    
                    links_summary = ""
                    if link_lines:
                        links_summary = "DISCOVERED AMAZON PRODUCT LINKS (ASIN AND URL):\n" + "\n".join(link_lines) + "\n\n"
                    
                    # For product detail pages (/dp/), extract the main image URL via JS
                    # after the page has fully rendered (so src is the real image, not a spacer GIF)
                    product_image_line = ""
                    if "/dp/" in url:
                        try:
                            img_url = await page.evaluate("""() => {
                                const img = document.querySelector('#landingImage') ||
                                            document.querySelector('#imgBlkFront') ||
                                            document.querySelector('.a-dynamic-image');
                                if (!img) return '';
                                // data-old-hires is the clearest high-res attribute
                                const hires = img.getAttribute('data-old-hires');
                                if (hires && hires.startsWith('http')) return hires;
                                // Fall back to rendered src (JS will have set this to real URL)
                                const src = img.src || '';
                                // Reject base64 spacers
                                if (src.startsWith('data:') || src.includes('transparent-pixel')) return '';
                                return src;
                            }""")
                            if img_url:
                                product_image_line = f"PRODUCT IMAGE URL: {img_url}\n\n"
                                print(f"[scraper] Extracted product image: {img_url}")
                        except Exception as ie:
                            print(f"[scraper] Image extraction exception (ignored): {ie}")
                    
                    # Format a minimal output container with links at the top to prevent truncation
                    return f"PAGE TITLE: {title}\n\n{product_image_line}{links_summary}PAGE BODY:\n{body_text}"
            except Exception as e:
                print(f"[scraper] Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    delay = random.uniform(5.0, 10.0)
                    print(f"[scraper] Waiting {delay:.2f} seconds before retrying...")
                    await asyncio.sleep(delay)
                else:
                    print(f"[scraper] Max retries reached. Giving up.")
                    raise e
