# Устранение неполадок SSE подключения

## Ошибка "TypeError: fetch failed: unknown scheme"

Эта ошибка обычно возникает при неправильной настройке URL для подключения к MCP серверу.

### Возможные причины и решения:

#### 1. Неправильный протокол

**Проблема**: Использование `ws://` вместо `http://` для SSE
```javascript
// ❌ Неправильно - WebSocket протокол для SSE
const eventSource = new EventSource('ws://localhost:8000/mcp');

// ✅ Правильно - HTTP протокол для SSE  
const eventSource = new EventSource('http://localhost:8000/mcp');
```

#### 2. Неправильный порт

**Проблема**: Подключение к неправильному порту

**Docker Compose** (рекомендуется):
```bash
# Сервер доступен на порту 8000
curl http://localhost:8000/health
```

**Прямой запуск**:
```bash
# Сервер запущен на порту 8000
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

#### 3. Сервер не запущен

**Проверка статуса**:
```bash
# Проверка health endpoint
curl http://localhost:8000/health

# Проверка SSE endpoint
curl http://localhost:8000/mcp
```

#### 4. Проблемы с CORS

**Решение**: Убедитесь, что CORS настроен правильно в FastAPI:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Правильные URL для подключения:

#### SSE (Server-Sent Events)
```javascript
const eventSource = new EventSource('http://localhost:8000/mcp');
```

#### WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/mcp/ws');
```

#### HTTP JSON-RPC
```javascript
fetch('http://localhost:8000/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
});
```

### Диагностика подключения:

#### 1. Проверка доступности сервера
```bash
# Health check
curl -v http://localhost:8000/health

# SSE endpoint
curl -v http://localhost:8000/mcp
```

#### 2. Проверка портов
```bash
# Проверка, что порт 8000 слушается
netstat -tlnp | grep :8000
# или
ss -tlnp | grep :8000
```

#### 3. Проверка логов сервера
```bash
# Docker
docker logs mcp-1c-helper

# Прямой запуск
# Логи выводятся в консоль
```

### Примеры правильного подключения:

#### JavaScript (SSE)
```javascript
const eventSource = new EventSource('http://localhost:8000/mcp');

eventSource.onopen = function(event) {
    console.log('SSE соединение установлено');
};

eventSource.onmessage = function(event) {
    console.log('Получено сообщение:', event.data);
};

eventSource.onerror = function(event) {
    console.error('Ошибка SSE:', event);
};
```

#### JavaScript (WebSocket)
```javascript
const ws = new WebSocket('ws://localhost:8000/mcp/ws');

ws.onopen = function(event) {
    console.log('WebSocket соединение установлено');
};

ws.onmessage = function(event) {
    console.log('Получено сообщение:', event.data);
};

ws.onerror = function(error) {
    console.error('Ошибка WebSocket:', error);
};
```

### Частые ошибки:

1. **"unknown scheme"** → Используйте `http://` для SSE, `ws://` для WebSocket
2. **"Connection refused"** → Сервер не запущен или неправильный порт
3. **"CORS error"** → Проблемы с CORS настройками
4. **"404 Not Found"** → Неправильный путь к endpoint

### Быстрая диагностика:

```bash
# 1. Проверка сервера
curl http://localhost:8000/health

# 2. Проверка SSE
curl -N http://localhost:8000/mcp

# 3. Проверка WebSocket (требует специальных инструментов)
# Используйте браузерную консоль или wscat
```
