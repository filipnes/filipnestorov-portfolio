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
        (r'/proizvod/', 'parse')  # Products only
    ]
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 3,
        'ROBOTSTXT_OBEY': False,
    }

    def parse(self, response):
        self.logger.info(f"Parsing URL: {response.url}")
        
        # Extract GTIN and other data from JSON-LD script
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
            self.logger.error(f"GTIN not found for {response.url}")
            return
        
        # Create ProductItem object
        product = ProductItem()
        
        # Pre-extract specifications to get brand and other data
        specs_data = {}
        spec_rows = response.css('table tbody tr')
        brand_from_specs = None
        
        for row in spec_rows:
            cells = row.css('td')
            if len(cells) >= 2:
                key_cell = cells[0]
                value_cell = cells[1]
                
                # Skip headers (colspan=2)
                if key_cell.css('[colspan]'):
                    continue
                
                key = key_cell.css('::text').get()
                value = value_cell.css('span::text').get()
                
                if key and value:
                    key_clean = key.strip()
                    value_clean = value.strip()
                    specs_data[key_clean] = value_clean
                    
                    # Check for brand
                    if key_clean == 'Brend':
                        brand_from_specs = value_clean
        
        product['providerkey'] = gtin
        product['gtin'] = gtin
        
        # Extract basic product information from JSON-LD
        title = ""
        if json_ld_data:
            title = json_ld_data.get('name', '').strip()
            product['title'] = title
            
            # Extract price from JSON-LD offers section
            offers = json_ld_data.get('offers', {})
            if offers and offers.get('price'):
                product['price'] = offers['price']
            
            # Extract category path from JSON-LD
            category_data = json_ld_data.get('category', {})
            if category_data and category_data.get('itemListElement'):
                category_items = category_data['itemListElement']
                # Get category names, skip first one if too generic
                category_names = [item.get('name', '') for item in category_items if item.get('name')]
                if len(category_names) > 1:
                    # Use last categories for more specific classification
                    product['productType'] = ' > '.join(category_names[-3:])
                elif category_names:
                    product['productType'] = category_names[-1]
        
        # Extract brand - priority: specifications > first word from title
        if brand_from_specs:
            product['brand'] = brand_from_specs
        elif title:
            # Use first word from title as fallback brand
            first_word = title.split()[0] if title.split() else ""
            if first_word:
                product['brand'] = first_word
        
        # Extract description using XPath
        description_parts = []
        
        # Method 1: Try to find active tab panel with description
        description_xpath = '//div[@role="tabpanel"][@data-headlessui-state="selected"]//text()[normalize-space()]'
        description_texts = response.xpath(description_xpath).getall()
        
        if description_texts:
            # Clean and join all text parts
            for text in description_texts:
                cleaned_text = text.strip()
                if cleaned_text and len(cleaned_text) > 3:  # Skip very short texts
                    description_parts.append(cleaned_text)
        
        # Method 2: Fallback - search for description in any tab panel with content
        if not description_parts:
            fallback_xpath = '//div[@role="tabpanel"]//li/text()[normalize-space()]'
            fallback_texts = response.xpath(fallback_xpath).getall()
            
            for text in fallback_texts:
                cleaned_text = text.strip()
                if cleaned_text and len(cleaned_text) > 10:  # Skip very short texts
                    description_parts.append(cleaned_text)
        
        # Method 3: CSS selector as last resort
        if not description_parts:
            css_description = response.css('div[role="tabpanel"][data-headlessui-state="selected"] li::text').getall()
            description_parts = [text.strip() for text in css_description if text.strip()]
        
        if description_parts:
            # Join all description parts with spaces
            full_description = ' '.join(description_parts)
            # Clean multiple whitespaces
            full_description = re.sub(r'\s+', ' ', full_description).strip()
            if full_description:
                product['longdescription'] = full_description
        
        # Extract manufacturer code (model) from specifications
        model = specs_data.get('Model')
        if model:
            product['manufacturerkey'] = model
        
        # Extract country of origin from specifications
        country = specs_data.get('Zemlja porekla')
        if country:
            product['countryoforigin'] = country
        
        yield product
        
        # Extract specifications and create SpecItems objects
        for key, value in specs_data.items():
            spec_item = SpecItem()
            spec_item['providerKey'] = gtin
            spec_item['SpecificationKey'] = key
            spec_item['SpecificationValue'] = value
            yield spec_item
        
        # Extract images
        image_urls = []
        
        # Method 1: Extract from img src attributes
        img_elements = response.css('button[aria-label*="Slika proizvoda"] img')
        for img in img_elements:
            src = img.css('::attr(src)').get()
            if src:
                # Extract actual image URL from Next.js image URL
                if '/_next/image?url=' in src:
                    try:
                        parsed_url = urlparse(src)
                        query_params = parse_qs(parsed_url.query)
                        if 'url' in query_params:
                            actual_url = unquote(query_params['url'][0])
                            image_urls.append(actual_url)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse image URL {src}: {e}")
                else:
                    image_urls.append(src)
        
        # Method 2: Extract from srcSet attribute (fallback option)
        if not image_urls:
            for img in img_elements:
                srcset = img.css('::attr(srcSet)').get()
                if srcset:
                    # Extract highest resolution image from srcset
                    srcset_parts = srcset.split(',')
                    if srcset_parts:
                        # Get last (highest resolution) image
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
                                self.logger.warning(f"Failed to parse srcset URL {src_url}: {e}")
        
        # Create MediaItem object if we have images
        if image_urls:
            media_item = MediaItem()
            media_item['providerKey'] = gtin
            
            # Add images (maximum 10)
            for i, url in enumerate(image_urls[:10], 1):
                if url and url.startswith(('http://', 'https://')):
                    media_item[f'imageurl_{i}'] = url
            
            yield media_item
