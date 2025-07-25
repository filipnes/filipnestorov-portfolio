# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html
from collections import OrderedDict
import scrapy


class ProductItem(scrapy.Item):
    fields = OrderedDict([
        ('providerkey', scrapy.Field()),
        ('gtin', scrapy.Field()),
        ('manufacturerkey', scrapy.Field()),
        ('brand', scrapy.Field()),
        ('productType', scrapy.Field()),
        ('weight', scrapy.Field()),
        ('title', scrapy.Field()),
        ('price', scrapy.Field()), 
        ('countryoforigin', scrapy.Field()),
        ('tariccode', scrapy.Field()),
        ('length', scrapy.Field()),
        ('width', scrapy.Field()),
        ('height', scrapy.Field()),
        ('releasedate', scrapy.Field()),
        ('tarescode', scrapy.Field()),
        ('weeenumber', scrapy.Field()),
        ('variantname', scrapy.Field()),
        ('longdescription', scrapy.Field()),
        ('composition', scrapy.Field()),
        ('application', scrapy.Field()),

    ])

class SpecItem(scrapy.Item):
    fields = OrderedDict([
        ('providerKey', scrapy.Field()),
        ('SpecificationKey', scrapy.Field()),
        ('SpecificationValue', scrapy.Field()),
    ])

class MediaItem(scrapy.Item):
    fields = OrderedDict([
        ('providerKey', scrapy.Field()),
        ('gtin', scrapy.Field()),
        ('datasheeturl_1', scrapy.Field()),
        ('datasheeturl_2', scrapy.Field()),
        ('datasheeturl_3', scrapy.Field()),
        ('safetydatasheet', scrapy.Field()),
        ('energylabel', scrapy.Field()),
        ('imageurl_1', scrapy.Field()),
        ('imageurl_2', scrapy.Field()),
        ('imageurl_3', scrapy.Field()),
        ('imageurl_4', scrapy.Field()),
        ('imageurl_5', scrapy.Field()),
        ('imageurl_6', scrapy.Field()),
        ('imageurl_7', scrapy.Field()),
        ('imageurl_8', scrapy.Field()),
        ('imageurl_9', scrapy.Field()),
        ('imageurl_10', scrapy.Field()),
    ])

