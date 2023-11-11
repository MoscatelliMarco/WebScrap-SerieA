from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from SerieA.spiders.matches import MatchesSpider

# Get project settings
project_settings = get_project_settings()

# Create a CrawlerProcess with the updated settings
process = CrawlerProcess(settings=project_settings)

# Start the crawling using the MatchesSpider
process.crawl(MatchesSpider)
process.start()