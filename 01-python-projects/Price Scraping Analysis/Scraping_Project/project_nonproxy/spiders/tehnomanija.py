import sys
import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
import random
from webdriver_manager.chrome import ChromeDriverManager
import csv
from collections import OrderedDict
from urllib.parse import urljoin, urlparse
import re
# Pokušaj import alternativnih XML parser-a
try:
    from lxml import etree as lxml_ET
    HAS_LXML = True
except ImportError:
    HAS_LXML = False
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# Jednostavne Item klase
class ProductItem(dict):
    def __init__(self):
        super().__init__()
        self.fields = OrderedDict([
            ('providerkey', ''),
            ('gtin', ''),
            ('manufacturerkey', ''),
            ('brand', ''),
            ('productType', ''),
            ('title', ''),
            ('countryoforigin', ''),
            ('longdescription', ''),
            ('price', ''),
        ])
        for field in self.fields:
            self[field] = ""
class SpecItem(dict):
    def __init__(self):
        super().__init__()
        self.fields = OrderedDict([
            ('providerKey', ''),
            ('SpecificationKey', ''),
            ('SpecificationValue', ''),
        ])
        for field in self.fields:
            self[field] = ""
class MediaItem(dict):
    def __init__(self):
        super().__init__()
        self.fields = OrderedDict([
            ('providerKey', ''),
            ('gtin', ''),
            ('datasheeturl_1', ''),
            ('datasheeturl_2', ''),
            ('datasheeturl_3', ''),
            ('safetydatasheet', ''),
            ('energylabel', ''),
            ('imageurl_1', ''),
            ('imageurl_2', ''),
            ('imageurl_3', ''),
            ('imageurl_4', ''),
            ('imageurl_5', ''),
            ('imageurl_6', ''),
            ('imageurl_7', ''),
            ('imageurl_8', ''),
            ('imageurl_9', ''),
            ('imageurl_10', ''),
        ])
        for field in self.fields:
            self[field] = ""

# Jednostavan CSV Pipeline
class CSVPipeline:
    def __init__(self, filename, item_class):
        self.filename = filename
        self.item_class = item_class
        self.data = []
        self.seen_keys = set()
        self.file = None
        self.writer = None
        
    def open_spider(self, spider):
        print(f"Otvaram {self.filename} za upis...")
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file, delimiter=";", quoting=csv.QUOTE_ALL)
        headers = list(self.item_class().fields.keys())
        self.writer.writerow(headers)
        self.file.flush()
        
    def process_item(self, item, spider):
        if isinstance(item, self.item_class):
            # Za specifikacije, koristimo kombinaciju providerKey + SpecificationKey kao jedinstveni ključ
            if isinstance(item, SpecItem):
                key = f"{item.get('providerKey', '')}_{item.get('SpecificationKey', '')}"
            else:
                key = item.get('providerKey') or item.get('providerkey')
                
            if key and key not in self.seen_keys:
                self.seen_keys.add(key)
                row = [item.get(field, "") for field in item.fields.keys()]
                self.writer.writerow(row)
                self.file.flush()
                self.data.append(row)
                print(f"Sačuvan item sa ključem: {key}")
        return item
        
    def close_spider(self, spider):
        if self.file:
            self.file.close()
        print(f"Zatvoren {self.filename}. Ukupno sačuvanih stavki: {len(self.data)}")

class TehnomanijaSeleniumSpider:
    name = "tehnomanija"
    
    def __init__(self):
        self.driver = None
        self.session = None
        self.setup_chrome_options()
        self.setup_session()
        self.init_driver()
        self.setup_pipelines()
    def setup_chrome_options(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--headless=new')
        self.chrome_options.add_argument('--disable-software-rasterizer')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-plugins')
        self.chrome_options.add_argument('--disable-javascript')
        self.chrome_options.add_argument('--disable-images')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.chrome_options.add_argument('--disable-blink-features')
        
    def setup_session(self):
        """Podesi requests session sa odgovarajućim header-ima"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/xml,text/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8',
            'Accept-Language': 'sr-RS,sr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    def setup_pipelines(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.product_pipeline = CSVPipeline(f'{self.name}_master.csv', ProductItem)
        self.spec_pipeline = CSVPipeline(f'{self.name}_spec.csv', SpecItem)
        self.media_pipeline = CSVPipeline(f'{self.name}_media.csv', MediaItem)
        
        self.product_pipeline.open_spider(self)
        self.spec_pipeline.open_spider(self)
        self.media_pipeline.open_spider(self)
    def init_driver(self):
        """Inicijalizuj Chrome driver sa stealth podešavanjima"""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
            self.driver.set_page_load_timeout(30)
            
            # Izvrši stealth script za sakrivanje automatizacije
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("Chrome driver uspešno inicijalizovan")
            
        except Exception as e:
            print(f"Greška pri podešavanju Selenium-a: {e}")
            raise
    def get_sitemap_content_with_selenium(self, sitemap_url):
        """Koristi Selenium za dobijanje sadržaja sitemap-a"""
        try:
            print(f"Uzimam {sitemap_url} sa Selenium-om...")
            self.driver.get(sitemap_url)
            time.sleep(3)
            
            # Uzmi page source
            page_source = self.driver.page_source
            
            # Proveri da li je dobijen XML sadržaj
            if '<urlset' in page_source or '<loc>' in page_source or '<?xml' in page_source:
                print("Uspešno dohvaćen XML sadržaj sa Selenium-om")
                return page_source
            else:
                print("Nije pronađen valjan XML sadržaj")
                return None
                
        except Exception as e:
            print(f"Selenium dohvatanje neuspešno: {e}")
            return None
    def parse_urls_from_xml_multiple_methods(self, xml_content):
        """Pokušaj više metoda XML parsiranja za izvlačenje URL-ova"""
        urls = []
        
        if not xml_content:
            return urls
        
        # Metoda 1: BeautifulSoup (najrobustnija)
        if HAS_BS4:
            try:
                print("Pokušavam BeautifulSoup XML parser...")
                soup = BeautifulSoup(xml_content, 'xml')
                loc_tags = soup.find_all('loc')
                for loc in loc_tags:
                    url = loc.get_text().strip()
                    if url and 'tehnomanija.rs' in url:
                        urls.append(url)
                
                if urls:
                    print(f"BeautifulSoup našao {len(urls)} URL-ova")
                    return urls
            except Exception as e:
                print(f"BeautifulSoup neuspešan: {e}")
        
        # Metoda 2: lxml parser
        if HAS_LXML:
            try:
                print("Pokušavam lxml parser...")
                root = lxml_ET.fromstring(xml_content.encode('utf-8'))
                
                # Pokušaj sa namespace
                namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                loc_elements = root.xpath('.//ns:loc', namespaces=namespace)
                
                if not loc_elements:
                    # Pokušaj bez namespace
                    loc_elements = root.xpath('.//loc')
                
                for loc in loc_elements:
                    url = loc.text.strip() if loc.text else ''
                    if url and 'tehnomanija.rs' in url:
                        urls.append(url)
                
                if urls:
                    print(f"lxml našao {len(urls)} URL-ova")
                    return urls
            except Exception as e:
                print(f"lxml neuspešan: {e}")
        
        # Metoda 3: Standardni ElementTree sa namespace handling
        try:
            print("Pokušavam ElementTree sa namespace...")
            root = ET.fromstring(xml_content)
            
            # Uzmi namespace iz root tag-a
            if '}' in root.tag:
                namespace = root.tag.split('}')[0] + '}'
                loc_elements = root.findall('.//' + namespace + 'loc')
            else:
                loc_elements = root.findall('.//loc')
            
            for loc in loc_elements:
                url = loc.text.strip() if loc.text else ''
                if url and 'tehnomanija.rs' in url:
                    urls.append(url)
            
            if urls:
                print(f"ElementTree našao {len(urls)} URL-ova")
                return urls
        except Exception as e:
            print(f"ElementTree sa namespace neuspešan: {e}")
        
        # Metoda 4: Jednostavan regex fallback
        try:
            print("Pokušavam regex ekstraktovanje...")
            import re
            loc_pattern = r'<loc>(.*?)</loc>'
            matches = re.findall(loc_pattern, xml_content, re.DOTALL)
            
            for match in matches:
                url = match.strip()
                if url and 'tehnomanija.rs' in url:
                    urls.append(url)
            
            if urls:
                print(f"Regex našao {len(urls)} URL-ova")
                return urls
        except Exception as e:
            print(f"Regex ekstraktovanje neuspešno: {e}")
        
        return urls
    def get_all_product_urls(self, limit=None):
        """Uzmi sve product URL-ove iz XML sitemap-ova koristeći više metoda"""
        all_product_urls = []
        
        # Poznati sitemap URL-ovi
        sitemap_urls = [
            "https://www.tehnomanija.rs/products_1.xml",
            "https://www.tehnomanija.rs/products_2.xml", 
            "https://www.tehnomanija.rs/products_3.xml"
        ]
        
        for sitemap_url in sitemap_urls:
            if limit and len(all_product_urls) >= limit:
                break
                
            print(f"\n=== Obrađujem {sitemap_url} ===")
            
            # Pokušaj da dobijes XML sadržaj koristeći Selenium
            xml_content = None
            xml_content = self.get_sitemap_content_with_selenium(sitemap_url)
            
            # Parsiraj URL-ove iz XML sadržaja
            if xml_content:
                urls = self.parse_urls_from_xml_multiple_methods(xml_content)
                
                # Dodaj SVE URL-ove bez agresivnog filtriranja
                for url in urls:
                    if limit and len(all_product_urls) >= limit:
                        break
                    
                    # Proveri samo da URL nije već u listi
                    if url not in all_product_urls:
                        all_product_urls.append(url)
                
                print(f"Dodao {len([u for u in urls if u not in all_product_urls[:len(all_product_urls)-len(urls)]])} novih URL-ova iz ovog sitemap-a")
            else:
                print("Neuspešno dobijanje XML sadržaja")
            
            # Pristojni delay
            time.sleep(random.uniform(2, 4))
        
        # Ispiši prvih nekoliko URL-ova za verifikaciju
        print(f"\nPrvih 10 sakupljenih URL-ova:")
        for i, url in enumerate(all_product_urls[:10]):
            print(f"  {i+1}: {url}")
        
        print(f"\nUkupno sakupljenih product URL-ova: {len(all_product_urls)}")
        return all_product_urls
    def check_connection(self):
        try:
            # Pokušaj više endpoint-ova
            endpoints = [
                "https://www.tehnomanija.rs",
                "https://google.com", 
                "https://www.cloudflare.com"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code in [200, 301, 302]:
                        print(f"Konekcija OK preko {endpoint}")
                        return True
                except:
                    continue
            
            print("Svi testovi konekcije neuspešni")
            return False
        except:
            return False
    def ensure_driver_active(self):
        try:
            self.driver.current_url
            return True
        except Exception:
            print("Driver izgleda neaktivan, reinicijalizujem...")
            self.init_driver()
            return False
    def safe_find_element(self, selector, attribute=None):
        """Bezbedno pronađi element i vrati tekst ili atribut"""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            if attribute:
                return element.get_attribute(attribute)
            else:
                return element.text.strip()
        except NoSuchElementException:
            return None
    def extract_product_details(self, product_url):
        # Poboljšana provera konekcije
        max_connection_retries = 3
        for conn_attempt in range(max_connection_retries):
            if self.check_connection():
                break
            else:
                print(f"Pokušaj konekcije {conn_attempt + 1} neuspešan, čekam 10 sekundi...")
                time.sleep(6)
        else:
            print("Nema internet konekcije nakon više pokušaja, preskačem...")
            return False
        print(f"Obrađujem: {product_url}")
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                self.driver.get(product_url)
                
                # Sačekaj da se stranica učita
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Dodatno čekanje za dinamički sadržaj
                time.sleep(2)
                
                product = ProductItem()
                gtin = None
                
                # Izvuci GTIN
                gtin = self.safe_find_element('div.loadbeeTabContent', 'data-loadbee-gtin')
                if not gtin:
                    # Fallback: izvuci iz URL-a
                    gtin = product_url.split('/')[-1].split('-')[-1]
                    print(f"Koristim GTIN iz URL-a: {gtin}")
                else:
                    print(f"Pronašao GTIN: {gtin}")
                
                product['providerkey'] = gtin
                product['gtin'] = gtin
                # Izvuci tip proizvoda iz URL-a
                try:
                    url_parts = product_url.replace('https://www.tehnomanija.rs/', '').split('/')
                    product_type = '/'.join(url_parts[:-1])
                    product['productType'] = product_type
                    print(f"Tip proizvoda: {product_type}")
                except:
                    pass
                # Izvuci naslov
                title = self.safe_find_element('h1.page-title span')
                if not title:
                    title = self.safe_find_element('h1.page-title')
                if title:
                    product['title'] = title
                    print(f"Naslov: {title[:50]}...")
                # Izvuci brand iz script-ova
                try:
                    scripts = self.driver.find_elements(By.TAG_NAME, 'script')
                    for script in scripts:
                        script_content = script.get_attribute('innerHTML') or ""
                        if '"brand":"' in script_content:
                            brand_start = script_content.find('"brand":"') + len('"brand":"')
                            brand_end = script_content.find('"', brand_start)
                            if brand_end > brand_start:
                                brand = script_content[brand_start:brand_end]
                                product['brand'] = brand
                                print(f"Brand: {brand}")
                                break
                except Exception as e:
                    print(f"Greška pri izvlačenju brand-a: {e}")
                
                # ISPRAVKA ZA CENU - novi selektor
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, 'span[data-price-type="finalPrice"] > span')
                    if price_elements:
                        # Uzmi prvi element
                        price_text = price_elements[0].text.strip()
                        # Ukloni 'RSD' iz stringa
                        price = price_text.replace('RSD', '').strip()
                        product['price'] = price
                        print(f"Cena: {price}")
                    else:
                        # Fallback na stari selektor
                        price = self.safe_find_element('meta[property="product:price:amount"]', 'content')
                        if price:
                            product['price'] = price
                            print(f"Cena (fallback): {price}")
                except Exception as e:
                    print(f"Greška pri izvlačenju cene: {e}")
                
                # ISPRAVKA ZA OPIS - postojeći selektor je već dobar
                description = self.safe_find_element('meta[property="og:description"]', 'content')
                if description:
                    product['longdescription'] = description
                    print(f"Opis: {description[:100]}...")
                
                # Sačuvaj proizvod
                self.product_pipeline.process_item(product, self)
                # Izvuci specifikacije
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '#product-attribute-specs-table'))
                    )
                    
                    spec_rows = self.driver.find_elements(By.CSS_SELECTOR, '#product-attribute-specs-table tbody tr td ul li')
                    print(f"Pronašao {len(spec_rows)} redova specifikacija")
                    
                    for spec_row in spec_rows:
                        try:
                            spans = spec_row.find_elements(By.TAG_NAME, 'span')
                            if len(spans) >= 2:
                                key = spans[0].text.strip()
                                value = spans[-1].text.strip()
                                
                                if key and value and key != value:
                                    spec_item = SpecItem()
                                    spec_item['providerKey'] = gtin
                                    spec_item['SpecificationKey'] = key
                                    spec_item['SpecificationValue'] = value
                                    self.spec_pipeline.process_item(spec_item, self)
                                    print(f'  Spec: {key} = {value}')
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    print(f"Nisu pronađene specifikacije: {e}")
                # Izvuci slike - ISPRAVLJEN SELEKTOR
                try:
                    time.sleep(1)  # Sačekaj da se slike učitaju
                    
                    # Novi selektor za href atribute iz fotorama frame-ova
                    frame_elements = self.driver.find_elements(By.CSS_SELECTOR, '.fotorama__stage__frame[href]')
                    print(f"Pronašao {len(frame_elements)} slika")
                    
                    if frame_elements:
                        media_item = MediaItem()
                        media_item['providerKey'] = gtin
                        media_item['gtin'] = gtin
                        
                        image_count = 0
                        for i, frame_element in enumerate(frame_elements[:10], start=1):
                            try:
                                # Uzmi href atribut koji sadrži URL slike
                                image_url = frame_element.get_attribute('href')
                                if image_url and 'data:' not in image_url:  # Preskoči base64 slike
                                    media_item[f'imageurl_{i}'] = image_url.strip()
                                    image_count += 1
                                    print(f'  Slika {i}: {image_url[:60]}...')
                            except Exception as e:
                                continue
                        
                        if image_count > 0:
                            self.media_pipeline.process_item(media_item, self)
                            print(f"Sačuvao {image_count} slika")
                            
                except Exception as e:
                    print(f"Greška pri izvlačenju slika: {e}")
                print("✓ Proizvod uspešno obrađen")
                return True
                
            except Exception as e:
                print(f"Pokušaj {attempt + 1} neuspešan: {e}")
                if attempt < max_retries - 1:
                    print("Ponovo pokušavam...")
                    self.init_driver()
                    time.sleep(5)
                else:
                    print("Maksimalno pokušaja prekoračeno")
                    return False
    def run(self):
        try:
            # Uzmi product URL-ove iz XML sitemap-ova
            product_urls = self.get_all_product_urls(limit=50)  # Povećan limit za testiranje
            print(f"Ukupno proizvoda za obradu: {len(product_urls)}")
            
            if not product_urls:
                print("Nije pronađen nijedan URL. Izlazim.")
                return
            
            successful_count = 0
            failed_count = 0
            
            for i, url in enumerate(product_urls):
                try:
                    print(f"\n--- Proizvod {i+1}/{len(product_urls)} ---")
                    
                    if not self.ensure_driver_active():
                        print("Driver reinicijalizovan")
                    
                    success = self.extract_product_details(url)
                    if success:
                        successful_count += 1
                    else:
                        failed_count += 1
                    
                    # Izveštaj o napretku svakih 10 stavki
                    if (i + 1) % 10 == 0:
                        total_processed = successful_count + failed_count
                        success_rate = (successful_count / total_processed) * 100 if total_processed > 0 else 0
                        print(f"\n=== Izveštaj o napretku ===")
                        print(f"Obrađeno: {i+1}/{len(product_urls)}")
                        print(f"Uspešno: {successful_count}")
                        print(f"Neuspešno: {failed_count}")
                        print(f"Stopa uspeha: {success_rate:.1f}%")
                    
                    # Delay između proizvoda
                    time.sleep(random.uniform(2, 4))
                
                except KeyboardInterrupt:
                    print("\nPrekinuto od strane korisnika")
                    break
                except Exception as e:
                    failed_count += 1
                    print(f"Greška pri obradi URL-a {url}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Greška tokom izvršavanja: {e}")
        finally:
            self.cleanup()
    def cleanup(self):
        print("\nČistim...")
        try:
            self.product_pipeline.close_spider(self)
            self.spec_pipeline.close_spider(self)
            self.media_pipeline.close_spider(self)
        except Exception as e:
            print(f"Greška pri zatvaranju pipeline-a: {e}")
        
        try:
            if self.driver:
                self.driver.quit()
                print("Driver uspešno zatvoren")
        except Exception as e:
            print(f"Greška pri zatvaranju driver-a: {e}")
if __name__ == "__main__":
    print("Pokrećem Tehnomanija XML Sitemap Spider...")
    print("Koristim više metoda XML parsiranja za maksimalnu kompatibilnost")
    print("=" * 60)
    
    try:
        scraper = TehnomanijaSeleniumSpider()
        scraper.run()
    except KeyboardInterrupt:
        print("\nScript prekinut od strane korisnika")
    except Exception as e:
        print(f"Fatalna greška: {e}")
    finally:
        print("Skripta završena.")