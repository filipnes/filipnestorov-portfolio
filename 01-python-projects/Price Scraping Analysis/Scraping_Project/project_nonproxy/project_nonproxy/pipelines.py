from itemadapter import ItemAdapter
from project_nonproxy.items import ProductItem, SpecItem, MediaItem
import paramiko
from paramiko import Transport, SFTPClient
import csv
import os

class BasePipeline:
    def __init__(self, settings):
        self.settings = settings
        self.item_class = None
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)
    
    def close_spider(self, spider):
        # Filter out rows with None values in the first column (providerkey)
        filtered_data = [row for row in self.data if row[0] is not None]
        
        if not filtered_data:
            spider.logger.info(f"Nema validnih podataka za {self.filename}. Fajl se neće kreirati.")
            self.file.close()
            if os.path.exists(self.filename):
                os.remove(self.filename)
            return
        
        # Get the original header row
        header_keys = list(self.item_class.fields.keys())
        
        # Determine which columns contain data
        non_empty_columns = []
        for col_idx, key in enumerate(header_keys):
            # Check if any row has a non-empty value in this column
            has_data = any(row[col_idx] for row in filtered_data if len(row) > col_idx)
            if has_data or col_idx == 0:  # Always keep the first column (providerKey)
                non_empty_columns.append(col_idx)
        
        # Create a new header with only non-empty columns
        new_header = [header_keys[i] for i in non_empty_columns]
        
        # Rewrite the file with only non-empty columns
        self.file.close()
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file, delimiter=";", quoting=csv.QUOTE_ALL)
        
        # Write the new header
        self.writer.writerow(new_header)
        
        # Sort the filtered data
        filtered_data.sort(key=lambda x: str(x[0]))
        
        # Write only the non-empty columns of each row
        for row in filtered_data:
            new_row = [row[i] for i in non_empty_columns if i < len(row)]
            self.writer.writerow(new_row)
        
        self.file.close()
        spider.logger.info(f"Fajl {self.filename} je uspešno kreiran sa {len(filtered_data)} records.")



class SpecPipeline(BasePipeline):
    def open_spider(self, spider):
        self.item_class = SpecItem
        self.data = []
        brand_segment = f"_{getattr(spider, 'brandName', '')}" if getattr(spider, 'brandName', '') else ""
        self.filename = f'{spider.name}{brand_segment}_scrapy_spec.csv'
        
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file, delimiter=";")
        headerkeys = list(SpecItem.fields.keys())
        self.writer.writerow(headerkeys)

    def process_item(self, item, spider):
        if isinstance(item, SpecItem):
            row = [item.get(key, "") for key in item.fields.keys()]
            if row not in self.data:  # Duplikate vermeiden
                self.data.append(row)
        return item
    


class ProductPipeline(BasePipeline):
    def open_spider(self, spider):
        self.item_class = ProductItem
        self.data = []
        self.seen_providerkeys = set() # Track seen providerkeys to avoid duplicates
        brand_segment = f"_{getattr(spider, 'brandName', '')}" if getattr(spider, 'brandName', '') else ""
        self.filename = f'{spider.name}{brand_segment}_scrapy_master.csv'
        
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file, delimiter=";", quoting=csv.QUOTE_ALL)
        headerkeys = list(ProductItem.fields.keys())
        self.writer.writerow(headerkeys)

    def process_item(self, item, spider):
        if isinstance(item, ProductItem):
            providerkey = item.get('providerkey')
            
            # Skip if we've already processed this providerkey
            if providerkey in self.seen_providerkeys:
                spider.logger.info(f"Skipping duplicate providerkey: {providerkey}")
                return item
            
            # Add to seen set and process the item
            self.seen_providerkeys.add(providerkey)
            row = [item.get(key, "") for key in item.fields.keys()]
            if row not in self.data:  # Duplikate vermeiden
                self.data.append(row)
        return item


class MediaPipeline(BasePipeline):
    def open_spider(self, spider):
        self.item_class = MediaItem
        self.data = []
        self.seen_providerkeys = set()  # Track seen providerkeys to avoid duplicates
        brand_segment = f"_{getattr(spider, 'brandName', '')}" if getattr(spider, 'brandName', '') else ""
        self.filename = f'{spider.name}{brand_segment}_scrapy_media.csv'
        
        self.file = open(self.filename, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file, delimiter=";", quoting=csv.QUOTE_ALL)
        headerkeys = list(MediaItem.fields.keys())
        self.writer.writerow(headerkeys)

    def process_item(self, item, spider):
        if isinstance(item, MediaItem):
            providerkey = item.get('providerKey')  # Note: MediaItem uses 'providerKey'
            
            # Skip if we've already processed this providerkey
            if providerkey in self.seen_providerkeys:
                spider.logger.info(f"Skipping duplicate media providerKey: {providerkey}")
                return item
            
            # Check if the item has any non-empty image or datasheet URLs
            has_content = any(
                item.get(field) 
                for field in item.fields.keys() 
                if field.startswith(('imageurl_', 'datasheeturl_'))
            )
            
            if has_content:
                self.seen_providerkeys.add(providerkey)
                # Process valid MediaItem
                row = [item.get(key, "") for key in item.fields.keys()]
                if row not in self.data:  # Avoid duplicates
                    self.data.append(row)
            else:
                spider.logger.info(f"Dropping MediaItem with only providerKey: {item.get('providerKey')}")
        
        return item
    
