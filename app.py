import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

# ডাউনলোড করার folder
SAVE_FOLDER = "studioo_images"
BASE_URL = "https://studiodoto.design"

# Website এর সব page গুলো
PAGES = [
    "/",
    "/works/",
    "/studio/",
    "/contact/",
]


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def download_image(img_url, save_folder, filename=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": BASE_URL,
    }
    try:
        response = requests.get(img_url, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.content) > 1000:
            if not filename:
                filename = os.path.basename(urlparse(img_url).path)
            filename = sanitize_filename(filename)
            if not filename or "." not in filename:
                filename = f"image_{hash(img_url) % 100000}.jpg"

            filepath = os.path.join(save_folder, filename)
            # Same name হলে rename করো
            counter = 1
            base, ext = os.path.splitext(filepath)
            while os.path.exists(filepath):
                filepath = f"{base}_{counter}{ext}"
                counter += 1

            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"  ✅ {filename}")
            return True
    except Exception as e:
        print(f"  ❌ Failed: {img_url[:60]} → {e}")
    return False


def scrape_page_images(page, url):
    """একটা page থেকে সব image URL collect করো"""
    img_urls = set()

    print(f"\n📄 Loading: {url}")
    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(3)  # JS render হওয়ার জন্য অপেক্ষা

    # Scroll করো যাতে lazy-load images load হয়
    for _ in range(5):
        page.mouse.wheel(0, 1500)
        time.sleep(1)

    # ১. সব <img> tag থেকে src নাও
    imgs = page.query_selector_all("img")
    for img in imgs:
        for attr in ["src", "data-src", "data-lazy-src", "data-original"]:
            src = img.get_attribute(attr)
            if src and src.startswith("http"):
                img_urls.add(src)
            elif src and src.startswith("/"):
                img_urls.add(urljoin(BASE_URL, src))

    # ২. CSS background-image থেকে URL নাও
    elements = page.query_selector_all("[style*='background']")
    for el in elements:
        style = el.get_attribute("style") or ""
        matches = re.findall(
            r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', style)
        img_urls.update(matches)

    # ৩. Network থেকে image request intercept (page source থেকে)
    content = page.content()
    # srcset থেকে URL বের করো
    srcset_matches = re.findall(r'srcset="([^"]+)"', content)
    for srcset in srcset_matches:
        for part in srcset.split(","):
            src = part.strip().split(" ")[0]
            if src.startswith("http"):
                img_urls.add(src)
            elif src.startswith("/"):
                img_urls.add(urljoin(BASE_URL, src))

    return img_urls


def main():
    os.makedirs(SAVE_FOLDER, exist_ok=True)
    all_images = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
        page = context.new_page()

        # প্রতিটা page scrape করো
        for path in PAGES:
            url = BASE_URL + path
            try:
                imgs = scrape_page_images(page, url)
                print(f"  → {len(imgs)} images found")
                all_images.update(imgs)
            except Exception as e:
                print(f"  ⚠️ Error on {url}: {e}")

        # Works page এ individual project links থাকতে পারে
        try:
            page.goto(BASE_URL + "/works/",
                      wait_until="networkidle", timeout=30000)
            time.sleep(2)
            links = page.query_selector_all("a[href]")
            project_links = set()
            for link in links:
                href = link.get_attribute("href") or ""
                if "/works/" in href and href != "/works/" and len(href) > 8:
                    full_url = urljoin(BASE_URL, href)
                    if full_url.startswith(BASE_URL):
                        project_links.add(full_url)

            print(f"\n🔗 Found {len(project_links)} project pages")
            for proj_url in list(project_links)[:20]:  # max 20 project
                try:
                    imgs = scrape_page_images(page, proj_url)
                    print(f"  → {len(imgs)} images found")
                    all_images.update(imgs)
                except Exception as e:
                    print(f"  ⚠️ Error: {e}")
        except Exception as e:
            print(f"⚠️ Works page error: {e}")

        browser.close()

    # Filter: শুধু real image URL রাখো
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif"}
    filtered = set()
    for url in all_images:
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in image_exts):
            filtered.add(url)
        elif "image" in url.lower() or "photo" in url.lower() or "media" in url.lower():
            filtered.add(url)

    print(f"\n📥 Total unique images to download: {len(filtered)}")

    # Download করো
    downloaded = 0
    for img_url in filtered:
        if download_image(img_url, SAVE_FOLDER):
            downloaded += 1

    print(f"\n🎉 Done! Downloaded: {downloaded}/{len(filtered)} images")
    print(f"📁 Saved in: '{SAVE_FOLDER}' folder")


if __name__ == "__main__":
    main()
