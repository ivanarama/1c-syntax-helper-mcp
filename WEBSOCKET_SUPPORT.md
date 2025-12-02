# WebSocket поддержка для MCP сервера

## Обзор изменений

В MCP сервер была добавлена поддержка WebSocket соединений наряду с существующей поддержкой SSE (Server-Sent Events) и HTTP JSON-RPC.

## Новые возможности

### WebSocket Endpoint

- **URL**: `ws://localhost:8000/mcp/ws` (или `ws://localhost:8002/mcp/ws` если используется Docker с маппингом портов)
- **Протокол**: JSON-RPC 2.0 через WebSocket
- **Поддержка**: Полная совместимость с MCP протоколом

### Поддерживаемые методы

Все методы MCP протокола поддерживаются через WebSocket:

- `initialize` - Инициализация соединения
- `tools/list` - Получение списка доступных инструментов
- `tools/call` - Вызов инструментов
- `prompts/list` - Список промптов (пустой)
- `prompts/get` - Получение промпта
- `resources/list` - Список ресурсов (пустой)
- `resources/read` - Чтение ресурса
- `roots/list` - Список корневых директорий (пустой)
- `sampling/create` - Создание семплинга (не поддерживается)
- `sampling/complete` - Завершение семплинга (не поддерживается)
- `notifications/initialized` - Уведомление об инициализации

### Batch запросы

WebSocket endpoint поддерживает batch запросы JSON-RPC (массив запросов в одном сообщении).

## Технические детали

### Архитектура

Реализация минимально инвазивная:

1. **Зависимости**: Добавлена только библиотека `websockets==12.0`
2. **Код**: Добавлен новый WebSocket endpoint `/mcp/ws`
3. **Переиспользование**: Максимальное переиспользование существующей логики

### Новые функции

- `mcp_websocket_endpoint()` - WebSocket обработчик
- `process_jsonrpc_message()` - Обработка JSON-RPC сообщений
- `process_single_jsonrpc_message()` - Обработка одиночного запроса

### Логирование

WebSocket соединения полностью логируются:
- Установка и разрыв соединения
- Входящие и исходящие сообщения
- Ошибки обработки

## Использование

### Подключение

```javascript
const ws = new WebSocket('ws://localhost:8000/mcp/ws');

ws.onopen = function() {
    console.log('WebSocket подключен');
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log('Получен ответ:', response);
};
```

### Инициализация MCP

```javascript
const initRequest = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "my-client",
            "version": "1.0.0"
        }
    }
};

ws.send(JSON.stringify(initRequest));
```

### Вызов инструмента

```javascript
const toolCall = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "find_1c_help",
        "arguments": {
            "query": "документ",
            "limit": 5
        }
    }
};

ws.send(JSON.stringify(toolCall));
```

## Тестирование

### Автоматические тесты

Запустите Python скрипт для автоматического тестирования:

```bash
python3 test_websocket.py
```

### Ручное тестирование

Откройте `websocket_test.html` в браузере для интерактивного тестирования WebSocket соединения.

## Совместимость

### Существующие клиенты

- **SSE endpoint** (`GET /mcp`) продолжает работать
- **HTTP JSON-RPC** (`POST /mcp`) продолжает работать  
- **WebSocket** (`ws://host/mcp/ws`) - новая возможность

### MCP клиенты

WebSocket поддержка полностью совместима с MCP протоколом версии 2024-11-05.

## Производительность

### Преимущества WebSocket

- **Bidirectional**: Двусторонняя связь
- **Low latency**: Низкая задержка
- **Connection reuse**: Переиспользование соединения
- **Real-time**: Поддержка real-time обновлений

### Vs SSE

| Характеристика | SSE | WebSocket |
|---------------|-----|-----------|
| Направление | Сервер → Клиент | Bidirectional |
| Протокол | HTTP | WebSocket |
| Overhead | Выше | Ниже |
| Real-time | Ограничено | Полная поддержка |

## Мониторинг

WebSocket соединения отслеживаются через:

- Стандартное логирование приложения
- Метрики производительности
- Rate limiting (через существующий middleware)

## Безопасность

### CORS

WebSocket соединения наследуют CORS настройки от FastAPI приложения.

### Rate Limiting

WebSocket запросы проходят через существующий rate limiting middleware.

### Обработка ошибок

Все ошибки WebSocket обрабатываются gracefully с отправкой соответствующих JSON-RPC error responses.
