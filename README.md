## gosuslugi-api

Python-библиотека для работы с публичным API `https://dom.gosuslugi.ru/` (ГИС ЖКХ).

> Форк [GregEremeev/gosuslugi-api](https://github.com/GregEremeev/gosuslugi-api) с обновлёнными методами, rate limiting и документацией.

### Доступные данные (без авторизации)

| Данные | Метод | Статус |
|--------|-------|--------|
| Поиск организации (по ИНН, названию) | `search_organizations()` | Работает |
| Детали организации | `get_organization()` | Работает |
| Дома по организации | `get_houses_by_org()` | Работает |
| Все дома (авто-пагинация) | `get_all_houses_by_org()` | Работает |
| Детали управления домом | `get_home_management()` | Работает |
| Характеристики дома (год, этажи, площадь) | `get_house_info()` | Работает |
| ФИАС-lookup по objectguid | `get_actual_houses()` | Работает |
| Информация о лицензиях | `get_licenses()` | Заблокирован (HTTP 403) |

### Важно: два типа GUID

API использует две разные системы GUID. **Не путайте их!**

| Тип GUID | Источник | Где используется |
|----------|----------|-----------------|
| **FIAS objectguid** | БД ФИАС | `get_actual_houses()` |
| **GIS GKH GUID** | `get_houses_by_org()` → поле `guid` | `get_home_management()`, `get_house_info()` |

### Быстрый старт

1. Установка:
```bash
pip install gosuslugi-api
```

2. Поиск организаций и получение данных о домах:

```python
from gosuslugi_api.clients import GosUslugiAPIClient

client = GosUslugiAPIClient()

# Поиск управляющих компаний в регионе
orgs = client.search_organizations(
    query='управляющая компания',
    region_names=['Республика Марий Эл'],
)
print(f'Найдено {len(orgs)} организаций')

# Получить дома под управлением организации
org_guid = orgs[0]['guid']
houses = client.get_houses_by_org(org_guid, per_page=10)
print(f'Всего домов: {houses["total"]}')

for house in houses['items']:
    print(f'  {house.get("address", "Н/Д")}')

    # Характеристики дома (год постройки, этажи, площадь, квартиры)
    gis_guid = house['guid']
    try:
        info = client.get_house_info(gis_guid)
        print(f'    Данные: {info}')
    except Exception as e:
        print(f'    Недоступно: {e}')
```

3. Перебор ВСЕХ домов организации:

```python
# Авто-пагинация — возвращает отдельные записи домов
for house in client.get_all_houses_by_org(org_guid, per_page=100):
    print(house.get('address', 'Н/Д'))
```

4. ФИАС-lookup:

```python
# Поиск по FIAS objectguid (формат UUID, НЕ целое число!)
fias_data = client.get_actual_houses('080439f6-256d-433d-9c2b-0363c5a8a686')
print(fias_data)
```

### Rate limiting

Клиент включает встроенное ограничение частоты запросов (0.5 сек между запросами по умолчанию):

```python
# Свой интервал
client = GosUslugiAPIClient(rate_limit=1.0)  # 1 сек между запросами

# Отключить ограничение (не рекомендуется)
client = GosUslugiAPIClient(rate_limit=0)
```

### REST API (FastAPI)

Библиотека включает FastAPI-обёртку для развёртывания как веб-сервис:

```bash
docker build -t gis-gkh-api .
docker run -p 8000:8000 gis-gkh-api
```

Эндпоинты:
- `GET /` — health check
- `GET /organizations/search?query=ИНН&region=Республика Марий Эл` — поиск организаций
- `GET /organizations/{guid}` — детали организации
- `GET /organizations/{guid}/houses` — дома организации
- `GET /houses/{guid}/management` — детали управления домом
- `GET /houses/{guid}/info` — характеристики дома
- `GET /fias/houses/{fias_guid}` — ФИАС-lookup

### Изменения относительно оригинала

- Добавлен `search_organizations()` с фильтрацией по региону
- Добавлены `get_houses_by_org()` и `get_all_houses_by_org()` для списков домов
- Исправлены методы, обходившие HTTP-клиент (теперь все через `_http_client`)
- Добавлен rate limiting для предотвращения блокировки IP
- Увеличен таймаут по умолчанию с 3 до 10 секунд
- Добавлены docstrings и type hints
- Обновлено для Python 3.8+
- Добавлена FastAPI-обёртка и Dockerfile
