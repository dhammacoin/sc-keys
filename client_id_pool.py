import requests
import re
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor

# Настройки
BASE = "https://soundcloud.com"
API_TEST = "https://api-v2.soundcloud.com/tracks?ids=566083323&client_id={}" # Конкретный ID трека для теста
FILE = "client_ids.json"

class SC_Extractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://soundcloud.com/"
        })
        self.patterns = [
            r'client_id\s*[:=]\s*"([a-zA-Z0-9]{32})"', # SC ключи обычно 32 символа
            r'clientId\s*[:=]\s*"([a-zA-Z0-9]{32})"',
            r'client_id[:=]([a-zA-Z0-9]{32})',
            r'"client_id","([a-zA-Z0-9]{32})"'
        ]

    def load_pool(self):
        if os.path.exists(FILE):
            with open(FILE, "r") as f:
                return json.load(f)
        return {"client_ids": [], "updated": 0}

    def save_pool(self, keys):
        data = {
            "client_ids": sorted(list(set(keys))),
            "updated": int(time.time())
        }
        with open(FILE, "w") as f:
            json.dump(data, f, indent=2)

    def validate(self, client_id):
        if not client_id or len(client_id) < 32: return False
        try:
            # Используем тайм-аут поменьше, чтобы не висеть
            r = self.session.get(API_TEST.format(client_id), timeout=5)
            return r.status_code == 200
        except:
            return False

    def get_js_urls(self):
        try:
            r = self.session.get(BASE, timeout=10)
            # Ищем скрипты в футере и теле страницы
            return re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', r.text)
        except Exception as e:
            print(f"[!] Ошибка главной: {e}")
            return []

    def extract_from_js(self, url):
        try:
            js = self.session.get(url, timeout=10).text
            found = []
            for p in self.patterns:
                found.extend(re.findall(p, js))
            return found
        except:
            return []

    def run(self):
        print("[+] Загрузка пула...")
        pool = self.load_pool()
        old_keys = pool["client_ids"]
        
        print(f"[+] Проверка {len(old_keys)} старых ключей...")
        # Параллельная валидация старых ключей
        with ThreadPoolExecutor(max_workers=10) as ex:
            valid_old = list(filter(None, ex.map(lambda k: k if self.validate(k) else None, old_keys)))

        print("[+] Поиск новых JS бандлов...")
        js_urls = self.get_js_urls()
        
        print(f"[+] Сканирование {len(js_urls)} файлов...")
        candidates = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = ex.map(self.extract_from_js, js_urls)
            for r in results: candidates.extend(r)
        
        candidates = list(set(candidates))
        print(f"[+] Найдено кандидатов: {len(candidates)}. Валидация...")
        
        with ThreadPoolExecutor(max_workers=10) as ex:
            valid_new = list(filter(None, ex.map(lambda k: k if self.validate(k) else None, candidates)))

        final_keys = list(set(valid_old + valid_new))
        self.save_pool(final_keys)
        print(f"[+++] Готово! В пуле: {len(final_keys)} ключей. Файл обновлен.")

if __name__ == "__main__":
    SC_Extractor().run()