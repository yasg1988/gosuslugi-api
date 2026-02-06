# Исследование API ГИС ЖКХ (2026-02-06)

Результаты исследования публичных эндпоинтов dom.gosuslugi.ru.

## Два типа GUID

| Тип | Источник | Пример | Где используется |
|-----|----------|--------|-----------------|
| **FIAS objectguid** | БД ФИАС (`as_houses.objectguid`) | `080439f6-256d-433d-9c2b-0363c5a8a686` | `/nsi/.../fias/v4/houses?houseCodes=` |
| **GIS GKH GUID** | homemanagement API | `700f05da-b213-41dc-b530-c8a48a214509` | `/homemanagement/.../public/1/`, `/information-disclosure/.../house-info` |

Перепутать нельзя — будет HTTP 500 или пустой результат.

## Рабочие публичные эндпоинты (без авторизации)

### 1. Поиск организации (УК/ТСЖ)
```
POST /ppa/api/rest/services/ppa/organizations/chooser/search;page=1;itemsPerPage=10
Content-Type: application/json

{
  "commonSearchString": "ИНН или название",
  "regionNames": ["Республика Марий Эл"],
  ...
}
```
**Возвращает:** guid, название, ИНН, ОГРН, ФИО руководителя, роли

### 2. Дома по организации
```
POST /homemanagement/api/rest/services/houses/public/searchByOrg?pageIndex=1&elementsPerPage=100
Content-Type: application/json

{"organizationGuid": "...", "calcCount": true}
```
**Возвращает:** общее количество, список домов с GIS GKH GUID, FIAS GUID, адрес

### 3. Детали управления домом
```
GET /homemanagement/api/rest/services/houses/public/1/{gisGkhGuid}/
```
**Возвращает:** JSON 14KB+ — полная информация об управлении, адресная иерархия

### 4. Характеристики дома (information-disclosure)
```
GET /information-disclosure/api/rest/services/disclosures/mkd/house-info?houseGuid={gisGkhGuid}
Заголовки: Session-GUID, Request-GUID (случайные UUID)
```
**Возвращает:** год постройки, этажность, кол-во квартир, площадь, энергоэффективность, фонд капремонта

### 5. ФИАС-lookup по objectguid
```
GET /nsi/api/rest/services/nsi/fias/v4/houses?houseCodes={fiasObjectguid}&includeDuplicates=false&actual=true
```
**Возвращает:** данные ФИАС — адрес, почтовый индекс. **houseCodes должен быть UUID, НЕ целое число objectid!**

### 6. Детали организации
```
GET /ppa/api/rest/services/ppa/public/organizations/orgByGuid?organizationGuid={guid}
```
**Возвращает:** подробная информация об организации

## Нерабочие эндпоинты

| Эндпоинт | Статус | Примечание |
|----------|--------|------------|
| `/licenses/.../region-license-xls/{region}` | 403 | Скачивание лицензий заблокировано |
| `/homemanagement/.../houses/search?regionCode=12` | 403 | Требуется авторизация |
| `/homemanagement/.../public/searchByAddress` | WAF | Срабатывает защита от ботов |
| `/nsi/.../fias/v4/addrobj` | 500 | Эндпоинт удалён |
| `/nsi/.../fias/v4/search` | 500 | Эндпоинт удалён |

## Алгоритм сбора данных

```
1. Найти все управляющие компании региона (search_organizations)
2. Для каждой организации → список домов (get_houses_by_org)
3. Для каждого дома → получить GIS GKH GUID
4. По GIS GKH GUID → характеристики дома (get_house_info)
5. По FIAS GUID (из шага 2) → связать с БД ФИАС
```

## Доступные характеристики домов

Из эндпоинта `information-disclosure`:
- Год постройки
- Количество этажей
- Количество квартир
- Общая площадь здания (кв.м)
- Класс энергоэффективности
- Фонд капитального ремонта
- Процент износа здания
- Информация об управляющей организации
