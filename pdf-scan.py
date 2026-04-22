import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

SAVE_FOLDER = "icab_pdfs"
BASE_URL = "https://www.icab.org.bd"

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
    return name[:200]


def download_pdf(pdf_url, save_folder):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": BASE_URL,
    }
    try:
        response = requests.get(pdf_url, headers=headers,
                                timeout=30, stream=True)
        if response.status_code == 200:
            filename = os.path.basename(urlparse(pdf_url).path)
            filename = sanitize_filename(filename)
            if not filename or filename == ".pdf":
                filename = f"doc_{hash(pdf_url) % 100000}.pdf"
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            filepath = os.path.join(save_folder, filename)
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


def safe_goto(page, url, retries=2):
    """Timeout-safe page navigation — networkidle এর বদলে domcontentloaded ব্যবহার করে"""
    for attempt in range(retries):
        try:
            # networkidle এর বদলে domcontentloaded — অনেক দ্রুত
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # JS render এর জন্য একটু অপেক্ষা
            time.sleep(3)
            return True
        except Exception as e:
            print(f"  ⚠️ Attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return False


def extract_pdfs_from_page(page, url):
    pdf_urls = set()

    print(f"\n📄 Scanning: {url}")

    if not safe_goto(page, url):
        print(f"  ❌ Skipping (could not load)")
        return pdf_urls

    # Scroll করো
    try:
        for _ in range(4):
            page.mouse.wheel(0, 1500)
            time.sleep(0.6)
    except:
        pass

    # ১. <a href> এ .pdf
    try:
        links = page.query_selector_all("a[href]")
        for link in links:
            href = link.get_attribute("href") or ""
            if ".pdf" in href.lower():
                full_url = urljoin(BASE_URL, href) if not href.startswith(
                    "http") else href
                pdf_urls.add(full_url)
    except Exception as e:
        print(f"  ⚠️ Link scan error: {e}")

    # ২. Page source থেকে regex
    try:
        content = page.content()
        matches = re.findall(
            r'["\']((?:https?://[^"\']+|/[^"\']+)\.pdf(?:\?[^"\']*)?)["\']',
            content, re.IGNORECASE
        )
        for match in matches:
            full_url = urljoin(
                BASE_URL, match) if match.startswith("/") else match
            pdf_urls.add(full_url)
    except Exception as e:
        print(f"  ⚠️ Regex scan error: {e}")

    print(f"  → {len(pdf_urls)} PDFs found")
    return pdf_urls


def find_subpages(page):
    """Homepage থেকে internal link collect করো"""
    subpages = set()
    try:
        links = page.query_selector_all("a[href]")
        for link in links:
            href = link.get_attribute("href") or ""
            if (href.startswith("/") and href != "/" and
                    ".pdf" not in href.lower() and
                    "mailto" not in href and
                    "tel:" not in href):
                subpages.add(BASE_URL + href)
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
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            # Slow site এর জন্য timeout বাড়ানো
            java_script_enabled=True,
        )
        bpage = context.new_page()
        # Default timeout বাড়াও
        bpage.set_default_timeout(45000)

        # Homepage load
        print("🔍 Loading homepage...")
        if not safe_goto(bpage, BASE_URL):
            print("❌ Homepage load failed। Internet connection বা site check করুন।")
            browser.close()
            return

        print("✅ Homepage loaded!")

        # Internal links discover
        nav_links = find_subpages(bpage)
        print(f"  → {len(nav_links)} internal pages found")

        # সব pages একসাথে
        predefined = set([BASE_URL + p for p in PAGES])
        all_pages = predefined | nav_links
        print(f"  → Total pages to scan: {len(all_pages)}\n")

        # প্রতিটা page scan
        for page_url in all_pages:
            if page_url in visited:
                continue
            visited.add(page_url)
            pdfs = extract_pdfs_from_page(bpage, page_url)
            all_pdfs.update(pdfs)

        browser.close()

    print(f"\n{'='*50}")
    print(f"📥 Total unique PDFs found: {len(all_pdfs)}")
    print(f"{'='*50}\n")

    if not all_pdfs:
        print("❌ কোনো PDF পাওয়া যায়নি।")
        return

    downloaded = 0
    failed = 0
    for pdf_url in sorted(all_pdfs):
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
