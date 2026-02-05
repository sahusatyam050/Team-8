import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any
import validators


class WebScraper:
    """General-purpose web scraper that extracts all types of data from websites."""
    
    def __init__(self, url: str):
        self.url = url
        self.soup = None
        self.base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
    def fetch_page(self) -> bool:
        """Fetch the webpage content."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.content, 'html.parser')
            return True
        except Exception as e:
            raise Exception(f"Failed to fetch webpage: {str(e)}")
    
    def extract_metadata(self) -> Dict[str, str]:
        """Extract page metadata (title, description, keywords)."""
        metadata = {
            'title': '',
            'description': '',
            'keywords': '',
            'author': ''
        }
        
        # Title
        title_tag = self.soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)
        
        # Meta tags
        meta_desc = self.soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '')
        
        meta_keywords = self.soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            metadata['keywords'] = meta_keywords.get('content', '')
        
        meta_author = self.soup.find('meta', attrs={'name': 'author'})
        if meta_author:
            metadata['author'] = meta_author.get('content', '')
        
        return metadata
    
    def extract_text(self) -> Dict[str, Any]:
        """Extract all text content from the page."""
        text_data = {
            'headings': {
                'h1': [],
                'h2': [],
                'h3': [],
                'h4': [],
                'h5': [],
                'h6': []
            },
            'paragraphs': [],
            'all_text': ''
        }
        
        # Extract headings
        for level in range(1, 7):
            tag_name = f'h{level}'
            headings = self.soup.find_all(tag_name)
            text_data['headings'][tag_name] = [h.get_text(strip=True) for h in headings if h.get_text(strip=True)]
        
        # Extract paragraphs
        paragraphs = self.soup.find_all('p')
        text_data['paragraphs'] = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
        
        # Extract all visible text
        # Remove script and style elements
        for script in self.soup(['script', 'style', 'meta', 'noscript']):
            script.decompose()
        
        text_data['all_text'] = self.soup.get_text(separator=' ', strip=True)
        
        return text_data
    
    def extract_images(self) -> List[Dict[str, str]]:
        """Extract all images with their URLs and alt text."""
        images = []
        img_tags = self.soup.find_all('img')
        
        for img in img_tags:
            src = img.get('src', '')
            if src:
                # Convert relative URLs to absolute
                absolute_url = urljoin(self.base_url, src)
                
                images.append({
                    'url': absolute_url,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
        
        return images
    
    def extract_links(self) -> Dict[str, List[Dict[str, str]]]:
        """Extract all links (internal and external)."""
        links = {
            'internal': [],
            'external': []
        }
        
        a_tags = self.soup.find_all('a', href=True)
        
        for a in a_tags:
            href = a.get('href', '')
            text = a.get_text(strip=True)
            
            if not href or href.startswith('#'):
                continue
            
            # Convert to absolute URL
            absolute_url = urljoin(self.base_url, href)
            
            link_data = {
                'url': absolute_url,
                'text': text,
                'title': a.get('title', '')
            }
            
            # Determine if internal or external
            if urlparse(absolute_url).netloc == urlparse(self.base_url).netloc:
                links['internal'].append(link_data)
            else:
                links['external'].append(link_data)
        
        return links
    
    def extract_tables(self) -> List[Dict[str, Any]]:
        """Extract all tables from the page."""
        tables_data = []
        tables = self.soup.find_all('table')
        
        for idx, table in enumerate(tables):
            table_info = {
                'index': idx + 1,
                'headers': [],
                'rows': []
            }
            
            # Extract headers
            thead = table.find('thead')
            if thead:
                headers = thead.find_all('th')
                table_info['headers'] = [th.get_text(strip=True) for th in headers]
            else:
                # Try to get headers from first row
                first_row = table.find('tr')
                if first_row:
                    headers = first_row.find_all('th')
                    if headers:
                        table_info['headers'] = [th.get_text(strip=True) for th in headers]
            
            # Extract rows
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    # Skip if this is the header row
                    if row_data != table_info['headers']:
                        table_info['rows'].append(row_data)
            
            if table_info['rows']:  # Only add if there's data
                tables_data.append(table_info)
        
        return tables_data
    
    def scrape_all(self) -> Dict[str, Any]:
        """Scrape all data from the webpage."""
        # Validate URL
        if not validators.url(self.url):
            raise ValueError("Invalid URL provided")
        
        # Fetch the page
        self.fetch_page()
        
        # Extract all data
        data = {
            'url': self.url,
            'metadata': self.extract_metadata(),
            'text': self.extract_text(),
            'images': self.extract_images(),
            'links': self.extract_links(),
            'tables': self.extract_tables(),
            'stats': {
                'total_images': 0,
                'total_links': 0,
                'total_tables': 0,
                'total_headings': 0,
                'total_paragraphs': 0
            }
        }
        
        # Calculate statistics
        data['stats']['total_images'] = len(data['images'])
        data['stats']['total_links'] = len(data['links']['internal']) + len(data['links']['external'])
        data['stats']['total_tables'] = len(data['tables'])
        data['stats']['total_headings'] = sum(len(headings) for headings in data['text']['headings'].values())
        data['stats']['total_paragraphs'] = len(data['text']['paragraphs'])
        
        return data
