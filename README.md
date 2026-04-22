# 📸 Studio O — Image Downloader

A Python script to automatically download all images from [studiodoto.design](https://studiodoto.design) — including all project pages under `/works/`.

---

## 🚀 Features

- ✅ Handles JavaScript-rendered pages (React/Next.js)
- ✅ Auto-scrolls to trigger lazy-loaded images
- ✅ Scrapes `<img>`, `srcset`, and CSS `background-image`
- ✅ Crawls all individual project pages under `/works/`
- ✅ Skips duplicates and tiny/broken images
- ✅ Saves everything neatly into a local folder

---

## 📦 Requirements

- Python 3.8+
- [Playwright](https://playwright.dev/python/)
- [Requests](https://docs.python-requests.org/)

---

## ⚙️ Installation

```bash
pip install playwright requests
playwright install chromium
```

---

## ▶️ Usage

```bash
python scraper.py
```

All images will be saved in the `studioo_images/` folder by default.

---

## 🗂️ Project Structure

```
.
├── scraper.py          # Main script
├── README.md           # This file
└── studioo_images/     # Downloaded images (auto-created)
```

---

## 🔧 Configuration

You can change these variables at the top of `scraper.py`:

| Variable | Default | Description |
|---|---|---|
| `SAVE_FOLDER` | `"studioo_images"` | Folder to save downloaded images |
| `BASE_URL` | `"https://studiodoto.design"` | Target website URL |
| `PAGES` | `["/", "/works/", "/studio/", "/contact/"]` | Pages to scrape |

---

## 📄 How It Works

1. Launches a headless Chromium browser via Playwright
2. Visits each page and waits for JavaScript to fully render
3. Scrolls down the page to trigger lazy-loaded images
4. Collects image URLs from:
   - `<img src>` and `<img data-src>` attributes
   - `srcset` attributes
   - CSS `background-image` inline styles
5. Visits all individual project pages found under `/works/`
6. Downloads each unique image using `requests`

---

## ⚠️ Notes

- The script uses a real browser (headless Chromium), so it may take a few minutes to complete.
- Only images with valid extensions (`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.svg`, `.avif`) or image-related URLs are downloaded.
- Files with duplicate names are automatically renamed (e.g., `image.jpg`, `image_1.jpg`).

---

## 📝 License

For personal and educational use only. Please respect the website's content ownership.
