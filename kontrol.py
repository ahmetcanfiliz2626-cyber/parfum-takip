#!/usr/bin/env python3
"""dekantparfumdepo.com'a yeni eklenen ve tekrar stoğa giren ürünleri bulur, e-posta gönderir."""
import json, os, re, smtplib, subprocess, sys, time, urllib.request, html
from email.mime.text import MIMEText
from datetime import datetime

SITEMAP = "https://www.dekantparfumdepo.com/store-products-sitemap.xml"
DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "bilinen_urunler.json")
LOG = os.path.join(DIR, "yeni_urunler.log")
STOCK = os.path.join(DIR, "stok.json")
LISTING = "https://www.dekantparfumdepo.com/?sort=newest&page={}"
QUICK_PAGES = 3      # her dakika taranan "en yeniler" sayfası
FULL_EVERY = 10      # kaç turda bir bütün sayfalar taranır
EMAIL_TO = os.environ["EMAIL_TO"]
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]
UA = {"User-Agent": "Mozilla/5.0"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def details(url):
    try:
        h = get(url)
    except Exception:
        return url.rsplit("/", 1)[-1], "?"
    t = re.search(r'og:title" content="([^"]*)"', h)
    p = re.search(r'product:price:amount" content="([^"]*)"', h)
    name = html.unescape(t.group(1)).replace(" | Dekant Parfüm Depo", "") if t else url
    return name, (p.group(1) + " TL") if p else "?"

def send_mail(subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, SMTP_USER, EMAIL_TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

def listing_page(n):
    """Liste sayfasındaki ürünleri {url: (ad, fiyat, tükendi_mi)} olarak döndürür."""
    items = {}
    for chunk in re.split(r'data-hook="product-item-root"', get(LISTING.format(n)))[1:]:
        u = re.search(r'href="(https://www\.dekantparfumdepo\.com/product-page/[^"]+)"', chunk)
        if not u:
            continue
        name = re.search(r'data-hook="product-item-name"[^>]*>([^<]*)<', chunk)
        price = re.search(r'data-hook="product-item-price-to-pay"[^>]*>([^<]*)<', chunk)
        items[u.group(1)] = (html.unescape(name.group(1)).strip() if name else u.group(1).rsplit("/", 1)[-1],
                             html.unescape(price.group(1)).strip() if price else "?",
                             'aria-label="Tükendi"' in chunk)
    return items

def check_stock(full):
    """Tükendi iken satışa dönen ürünleri e-postayla bildirir."""
    prev = json.load(open(STOCK)) if os.path.exists(STOCK) else {}
    seen, n = {}, 1
    while full or n <= QUICK_PAGES:
        page = listing_page(n)
        if not page:
            break
        seen.update(page)
        n += 1
    back = [(u, name, price) for u, (name, price, sold_out) in seen.items() if prev.get(u) is True and not sold_out]
    prev.update({u: sold_out for u, (_, _, sold_out) in seen.items()})
    json.dump(prev, open(STOCK, "w"), ensure_ascii=False, indent=0, sort_keys=True)
    if not back:
        return
    body = f"{len(back)} parfüm tekrar stokta:\n\n" + "\n\n".join(f"• {name} — {price}\n  {u}" for u, name, price in back)
    print(body, flush=True)
    with open(LOG, "a") as f:
        f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M} ===\n{body}\n")
    send_mail(f"Dekant Parfüm Depo: {len(back)} parfüm tekrar stokta", body)
    print("E-posta gönderildi.", flush=True)

def main():
    if "--test-mail" in sys.argv:
        send_mail("Parfüm takip (bulut): test e-postası", "Bulut takibi çalışıyor. Yeni parfüm çıkınca buraya e-posta gelecek.")
        return
    urls = set(re.findall(r"<loc>(https://[^<]*/product-page/[^<]*)</loc>", get(SITEMAP)))
    if not urls:
        sys.exit("Sitemap boş geldi, durum güncellenmedi.")
    first_run = not os.path.exists(STATE)
    known = set() if first_run else set(json.load(open(STATE)))
    new = sorted(urls - known)
    json.dump(sorted(urls | known), open(STATE, "w"), ensure_ascii=False, indent=0)
    if first_run:
        print(f"İlk çalıştırma: {len(urls)} ürün kaydedildi, bundan sonra yeniler bildirilecek.")
        return
    if not new:
        print(f"{datetime.now():%Y-%m-%d %H:%M} yeni ürün yok ({len(urls)} ürün).", flush=True)
        return
    lines = []
    for u in new:
        name, price = details(u)
        lines.append(f"• {name} — {price}\n  {u}")
    body = f"{len(new)} yeni parfüm satışa çıktı:\n\n" + "\n\n".join(lines)
    print(body)
    with open(LOG, "a") as f:
        f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M} ===\n{body}\n")
    send_mail(f"Dekant Parfüm Depo: {len(new)} yeni parfüm", body)
    print("E-posta gönderildi.")

def save_to_git():
    subprocess.run(["git", "add", "bilinen_urunler.json", "stok.json", "yeni_urunler.log"], cwd=DIR)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=DIR).returncode:
        subprocess.run(["git", "commit", "-qm", "Yeni urunler"], cwd=DIR)
        subprocess.run(["git", "pull", "-q", "--rebase"], cwd=DIR)
        subprocess.run(["git", "push", "-q"], cwd=DIR)

def loop(minutes, interval=60):
    end = time.time() + minutes * 60
    turn = 0
    while time.time() < end:
        start = time.time()
        try:
            main()
            check_stock(full=turn % FULL_EVERY == 0)
            if "--git" in sys.argv:
                save_to_git()
        except Exception as e:
            print(f"{datetime.now():%H:%M} hata, sonraki turda tekrar denenecek: {e}", flush=True)
        turn += 1
        time.sleep(max(0, interval - (time.time() - start)))

if __name__ == "__main__":
    if "--loop" in sys.argv:
        loop(int(sys.argv[sys.argv.index("--loop") + 1]))
    else:
        main()
        check_stock(full=True)
