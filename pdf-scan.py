import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

SAVE_FOLDER = "icab_pdfs"
BASE_URL = "https://www.icab.org.bd"

# ICAB এর common page গুলো যেখানে PDF থাকতে পারে
PAGES = [
    "/",
    "/page/publications",
    "/page/circulars",
    "/page/notices",
    "/page/downloads",
    "/page/annual-report",
    "/page/newsletters",
    "/page/journals",
    "/page/acts-rules",
    "/page/study-materials",
    "/page/exams",
    "/page/news",
]


def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return name[:200]  # max filename length


def download_pdf(pdf_url, save_folder):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": BASE_URL,
    }
    try:
        response = requests.get(pdf_url, headers=headers,
                                timeout=30, stream=True)
        if response.status_code == 200:
            # Filename বের করো URL থেকে
            filename = os.path.basename(urlparse(pdf_url).path)
            filename = sanitize_filename(filename)
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            filepath = os.path.join(save_folder, filename)
            # Duplicate হলে rename
            counter = 1
            base, ext = os.path.splitext(filepath)
            while os.path.exists(filepath):
                filepath = f"{base}_{counter}{ext}"
                counter += 1

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_kb = os.path.getsize(filepath) // 1024
            print(f"  ✅ {filename} ({size_kb} KB)")
            return True
        else:
            print(f"  ⚠️ HTTP {response.status_code}: {pdf_url[:70]}")
    except Exception as e:
        print(f"  ❌ Failed: {pdf_url[:70]} → {e}")
    return False


def extract_pdfs_from_page(page, url):
    """একটা page থেকে সব PDF link বের করো"""
    pdf_urls = set()

    print(f"\n📄 Scanning: {url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Scroll করো lazy content এর জন্য
        for _ in range(5):
            page.mouse.wheel(0, 1500)
            time.sleep(0.8)
        page.mouse.wheel(0, -99999)  # উপরে ফিরে যাও
        time.sleep(1)

    except Exception as e:
        print(f"  ⚠️ Page load error: {e}")
        return pdf_urls

    # ১. সব <a href> এ .pdf আছে কিনা দেখো
    links = page.query_selector_all("a[href]")
    for link in links:
        href = link.get_attribute("href") or ""
        if ".pdf" in href.lower():
            full_url = urljoin(
                BASE_URL, href) if href.startswith("/") else href
            if full_url.startswith("http"):
                pdf_urls.add(full_url)

    # ২. Page source থেকে PDF URL regex দিয়ে বের করো
    content = page.content()
    # http বা /path দিয়ে শুরু PDF link
    matches = re.findall(
        r'["\']((?:https?://[^"\']+|/[^"\']+)\.pdf(?:\?[^"\']*)?)["\']', content, re.IGNORECASE)
    for match in matches:
        full_url = urljoin(BASE_URL, match) if match.startswith("/") else match
        pdf_urls.add(full_url)

    # ৩. onclick বা data attribute এ PDF link থাকতে পারে
    onclick_matches = re.findall(
        r'(?:onclick|data-url|data-href)=["\']([^"\']*\.pdf[^"\']*)["\']', content, re.IGNORECASE)
    for match in onclick_matches:
        full_url = urljoin(BASE_URL, match) if match.startswith("/") else match
        if full_url.startswith("http"):
            pdf_urls.add(full_url)

    print(f"  → {len(pdf_urls)} PDFs found")
    return pdf_urls


def find_subpages(page, url):
    """Page এর ভেতরে আরও subpage link খোঁজো"""
    subpages = set()
    try:
        links = page.query_selector_all("a[href]")
        for link in links:
            href = link.get_attribute("href") or ""
            if href.startswith("/") and href != "/" and ".pdf" not in href.lower():
                full = BASE_URL + href
                subpages.add(full)
            elif href.startswith(BASE_URL) and ".pdf" not in href.lower():
                subpages.add(href)
    except:
        pass
    return subpages


def main():
    os.makedirs(SAVE_FOLDER, exist_ok=True)
    all_pdfs = set()
    visited = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
        bpage = context.new_page()

        # প্রথমে homepage load করো এবং সব internal link collect করো
        print("🔍 Discovering pages...")
        bpage.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        nav_links = find_subpages(bpage, BASE_URL)
        print(f"  → {len(nav_links)} internal pages found from homepage")

        # Pre-defined pages + discovered pages মেলাও
        all_pages = set([BASE_URL + p for p in PAGES]) | nav_links
        print(f"  → Total pages to scan: {len(all_pages)}")

        # প্রতিটা page scan করো
        for page_url in all_pages:
            if page_url in visited:
                continue
            visited.add(page_url)
            pdfs = extract_pdfs_from_page(bpage, page_url)
            all_pdfs.update(pdfs)

        browser.close()

    print(f"\n{'='*50}")
    print(f"📥 Total unique PDFs found: {len(all_pdfs)}")
    print(f"{'='*50}")

    if not all_pdfs:
        print("❌ কোনো PDF পাওয়া যায়নি।")
        return

    # Download করো
    downloaded = 0
    failed = 0
    for pdf_url in all_pdfs:
        if download_pdf(pdf_url, SAVE_FOLDER):
            downloaded += 1
        else:
            failed += 1

    print(f"\n🎉 Done!")
    print(f"  ✅ Downloaded : {downloaded}")
    print(f"  ❌ Failed     : {failed}")
    print(f"  📁 Saved in  : '{SAVE_FOLDER}/' folder")


if __name__ == "__main__":
    main()
