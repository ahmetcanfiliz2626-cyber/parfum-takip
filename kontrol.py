#!/usr/bin/env python3
"""dekantparfumdepo.com'a yeni eklenen ürünleri bulur, bildirim ve e-posta gönderir."""
import json, os, re, smtplib, sys, urllib.request, html
from email.mime.text import MIMEText
from datetime import datetime

SITEMAP = "https://www.dekantparfumdepo.com/store-products-sitemap.xml"
DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "bilinen_urunler.json")
LOG = os.path.join(DIR, "yeni_urunler.log")
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
        print(f"{datetime.now():%Y-%m-%d %H:%M} yeni ürün yok ({len(urls)} ürün).")
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

if __name__ == "__main__":
    main()
