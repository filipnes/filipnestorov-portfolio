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

# Try importing alternative XML parsers
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

# Simple Item classes
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

# Simple CSV Pipeline
class CSVPipeline:
    def __init__(self, filename, item_class):
        self.filename = filename
        self.item_class = item_class
        self.data = []
        self.seen_keys = set()
        self.file = None
        self.writer = None

    def open_spider(self, spider):
        print(f"Opening {self.filename} for writing...")
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file, delimiter=";", quoting=csv.QUOTE_ALL)
        headers = list(self.item_class().fields.keys())
        self.writer.writerow(headers)
        self.file.flush()

    def process_item(self, item, spider):
        if isinstance(item, self.item_class):
            # For specifications, use combination of providerKey + SpecificationKey as unique key
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
                print(f"Saved item with key: {key}")
        return item

    def close_spider(self, spider):
        if self.file:
            self.file.close()
        print(f"Closed {self.filename}. Total saved items: {len(self.data)}")

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
        """Set up requests session with appropriate headers"""
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
        """Initialize Chrome driver with stealth settings"""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
            self.driver.set_page_load_timeout(30)
            
            # Execute stealth script to hide automation
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("Chrome driver successfully initialized")
        except Exception as e:
            print(f"Error setting up Selenium: {e}")
            raise

    def get_sitemap_content_with_selenium(self, sitemap_url):
        """Use Selenium to get sitemap content"""
        try:
            print(f"Fetching {sitemap_url} with Selenium...")
            self.driver.get(sitemap_url)
            time.sleep(3)
            
            # Get page source
            page_source = self.driver.page_source
            
            # Check if XML content was received
            if '<urlset' in page_source or '<loc>' in page_source or '<?xml' in page_source:
                print("Successfully fetched XML content with Selenium")
                return page_source
            else:
                print("No valid XML content found")
                return None
                
        except Exception as e:
            print(f"Selenium fetch failed: {e}")
            return None

    def parse_urls_from_xml_multiple_methods(self, xml_content):
        """Try multiple XML parsing methods to extract URLs"""
        urls = []
        
        if not xml_content:
            return urls

        # Method 1: BeautifulSoup (most robust)
        if HAS_BS4:
            try:
                print("Trying BeautifulSoup XML parser...")
                soup = BeautifulSoup(xml_content, 'xml')
                loc_tags = soup.find_all('loc')
                for loc in loc_tags:
                    url = loc.get_text().strip()
                    if url and 'tehnomanija.rs' in url:
                        urls.append(url)
                if urls:
                    print(f"BeautifulSoup found {len(urls)} URLs")
                    return urls
            except Exception as e:
                print(f"BeautifulSoup failed: {e}")

        # Method 2: lxml parser
        if HAS_LXML:
            try:
                print("Trying lxml parser...")
                root = lxml_ET.fromstring(xml_content.encode('utf-8'))
                
                # Try with namespace
                namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                loc_elements = root.xpath('.//ns:loc', namespaces=namespace)
                if not loc_elements:
                    # Try without namespace
                    loc_elements = root.xpath('.//loc')
                
                for loc in loc_elements:
                    url = loc.text.strip() if loc.text else ''
                    if url and 'tehnomanija.rs' in url:
                        urls.append(url)
                
                if urls:
                    print(f"lxml found {len(urls)} URLs")
                    return urls
            except Exception as e:
                print(f"lxml failed: {e}")

        # Method 3: Standard ElementTree with namespace handling
        try:
            print("Trying ElementTree with namespace...")
            root = ET.fromstring(xml_content)
            
            # Get namespace from root tag
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
                print(f"ElementTree found {len(urls)} URLs")
                return urls
        except Exception as e:
            print(f"ElementTree with namespace failed: {e}")

        # Method 4: Simple regex fallback
        try:
            print("Trying regex extraction...")
            import re
            loc_pattern = r'<loc>(.*?)</loc>'
            matches = re.findall(loc_pattern, xml_content, re.DOTALL)
            for match in matches:
                url = match.strip()
                if url and 'tehnomanija.rs' in url:
                    urls.append(url)
            if urls:
                print(f"Regex found {len(urls)} URLs")
                return urls
        except Exception as e:
            print(f"Regex extraction failed: {e}")

        return urls

    def get_all_product_urls(self, limit=None):
        """Get all product URLs from XML sitemaps using multiple methods"""
        all_product_urls = []
        
        # Known sitemap URLs
        sitemap_urls = [
            "https://www.tehnomanija.rs/products_1.xml",
            "https://www.tehnomanija.rs/products_2.xml",
            "https://www.tehnomanija.rs/products_3.xml"
        ]
        
        for sitemap_url in sitemap_urls:
            if limit and len(all_product_urls) >= limit:
                break
                
            print(f"\n=== Processing {sitemap_url} ===")
            
            # Try to get XML content using Selenium
            xml_content = None
            xml_content = self.get_sitemap_content_with_selenium(sitemap_url)
            
            # Parse URLs from XML content
            if xml_content:
                urls = self.parse_urls_from_xml_multiple_methods(xml_content)
                
                # Add ALL URLs without aggressive filtering
                for url in urls:
                    if limit and len(all_product_urls) >= limit:
                        break
                    # Only check that URL is not already in list
                    if url not in all_product_urls:
                        all_product_urls.append(url)
                
                print(f"Added {len([u for u in urls if u not in all_product_urls[:len(all_product_urls)-len(urls)]])} new URLs from this sitemap")
            else:
                print("Failed to get XML content")
            
            # Decent delay
            time.sleep(random.uniform(2, 4))

        # Print first few URLs for verification
        print(f"\nFirst 10 collected URLs:")
        for i, url in enumerate(all_product_urls[:10]):
            print(f"  {i+1}: {url}")
            
        print(f"\nTotal collected product URLs: {len(all_product_urls)}")
        return all_product_urls

    def check_connection(self):
        try:
            # Try multiple endpoints
            endpoints = [
                "https://www.tehnomanija.rs",
                "https://google.com",
                "https://www.cloudflare.com"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code in [200, 301, 302]:
                        print(f"Connection OK via {endpoint}")
                        return True
                except:
                    continue
            
            print("All connection tests failed")
            return False
        except:
            return False

    def ensure_driver_active(self):
        try:
            self.driver.current_url
            return True
        except Exception:
            print("Driver seems inactive, reinitializing...")
            self.init_driver()
            return False

    def safe_find_element(self, selector, attribute=None):
        """Safely find element and return text or attribute"""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            if attribute:
                return element.get_attribute(attribute)
            else:
                return element.text.strip()
        except NoSuchElementException:
            return None

    def extract_product_details(self, product_url):
        # Enhanced connection check
        max_connection_retries = 3
        for conn_attempt in range(max_connection_retries):
            if self.check_connection():
                break
            else:
                print(f"Connection attempt {conn_attempt + 1} failed, waiting 10 seconds...")
                time.sleep(6)
        else:
            print("No internet connection after multiple attempts, skipping...")
            return False

        print(f"Processing: {product_url}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.driver.get(product_url)
                
                # Wait for page to load
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Additional wait for dynamic content
                time.sleep(2)
                
                product = ProductItem()
                gtin = None
                
                # Extract GTIN
                gtin = self.safe_find_element('div.loadbeeTabContent', 'data-loadbee-gtin')
                if not gtin:
                    # Fallback: extract from URL
                    gtin = product_url.split('/')[-1].split('-')[-1]
                    print(f"Using GTIN from URL: {gtin}")
                else:
                    print(f"Found GTIN: {gtin}")
                
                product['providerkey'] = gtin
                product['gtin'] = gtin
                
                # Extract product type from URL
                try:
                    url_parts = product_url.replace('https://www.tehnomanija.rs/', '').split('/')
                    product_type = '/'.join(url_parts[:-1])
                    product['productType'] = product_type
                    print(f"Product type: {product_type}")
                except:
                    pass
                
                # Extract title
                title = self.safe_find_element('h1.page-title span')
                if not title:
                    title = self.safe_find_element('h1.page-title')
                if title:
                    product['title'] = title
                    print(f"Title: {title[:50]}...")
                
                # Extract brand from scripts
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
                    print(f"Error extracting brand: {e}")
                
                # PRICE FIX - new selector
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, 'span[data-price-type="finalPrice"] > span')
                    if price_elements:
                        # Take first element
                        price_text = price_elements[0].text.strip()
                        # Remove 'RSD' from string
                        price = price_text.replace('RSD', '').strip()
                        product['price'] = price
                        print(f"Price: {price}")
                    else:
                        # Fallback to old selector
                        price = self.safe_find_element('meta[property="product:price:amount"]', 'content')
                        if price:
                            product['price'] = price
                            print(f"Price (fallback): {price}")
                except Exception as e:
                    print(f"Error extracting price: {e}")
                
                # DESCRIPTION FIX - existing selector is already good
                description = self.safe_find_element('meta[property="og:description"]', 'content')
                if description:
                    product['longdescription'] = description
                    print(f"Description: {description[:100]}...")
                
                # Save product
                self.product_pipeline.process_item(product, self)
                
                # Extract specifications
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '#product-attribute-specs-table'))
                    )
                    
                    spec_rows = self.driver.find_elements(By.CSS_SELECTOR, '#product-attribute-specs-table tbody tr td ul li')
                    print(f"Found {len(spec_rows)} specification rows")
                    
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
                    print(f"No specifications found: {e}")
                
                # Extract images - FIXED SELECTOR
                try:
                    time.sleep(1)  # Wait for images to load
                    
                    # New selector for href attributes from fotorama frames
                    frame_elements = self.driver.find_elements(By.CSS_SELECTOR, '.fotorama__stage__frame[href]')
                    print(f"Found {len(frame_elements)} images")
                    
                    if frame_elements:
                        media_item = MediaItem()
                        media_item['providerKey'] = gtin
                        media_item['gtin'] = gtin
                        
                        image_count = 0
                        for i, frame_element in enumerate(frame_elements[:10], start=1):
                            try:
                                # Get href attribute containing image URL
                                image_url = frame_element.get_attribute('href')
                                if image_url and 'data:' not in image_url:  # Skip base64 images
                                    media_item[f'imageurl_{i}'] = image_url.strip()
                                    image_count += 1
                                    print(f'  Image {i}: {image_url[:60]}...')
                            except Exception as e:
                                continue
                        
                        if image_count > 0:
                            self.media_pipeline.process_item(media_item, self)
                            print(f"Saved {image_count} images")
                            
                except Exception as e:
                    print(f"Error extracting images: {e}")
                
                print("✓ Product successfully processed")
                return True
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print("Retrying...")
                    self.init_driver()
                    time.sleep(5)
                else:
                    print("Maximum attempts exceeded")
                    return False

    def run(self):
        try:
            # Get product URLs from XML sitemaps
            product_urls = self.get_all_product_urls(limit=50)  # Increased limit for testing
            print(f"Total products to process: {len(product_urls)}")
            
            if not product_urls:
                print("No URLs found. Exiting.")
                return
            
            successful_count = 0
            failed_count = 0
            
            for i, url in enumerate(product_urls):
                try:
                    print(f"\n--- Product {i+1}/{len(product_urls)} ---")
                    
                    if not self.ensure_driver_active():
                        print("Driver reinitialized")
                    
                    success = self.extract_product_details(url)
                    
                    if success:
                        successful_count += 1
                    else:
                        failed_count += 1
                    
                    # Progress report every 10 items
                    if (i + 1) % 10 == 0:
                        total_processed = successful_count + failed_count
                        success_rate = (successful_count / total_processed) * 100 if total_processed > 0 else 0
                        print(f"\n=== Progress Report ===")
                        print(f"Processed: {i+1}/{len(product_urls)}")
                        print(f"Successful: {successful_count}")
                        print(f"Failed: {failed_count}")
                        print(f"Success rate: {success_rate:.1f}%")
                    
                    # Delay between products
                    time.sleep(random.uniform(2, 4))
                    
                except KeyboardInterrupt:
                    print("\nInterrupted by user")
                    break
                except Exception as e:
                    failed_count += 1
                    print(f"Error processing URL {url}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error during execution: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        print("\nCleaning up...")
        try:
            self.product_pipeline.close_spider(self)
            self.spec_pipeline.close_spider(self)
            self.media_pipeline.close_spider(self)
        except Exception as e:
            print(f"Error closing pipelines: {e}")
            
        try:
            if self.driver:
                self.driver.quit()
                print("Driver successfully closed")
        except Exception as e:
            print(f"Error closing driver: {e}")

if __name__ == "__main__":
    print("Starting Tehnomanija XML Sitemap Spider...")
    print("Using multiple XML parsing methods for maximum compatibility")
    print("=" * 60)
    
    try:
        scraper = TehnomanijaSeleniumSpider()
        scraper.run()
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        print("Script finished.")
