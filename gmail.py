from imap_tools import MailBox, AND
import datetime
from bs4 import BeautifulSoup
import re

class GmailUtils:
    @staticmethod
    def extract_links_with_prices(html_content):
        """HTML içeriğinden linkleri ve yakınlarındaki fiyatları çıkart"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links_with_prices = []
        seen = set()

        # Tüm <a> etiketlerini tarayıp ilan linki olabilecekleri seç
        for a in soup.find_all('a', href=True):
            href = a['href']
            if ("/ilan/" in href) or ("shbdn.com" in href) or ("sahibinden.com/ilan/" in href):
                link = href

                # Aynı kapsayıcıda veya birkaç seviye üstte fiyatı aramak için metin topla
                fragments = []
                el = a
                for _ in range(5):
                    if el is None:
                        break
                    fragments.append(el.get_text(" ", strip=True))
                    # Sonraki kardeşlerin metinlerini de al
                    for sib in el.find_next_siblings():
                        fragments.append(sib.get_text(" ", strip=True))
                    el = el.parent

                combined = " ".join([f for f in fragments if f])

                price = None
                # Örnek: "Fiyat: 3.325.000 TL" veya "3.325.000 TL"
                m = re.search(r'Fiyat[:\s]*([\d\.\s,]+\s*(?:TL|₺))', combined, flags=re.IGNORECASE)
                if not m:
                    m = re.search(r'([\d\.\s,]+)\s*(TL|₺)', combined, flags=re.IGNORECASE)

                if m:
                    # Birinci regex grubunda para birimi dahil olabilir
                    if len(m.groups()) == 1:
                        price = m.group(1).strip()
                    else:
                        price = (m.group(1) + ' ' + (m.group(2) or '')).strip()

                if link not in seen:
                    seen.add(link)
                    links_with_prices.append({
                        'link': link,
                        'price': price if price else 'Fiyat bilgisi yok'
                    })

        return links_with_prices
    
    @staticmethod
    def read_emails_with_app_password(user_email, app_password, subject_query=''):
        try:
            with MailBox('imap.gmail.com').login(user_email, app_password, 'INBOX') as mailbox:
                today = datetime.date.today()
                email_list = []
                
                # Bugün gelen mailleri çek
                criteria = AND(subject=subject_query, from_='sahibinden.com', date=today)
                
                for msg in mailbox.fetch(criteria, charset='utf-8'):
                    # HTML içeriğini işle
                    # soup = BeautifulSoup(msg.html, 'html.parser')
                    
                    # Linkleri fiyatlarıyla birlikte çıkart
                    links_with_prices = GmailUtils.extract_links_with_prices(msg.html)
                    
                    email_list.append({
                        "subject": msg.subject,
                        "date": msg.date,
                        "links_with_prices": links_with_prices
                    })
                return email_list
        except Exception as e:
            print(f"Hata oluştu: {e}")
            return []
  

    @staticmethod
    def read_emails_within_26Hours(user_email, app_password, subject_query='', hours_back=26):
        try:
            with MailBox('imap.gmail.com').login(user_email, app_password, 'INBOX') as mailbox:
                email_list = []

                now = datetime.datetime.now(datetime.timezone.utc)
                threshold = now - datetime.timedelta(hours=hours_back)

                # 🔥 KRİTERİ DOĞRU KUR
                if subject_query:
                    criteria = AND(from_='sahibinden', subject=subject_query)
                else:
                    criteria = AND(from_='sahibinden')

                # 🔍 Debug için: son gelenlerden başla
                for msg in mailbox.fetch(criteria, reverse=True, limit=50, charset='utf-8'):

                    if not msg.date:
                        continue

                    msg_date = msg.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=datetime.timezone.utc)

                    if msg_date < threshold:
                        continue

                    html_content = msg.html or ""
                    links_with_prices = GmailUtils.extract_links_with_prices(html_content)

                    email_list.append({
                        "subject": msg.subject,
                        "date": msg_date,
                        "links_with_prices": links_with_prices
                    })

                return email_list

        except Exception as e:
            print(f"Hata oluştu: {e}")
            return []
