# SSE (Server-Sent Events) Support ✅

## ✅ SSE теперь полностью поддерживается!

MCP сервер теперь работает через SSE, как и первый сервер (my-1c-mcp-server).

## Конфигурация VS Code

Используйте эту конфигурацию в `~/.config/Code/User/globalStorage/mcp.json`:

```json
{
  "mcpServers": {
    "my-1c-mcp-server": {
      "url": "http://192.168.1.13:8012/sse",
      "timeout": 60,
      "headers": {
        "x-collection-name": "1cservice_rag"
      },
      "disabled": false,
      "alwaysAllow": []
    },
    "1c-syntax-helper": {
      "url": "http://192.168.1.13:8002/mcp",
      "timeout": 60,
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

## Как работает SSE

### 1. Установка соединения
Клиент подключается к `GET http://192.168.1.13:8002/mcp`

### 2. Получение начальных событий

**Event: connection**
```
event: connection
data: {"status": "connected", "session_id": "uuid", "timestamp": 1234567890}
```

**Event: message (инициализация)**
```
event: message
data: {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": "2024-11-05", "capabilities": {...}, "serverInfo": {...}}}
```

**Event: endpoint**
```
event: endpoint
data: /mcp/messages?session_id=uuid
```

### 3. Отправка запросов
Клиент отправляет JSON-RPC запросы на endpoint из события `endpoint`:
```
POST http://192.168.1.13:8002/mcp/messages?session_id=uuid
Content-Type: application/json

{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
```

### 4. Поддержание соединения
Сервер отправляет ping события каждые 30 секунд:
```
event: ping
data: {"timestamp": 1234567890, "session_id": "uuid"}
```

## Доступные методы

- `initialize` - Инициализация MCP сессии
- `tools/list` - Получение списка доступных инструментов
- `tools/call` - Вызов инструмента
- `prompts/list` - Список подсказок
- `resources/list` - Список ресурсов
- `roots/list` - Список корневых элементов

## Тестирование SSE

```bash
# Подключение к SSE endpoint
curl -N http://192.168.1.13:8002/mcp

# Отправка запроса через messages endpoint
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}' \
  "http://192.168.1.13:8002/mcp/messages?session_id=YOUR_SESSION_ID"
```

## Преимущества SSE

✅ **Совместимость** - Работает так же, как первый MCP сервер  
✅ **Real-time** - Постоянное соединение для push-уведомлений  
✅ **Простота** - Использует стандартный HTTP  
✅ **Автоматическая инициализация** - Сервер сразу отправляет capabilities  

## Альтернативные транспорты

Если SSE не подходит, можно использовать:
- **JSON-RPC**: `POST http://192.168.1.13:8002/mcp`
- **WebSocket**: `ws://192.168.1.13:8002/mcp/ws`
