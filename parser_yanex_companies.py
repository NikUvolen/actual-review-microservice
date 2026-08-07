import re
import time
from urllib.parse import quote_plus, urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Настройка драйвера
driver = webdriver.Chrome()
wait = WebDriverWait(driver, 20)

# Открываем Яндекс Карты с вашим поисковым запросом
query = "кафе иркутск"
url = f"https://yandex.ru/maps/?text={quote_plus(query)}"
driver.get(url)

# Находим панель со результатами и прокручиваем её
wait.until(
    EC.presence_of_element_located((
        By.CSS_SELECTOR,
        "a[href*='/maps/org/'], a.search-snippet-view__link-overlay"
    ))
)
scroll_panel = wait.until(
    EC.presence_of_element_located((
        By.CSS_SELECTOR,
        ".search-list-view, .scroll__container, [class*='scroll__container']"
    ))
)


def collect_org_links() -> set[str]:
    elements = driver.find_elements(
        By.CSS_SELECTOR,
        "a[href*='/maps/org/'], a.search-snippet-view__link-overlay"
    )
    urls = set()
    for element in elements:
        href = element.get_attribute("href")
        if href and "/maps/org/" in href:
            full_url = urljoin("https://yandex.ru", href)
            match = re.search(r"(https://yandex\.ru/maps/org/[^/?#]+/\d+)/?", full_url)
            if match:
                urls.add(f"{match.group(1)}/")
    return urls

# Прокручиваем вниз, чтобы загрузились 100-200 организаций
urls = set()
same_count_retries = 0
for _ in range(30):
    before = len(urls)
    urls.update(collect_org_links())

    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_panel)
    driver.execute_script("arguments[0].dispatchEvent(new WheelEvent('wheel', {deltaY: 1200}))", scroll_panel)
    time.sleep(2)

    if len(urls) == before:
        same_count_retries += 1
    else:
        same_count_retries = 0

    if same_count_retries >= 5:
        break

print(f"Собрано ссылок: {len(urls)}")

with open('res.txt', 'w') as file:
    for url in sorted(urls):
        file.write(str(url) + '\n')

driver.quit()
