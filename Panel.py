import cloudscraper
import re

class PanelAPI:
    def __init__(self, panel_url, username, password):
        self.panel_url = panel_url
        self.username = username
        self.password = password
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=10
        )
        self.logged_in = False
        
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
    
    def login(self):
        try:
            print("🔄 Logging into panel...")
            login_page = self.scraper.get(f'{self.panel_url}/login')
            
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ''
            
            response = self.scraper.post(f'{self.panel_url}/login', data={
                'username': self.username,
                'password': self.password,
                '_token': csrf_token
            })
            
            if response.status_code == 200:
                self.logged_in = True
                print("✅ Panel login successful!")
                return True
            return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def generate_key(self, duration, max_devices=1):
        try:
            if not self.logged_in:
                if not self.login():
                    return None
            
            print(f"🔄 Generating {duration} key...")
            
            duration_map = {
                '5h': '5_hours', '3d': '3_days', '7d': '7_days',
                '14d': '14_days', '30d': '30_days', '60d': '60_days'
            }
            duration_value = duration_map.get(duration, duration)
            
            response = self.scraper.post(f'{self.panel_url}/generate', data={
                'duration': duration_value,
                'max_devices': str(max_devices)
            })
            
            patterns = [
                r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
                r'[A-Z0-9]{16,32}',
                r'"key":"([^"]+)"',
                r'"license":"([^"]+)"',
                r'<code>([^<]+)</code>',
                r'Key:\s*([A-Z0-9\-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    key = match.group(1) if match.groups() else match.group(0)
                    print(f"✅ Key generated: {key}")
                    return key
            
            print("❌ Could not extract key from response")
            return None
        except Exception as e:
            print(f"❌ Generation error: {e}")
            return None
