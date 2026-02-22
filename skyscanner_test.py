
import csv
import datetime
import time
import random
import pytest
import uuid
import os
import shutil
from playwright.sync_api import Playwright, sync_playwright
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv    
from imap_tools import MailBox, AND
from bs4 import BeautifulSoup
# import re

load_dotenv()  # .env dosyasını yükle

@pytest.fixture(scope="session")
def browserSkyscanner(playwright: Playwright):
    # Her test oturumu için benzersiz bir klasör adı
    temp_profile = f"/tmp/skyscanner_{uuid.uuid4()}"
    
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=temp_profile,
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    page = context.pages[0]
    yield page
    
    context.close()
    # Test bittiğinde klasörü temizle (Incognito etkisi)
    if os.path.exists(temp_profile):
        shutil.rmtree(temp_profile)

def convertDateFormat(dateStr):
    # Convert date from DD.MM.YYYY to YYMMDD
    day = dateStr[0:2]
    month = dateStr[3:5]
    year = dateStr[8:10]
    return f"{year}{month}{day}"

def simulate_human_mouse_movement(page, start_x, start_y, end_x, end_y):
    """İnsan benzeri mouse hareketi simülasyonu"""
    steps = random.randint(20, 40)
    points = []
    
    # Bezier eğrisi için kontrol noktaları
    cp1_x = start_x + (end_x - start_x) * random.uniform(0.3, 0.5)
    cp1_y = start_y + (end_y - start_y) * random.uniform(0.2, 0.4)
    cp2_x = start_x + (end_x - start_x) * random.uniform(0.6, 0.8)
    cp2_y = start_y + (end_y - start_y) * random.uniform(0.6, 0.8)
    
    for i in range(steps):
        t = i / steps
        # Kübik Bezier eğrisi
        x = (1-t)**3 * start_x + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * end_x
        y = (1-t)**3 * start_y + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * end_y
        
        # Rastgele küçük sapmalar ekle
        x += random.uniform(-2, 2)
        y += random.uniform(-2, 2)
        
        points.append((x, y))
    
    # Hareketi gerçekleştir
    for x, y in points:
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.01, 0.05))

def checkAndCloseModal(page):
    try:

        # Sayfanın stabil hale gelmesi için çok kısa bir bekleme
        page.wait_for_timeout(1000)

        # 1. Strateji: Doğrudan aria-label kullanarak kapatma (En garanti yol)
        # Görseldeki 'İletişim kutusunu kapatın' metni tam olarak budur
        close_labels = ["İletişim kutusunu kapatın", "Close dialog", "Close"]
        for label in close_labels:
            btn = page.get_by_label(label).first
            if btn.is_visible(timeout=500):
                btn.click(force=True) # force=True, bazen üstte başka katman varsa tıklamayı zorlar
                print(f"Modal '{label}' etiketi ile kapatıldı.")
                return

        # 2. Strateji: Görseldeki özel sınıf isimlerini hedefle
        # 'CloseButton_close_button_container' sınıfı görsellerde net şekilde seçili
        specific_selectors = [
            "button[class*='CloseButton_close_button_container']",
            "button[class*='BpkCloseButton']",
            "div[class*='CloseButton_close_button'] button"
        ]
        
        for selector in specific_selectors:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=500):
                btn.click(force=True)
                print(f"Modal {selector} seçicisi ile kapatıldı.")
                return

        # 3. Strateji: "Devam Et" butonunu yakala (Ödemeler ekranı için)
        continue_btn = page.get_by_role("button", name="Devam Et").first
        if continue_btn.is_visible(timeout=500):
            continue_btn.click()
            print("Modal 'Devam Et' butonu ile geçildi.")
        # page.refresh()
        page.wait_for_timeout(2000)


        close_x_button = page.locator("button[class*='BpkCloseButton']")
        close_dialog = page.get_by_label("İletişim kutusunu kapatın")
        if close_x_button.is_visible():
            close_x_button.click()
            print("Modal 'X' butonu ile kapatıldı.")
        elif close_dialog.is_visible():
            close_dialog.click()
            print("Erişilebilirlik etiketi ile modal kapatıldı.")   
        page.wait_for_timeout(500)
    except:
        pass

def test_skyscanner(browserSkyscanner):
    page = browserSkyscanner
    url = "https://www.skyscanner.com"
    page.goto(url)
    page.wait_for_timeout(1000)
    passCaptcha(url, page.url, page)
    checkAndCloseModal(page)

    print("\nTarayıcı başarıyla açıldı ve skyscanner.com'a gidildi.")
    flightList = []
    with open('flightInfoList.csv', mode='r') as file:
        csvreader = csv.reader(file)
        header = next(csvreader)  # Skip header
        count = 0
        
        for row in csvreader:
            values_list = []
            print(row)
            # get values from csv and lowercase them for fromStr and toStr  
            fromStr = row[0].lower()
            toStr = row[1].lower()
            departDate = convertDateFormat(row[2])

            print(f"\n{fromStr} - {toStr} için {departDate} tarihli uçuş aranıyor...")

            url = f"https://www.skyscanner.com.tr/tasima/ucak-bileti/{fromStr}/{toStr}/{departDate}/?adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=0&preferdirects=false&outboundaltsenabled=false&inboundaltsenabled=false&stops=!oneStop,!twoPlusStops"
            print(f"Gidilen URL: {url}")
            #https://www.skyscanner.com.tr/tasima/ucak-bileti/esb/fran/260320/config/11389-2603201350--32570-0-11616-2603201530?adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=0&outboundaltsenabled=false&inboundaltsenabled=false&stops=!oneStop,!twoPlusStops
            #https://www.skyscanner.com.tr/tasima/ucak-bileti/fra/esb/260209/?adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=0&preferdirects=false&outboundaltsenabled=false&inboundaltsenabled=false&stops=!oneStop,!twoPlusStops
            page.goto(url)
            page.wait_for_timeout(3000)  # Arama sonuçlarını görmek için 5 saniye bekle
            checkAndCloseModal(page)
       
            # get page url and print it
            current_url = page.url
            print(f"Current URL: {current_url}")
            checkAndCloseModal(page)


            # print("Frame bilgileri:")
            # print(page.frames)

            passCaptcha(url, current_url, page)  
            checkAndCloseModal(page)
        
            ticket_container = page.locator("div[class*='EcoTicketWrapper_ecoContainer']")
            ticket_count = ticket_container.count()
            print(f"Bulunan bilet sayısı: {ticket_count}")
            #img[class*='BpkImage_bpk-image__img']
            # flightFirm = page.locator(f"img[class*='BpkImage_bpk-image__img'].nth({count}).locator('..')")
            # firmName = flightFirm.get_attribute("alt")
            # print(f"Uçuş Firması: {firmName}")

            for i in range(ticket_count):               
                checkAndCloseModal(page)
                ticketsUrl = page.url

                ticket = ticket_container.nth(i)
                # ticket.locator("div[class*='TicketStubContent_ctaButtonContainer']").click()
                # page.wait_for_timeout(3000)  # Detayları görmek için 1 saniye bekle
                checkAndCloseModal(page)

                price_text = ticket.locator("div[class*='Price_mainPrice']").inner_text()
                print(f"\nBilet {i+1} için fiyat: {price_text.strip()}")

                airline_locators = page.locator("div[class*='LegDetails_container'] img")
                # airline_count = airline_locators.count()
                # print(f"  Uçuş için bulunan havayolu sayısı: {airline_count}")
                airline = airline_locators.nth(i).get_attribute("alt")
                print(f"Havayolu: {airline}")

                flightDict = {
                    "price": price_text.strip(),
                    "provider": "Skyscanner",
                    "from": fromStr,
                    "to": toStr,
                    "departDate": row[2],
                    "airline": airline,
                    "url": ticketsUrl
                }

                flightList.append(flightDict)

                # for j in range(pricing_count):
                #     flightDict = {}
                #     checkAndCloseModal(page)
                #     pricing = PricingItems.nth(j)# Fiyat bilgisini çek
                #     values = pricing.inner_text()
                #     typeOfValues = type(values)
                #     print(f"    Fiyat seçeneği {j+1} türü: {typeOfValues}")
                #     print(values)
                #     # convert values to list by line break
                #     # valueListmap = map(values_list.append(v) for v in values.split("\n"))
                #     # print(f"valueListmap: {valueListmap}")
                #     values_list = values.split("\n")
                #     print(f"    Fiyat seçeneği {j+1} liste: {values_list}")
                #     # first item is price, second item is provider
                #     price_text = values_list[9]
                #     price_text1 = values_list[10]
                #     # price_text2 = values_list[11]
                #     # price_text3 = values_list[12]
                #     provider_text = values_list[0]  

                #     # # print price tests
                #     print(price_text)
                #     print(price_text1)
                #     # print(price_text2)
                #     # print(price_text3)
                   
                #     flightDict = {
                #         "price": price_text.strip(),
                #         "provider": provider_text.strip(),
                #         "from": fromStr,
                #         "to": toStr,
                #         "departDate": row[2],
                #         "airline": airline,
                #         "url": ticketsUrl
                #     }

                #     print(f"\nUçuş Detayları: {flightDict}")
                #     flightList.append(flightDict)
                #     print(f"    Fiyat seçeneği {j+1}: {price_text.strip()} - Sağlayıcı: {provider_text.strip()}")
                #     print(f"    ----------------  Diğer satıcı  -------------------")

                # page.go_back()
                # page.wait_for_timeout(1000)  # Geri dönmeyi bekle

            

            print(f"\nFlight search from {fromStr} to {toStr} on {row[2]} completed successfully.")
            count += 1
        print(f"\nTüm uçuş aramaları tamamlandı. Toplam uçuş detayı sayısı: {len(flightList)}")
        print(f"\nUçuş Detayları Listesi:")
        for flight in flightList:
            print(flight)       

            print(f"----------------------------------------------------------------------")

    # convert flightList to html  to acttch to a mail
    with open('flightDetails.html', 'w', encoding='utf-8') as f:
        f.write('<html><head><meta charset="UTF-8"></head><body>')
        f.write('<h1>Uçuş Detayları</h1>')
        f.write('<table border="1"><tr><th>From</th><th>To</th><th>Depart Date</th><th>Airline</th><th>Price</th><th>Provider</th><th>URL</th></tr>')
        for flight in flightList:
            f.write(f"<tr><td>{flight['from']}</td><td>{flight['to']}</td><td>{flight['departDate']}</td><td>{flight['airline']}</td><td>{flight['price']}</td><td>{flight['provider']}</td><td><a href='{flight['url']}'>Link</a></td></tr>")
        f.write('</table></body></html>')   
    
    send_html_email(
        message=open('flightDetails.html', 'r', encoding='utf-8').read(),
        subject="Uçuş Detayları Raporu",
        to_address=os.getenv("TO_MAIL"),
        from_address=os.getenv("FROM_MAIL")
    )



def send_html_email(message, subject, to_address, from_address):
    # Gmail SMTP ayarları
    host = "smtp.gmail.com"
    port = 465
    # ConfigurationReader yerine doğrudan şifreyi veya bir env değişkenini alabilirsiniz
    app_password = os.getenv("APP_PASSWORD")  # Uygulama şifresi
    username = os.getenv("FROM_MAIL")  # Gönderen e-posta adresi

    # E-posta nesnesini oluşturma
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_address
    msg['To'] = to_address

    # İçeriğin HTML olup olmadığını kontrol etme (Java'daki mantıkla aynı)
    is_html = message is not None and (
        message.strip().startswith("<") or 
        "<table" in message or 
        "<html" in message
    )

    if is_html:
        msg.set_content("Lütfen HTML destekleyen bir e-posta istemcisi kullanın.") # Fallback
        msg.add_alternative(message, subtype='html')
    else:
        msg.set_content(message)

    try:
        # SSL ile bağlantı kurma (Java'daki ssl.enable=true karşılığı)
        with smtplib.SMTP_SSL(host, port) as server:
            server.login(username, app_password)
            server.send_message(msg)
            
        print("********************** Mail Sent **********************")
    except Exception as e:
        print(f"E-posta gönderilirken hata oluştu: {e}")     

def passCaptcha(url, current_url, page):
    if "captcha" in current_url.lower():
                print("Captcha metini: Lütfen doğrulama yapın")
                try:
                            # Tüm frame'leri kontrol et
                            frames = page.frames
                            print(f"Toplam {len(frames)} frame bulundu")
                            
                            captcha_frame = None
                            for i, frame in enumerate(frames):
                                print(f"Frame {i}: {frame.name} - {frame.url[:100] if frame.url else 'No URL'}")
                                # CAPTCHA frame'ini bul
                                if "captcha" in frame.url.lower() or "verify" in frame.url.lower():
                                    captcha_frame = frame
                                    break
                            
                            if captcha_frame is None:
                                # Frame locator ile tekrar deneyelim
                                try:
                                    captcha_frame = page.frame_locator('iframe[title*="human"], iframe[title*="verification"], iframe[title*="challenge"]').content_frame
                                except:
                                    captcha_frame = page.frames[-1]  # Son frame'i dene
                            
                            print(f"CAPTCHA frame'i bulundu: {captcha_frame.url}")
                            
                            # 1. Önce sayfayı scroll et
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
                            page.wait_for_timeout(1000)
                            
                            # 2. Butonu bulmak için birden fazla yol dene
                            button = None
                            
                            # Yöntem 1: XPath ile metin arama
                            button_xpath = captcha_frame.locator('//*[contains(text(), "Press") or contains(text(), "press") or contains(text(), "Hold")]')
                            if button_xpath.count() > 0:
                                button = button_xpath.first
                                print(f"Buton XPath ile bulundu: {button}")
                            
                            # Yöntem 2: CSS selector ile
                            if not button:
                                selectors = [
                                    '[aria-label*="Press"]',
                                    'button:has-text("Press")',
                                    'div:has-text("Press")',
                                    'p:has-text("Press")',
                                    'span:has-text("Press")',
                                    '[class*="captcha"]',
                                    '[class*="verify"]',
                                    '[class*="challenge"]'
                                ]
                                
                                for selector in selectors:
                                    elements = captcha_frame.locator(selector)
                                    if elements.count() > 0:
                                        button = elements.first
                                        print(f"Buton selector ile bulundu: {selector}")
                                        break
                            
                            if button:
                                # Butonu görünür hale getir
                                button.scroll_into_view_if_needed()
                                page.wait_for_timeout(2000)
                                
                                # Butonun durumunu kontrol et
                                is_visible = button.is_visible()
                                print(f"Buton görünür mü?: {is_visible}")
                                
                                # Bounding box al
                                box = button.bounding_box()
                                if not box:
                                    # Birkaç kez deneyelim
                                    for _ in range(3):
                                        page.wait_for_timeout(500)
                                        box = button.bounding_box()
                                        if box:
                                            break
                                
                                if box:
                                    print(f"Buton koordinatları: x={box['x']}, y={box['y']}, width={box['width']}, height={box['height']}")
                                    
                                    # 3. İnsan benzeri mouse hareketi
                                    # Önce sayfanın ortasına git
                                    viewport = page.viewport_size
                                    start_x = viewport['width'] // 2
                                    start_y = viewport['height'] // 2
                                    
                                    # Butonun merkezini hesapla
                                    target_x = box['x'] + box['width'] / 2
                                    target_y = box['y'] + box['height'] / 2
                                    
                                    # Mouse'u hareket ettir
                                    page.mouse.move(start_x, start_y)
                                    page.wait_for_timeout(500)
                                    
                                    # Kavisli hareket
                                    steps = 20
                                    for i in range(steps):
                                        t = i / steps
                                        # Bezier eğrisi
                                        cp_x = start_x + (target_x - start_x) * 0.5
                                        cp_y = start_y - 50  # Yukarı doğru kavis
                                        
                                        x = (1-t)**2 * start_x + 2*(1-t)*t * cp_x + t**2 * target_x
                                        y = (1-t)**2 * start_y + 2*(1-t)*t * cp_y + t**2 * target_y
                                        
                                        page.mouse.move(x, y)
                                        page.wait_for_timeout(50)
                                    
                                    # 4. Basılı tutma işlemi
                                    print("Butona tıklanıyor ve 10 saniye basılı tutuluyor...")
                                    page.mouse.down()
                                    
                                    # Basılı tutarken hafif hareketler
                                    hold_time = 12  # saniye
                                    start_time = time.time()
                                    
                                    while time.time() - start_time < hold_time:
                                        # Hafif titreme
                                        offset_x = random.uniform(-2, 2)
                                        offset_y = random.uniform(-2, 2)
                                        page.mouse.move(target_x + offset_x, target_y + offset_y)
                                        
                                        # İlerleme göstergesi
                                        elapsed = time.time() - start_time
                                        if elapsed % 2 < 0.1:  # Her 2 saniyede bir
                                            print(f"  {elapsed:.1f}/{hold_time} saniye...")
                                        
                                        page.wait_for_timeout(100)
                                    
                                    # 5. Bırak
                                    page.mouse.up()
                                    print("CAPTCHA işlemi tamamlandı")
                                    
                                    # 6. Bekle ve kontrol et
                                    page.wait_for_timeout(3000)
                                    
                                    # URL'de hala captcha var mı?
                                    # if "captcha" not in page.url.lower():
                                    #     print("✓ CAPTCHA başarıyla geçildi!")
                                    #     return True
                                    # else:
                                    #     print("⚠ CAPTCHA hala görünüyor, sayfayı yeniliyorum...")
                                    #     page.reload()
                                    #     page.wait_for_timeout(5000)
                                    #     return False
                                        
                                else:
                                    print("Hata: Buton koordinatları alınamadı")
                            else:
                                print("Hata: Buton bulunamadı")
                                
                                # Sayfanın HTML'sini kaydet (debug için)
                                html = page.content()
                                with open("debug_captcha_page.html", "w", encoding="utf-8") as f:
                                    f.write(html)
                                print("Debug: Sayfa kaydedildi (debug_captcha_page.html)")
                                # page.goto(url)  # Sayfayı yenile
                                # page.wait_for_timeout(5000)
                                
                except Exception as e:
                    print(f"CAPTCHA işleminde hata: {str(e)}")
                    import traceback
                    traceback.print_exc()
                page.goto(url)
                page.wait_for_timeout(5000) 
                checkAndCloseModal(page)     



def read_old_email(user_email, app_password, subject_query=''):
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
                links_with_prices = extract_links_with_prices(msg.html)
                
                email_list.append({
                    "subject": msg.subject,
                    "date": msg.date,
                    "links_with_prices": links_with_prices
                })
            return email_list
    except Exception as e:
        print(f"Hata oluştu: {e}")
        return []


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


def read_last_sent_flight_email(user_email, app_password):
    try:
        # Gmail için 'Sent Mail' klasörüne bağlanıyoruz
        with MailBox('imap.gmail.com').login(user_email, app_password, '[Gmail]/Sent Mail') as mailbox:
            
            # Filtreleme Kriterleri:
            # 1. to='gsarikurk@gmail.com' -> Sadece bu adrese gönderilenler
            # 2. subject='Uçuş Detayları' -> Konusu tam olarak bu olan (veya içeren)
            criteria = AND(
                to='gsarikurk@gmail.com', 
                subject='Uçuş Detayları'
            )
            
            # reverse=True: En yeni mailden eskiye doğru sırala
            # limit=1: Sadece en sonuncuyu al
            messages = mailbox.fetch(criteria, limit=1, reverse=True)
            
            email_data = None
            for msg in messages:
                # Daha önce yazdığımız tabloyu parçalayan fonksiyon
                flight_data = parse_flight_table(msg.html)
                
                email_data = {
                    "subject": msg.subject,
                    "date": msg.date,
                    "to": msg.to,
                    "flights": flight_data
                }
                # İlk (ve tek) maili alınca döngüden çıkabiliriz
                break 
            
            if not email_data:
                print("Kriterlere uygun gönderilmiş mail bulunamadı.")
                
            return email_data

    except Exception as e:
        print(f"Hata oluştu: {e}")
        return None
    

def parse_flight_table(html_content):
    """Uçuş tablosundaki her satırı yapılandırılmış veriye dönüştürür"""
    soup = BeautifulSoup(html_content, 'html.parser')
    flights = []
    
    table = soup.find('table')
    if not table:
        return []

    # Başlıkları al (From, To, Depart Date, Airline, Price, Provider, URL)
    headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
    
    # Satırları tara (İlk satır başlık olduğu için geçilebilir ama tr/td yapısı daha güvenli)
    rows = table.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if not cols:
            continue
            
        # Sütun verilerini eşleştir
        flight_info = {}
        for i, col in enumerate(cols):
            header_name = headers[i] if i < len(headers) else f"column_{i}"
            
            if header_name == 'url':
                # Linkin kendisini (href) al
                link_tag = col.find('a', href=True)
                flight_info['url'] = link_tag['href'] if link_tag else None
            else:
                flight_info[header_name] = col.get_text(strip=True)
        
        flights.append(flight_info)
        
    return flights    