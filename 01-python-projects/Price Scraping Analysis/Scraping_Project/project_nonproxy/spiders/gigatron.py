import scrapy
import json
import re
from urllib.parse import unquote, urlparse, parse_qs
from scrapy.spiders import SitemapSpider
from project_nonproxy.items import ProductItem, SpecItem, MediaItem

class GigatronSpider(SitemapSpider):
    name = 'gigatron'
    
    sitemap_urls = [
        'https://gigatron.rs/sitemap/samsung.xml', 
        'https://gigatron.rs/sitemap/proizvodi.xml'
    ]
    
    sitemap_rules = [
        (r'/proizvod/', 'parse')  # just products
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 3,
        'ROBOTSTXT_OBEY': False,
    }

    def parse(self, response):
        self.logger.info(f"Parsiranje URL-a: {response.url}")
        
        # Izdvajanje GTIN-a i drugih podataka iz JSON-LD skripte
        gtin = None
        json_ld_data = None
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script)
                if data.get('@type') == 'Product':
                    json_ld_data = data
                    gtin = json_ld_data.get('sku', '').strip()
                    break
            except json.JSONDecodeError:
                continue
        
        if not gtin:
            self.logger.error(f"GTIN nije pronađen za {response.url}")
            return
        
        # Kreiranje ProductItem objekta
        product = ProductItem()
        
        # Prethodno izdvajanje specifikacija da dobijemo brend i druge podatke
        specs_data = {}
        spec_rows = response.css('table tbody tr')
        brand_from_specs = None
        
        for row in spec_rows:
            cells = row.css('td')
            if len(cells) >= 2:
                key_cell = cells[0]
                value_cell = cells[1]
                
                # Preskačemo zaglavlja (colspan=2)
                if key_cell.css('[colspan]'):
                    continue
                
                key = key_cell.css('::text').get()
                value = value_cell.css('span::text').get()
                
                if key and value:
                    key_clean = key.strip()
                    value_clean = value.strip()
                    specs_data[key_clean] = value_clean
                    
                    # Provera za brend
                    if key_clean == 'Brend':
                        brand_from_specs = value_clean
        
        product['providerkey'] = gtin
        product['gtin'] = gtin
        
        # Izdvajanje osnovnih informacija o proizvodu iz JSON-LD
        title = ""
        if json_ld_data:
            title = json_ld_data.get('name', '').strip()
            product['title'] = title
            
            # Izdvajanje cene iz JSON-LD offers sekcije
            offers = json_ld_data.get('offers', {})
            if offers and offers.get('price'):
                product['price'] = offers['price']
            
            # Izdvajanje putanje kategorije iz JSON-LD
            category_data = json_ld_data.get('category', {})
            if category_data and category_data.get('itemListElement'):
                category_items = category_data['itemListElement']
                # Uzimamo nazive kategorija, preskačemo prvu ako je previše generička
                category_names = [item.get('name', '') for item in category_items if item.get('name')]
                if len(category_names) > 1:
                    # Koristimo poslednje kategorije za specifičniju klasifikaciju
                    product['productType'] = ' > '.join(category_names[-3:])
                elif category_names:
                    product['productType'] = category_names[-1]
        
        # Izdvajanje brenda - prioritet: specifikacije > prva reč iz naslova
        if brand_from_specs:
            product['brand'] = brand_from_specs
        elif title:
            # Uzimamo prvu reč iz naslova kao rezervni brend
            first_word = title.split()[0] if title.split() else ""
            if first_word:
                product['brand'] = first_word
        
        # Izdvajanje opisa koristeći XPath
        description_parts = []
        
        # Metoda 1: Pokušavamo da pronađemo aktivni tab panel sa opisom
        description_xpath = '//div[@role="tabpanel"][@data-headlessui-state="selected"]//text()[normalize-space()]'
        description_texts = response.xpath(description_xpath).getall()
        
        if description_texts:
            # Čišćenje i spajanje svih delova teksta
            for text in description_texts:
                cleaned_text = text.strip()
                if cleaned_text and len(cleaned_text) > 3:  # Preskačemo veoma kratke tekstove
                    description_parts.append(cleaned_text)
        
        # Metoda 2: Rezervna opcija - tražimo opis u bilo kom tab panel-u sa sadržajem
        if not description_parts:
            fallback_xpath = '//div[@role="tabpanel"]//li/text()[normalize-space()]'
            fallback_texts = response.xpath(fallback_xpath).getall()
            
            for text in fallback_texts:
                cleaned_text = text.strip()
                if cleaned_text and len(cleaned_text) > 10:  # Preskačemo veoma kratke tekstove
                    description_parts.append(cleaned_text)
        
        # Metoda 3: CSS selektor kao poslednja opcija
        if not description_parts:
            css_description = response.css('div[role="tabpanel"][data-headlessui-state="selected"] li::text').getall()
            description_parts = [text.strip() for text in css_description if text.strip()]
        
        if description_parts:
            # Spajamo sve delove opisa sa razmakom
            full_description = ' '.join(description_parts)
            # Čišćenje višestrukih razmaka
            full_description = re.sub(r'\s+', ' ', full_description).strip()
            if full_description:
                product['longdescription'] = full_description
        
        # Izdvajanje koda proizvođača (model) iz specifikacija
        model = specs_data.get('Model')
        if model:
            product['manufacturerkey'] = model
        
        # Izdvajanje zemlje porekla iz specifikacija
        country = specs_data.get('Zemlja porekla')
        if country:
            product['countryoforigin'] = country
        
        yield product
        
        # Izdvajanje specifikacija i kreiranje SpecItems objekata
        for key, value in specs_data.items():
            spec_item = SpecItem()
            spec_item['providerKey'] = gtin
            spec_item['SpecificationKey'] = key
            spec_item['SpecificationValue'] = value
            yield spec_item
        
        # Izdvajanje slika
        image_urls = []
        
        # Metoda 1: Izdvajanje iz img src atributa
        img_elements = response.css('button[aria-label*="Slika proizvoda"] img')
        for img in img_elements:
            src = img.css('::attr(src)').get()
            if src:
                # Izdvajanje stvarnog URL-a slike iz Next.js image URL-a
                if '/_next/image?url=' in src:
                    try:
                        parsed_url = urlparse(src)
                        query_params = parse_qs(parsed_url.query)
                        if 'url' in query_params:
                            actual_url = unquote(query_params['url'][0])
                            image_urls.append(actual_url)
                    except Exception as e:
                        self.logger.warning(f"Neuspešno parsiranje URL-a slike {src}: {e}")
                else:
                    image_urls.append(src)
        
        # Metoda 2: Izdvajanje iz srcSet atributa (rezervna opcija)
        if not image_urls:
            for img in img_elements:
                srcset = img.css('::attr(srcSet)').get()
                if srcset:
                    # Izdvajanje slike najveće rezolucije iz srcset-a
                    srcset_parts = srcset.split(',')
                    if srcset_parts:
                        # Uzimamo poslednju (najveće rezolucije) sliku
                        last_part = srcset_parts[-1].strip()
                        src_url = last_part.split(' ')[0]
                        if '/_next/image?url=' in src_url:
                            try:
                                parsed_url = urlparse(src_url)
                                query_params = parse_qs(parsed_url.query)
                                if 'url' in query_params:
                                    actual_url = unquote(query_params['url'][0])
                                    image_urls.append(actual_url)
                            except Exception as e:
                                self.logger.warning(f"Neuspešno parsiranje srcset URL-a {src_url}: {e}")
        
        # Kreiranje MediaItem objekta ako imamo slike
        if image_urls:
            media_item = MediaItem()
            media_item['providerKey'] = gtin
            
            # Dodavanje slika (maksimalno 10)
            for i, url in enumerate(image_urls[:10], 1):
                if url and url.startswith(('http://', 'https://')):
                    media_item[f'imageurl_{i}'] = url
            
            yield media_item
