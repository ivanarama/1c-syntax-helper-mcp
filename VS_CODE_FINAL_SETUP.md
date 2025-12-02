# VS Code MCP Setup - Final Configuration

## Проблема решена! ✅

SSE endpoint был отключен, так как VS Code имеет проблемы с SSE соединениями. Теперь используется только JSON-RPC через `command` + `args`.

## Конфигурация VS Code

### 1. Настройка mcp.json

Создайте или обновите файл `~/.config/Code/User/globalStorage/mcp.json`:

```json
{
  "mcpServers": {
    "1c-syntax-helper": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://192.168.1.13:8002/mcp"
      ],
      "env": {},
      "cwd": "",
      "timeout": 60000,
      "disabled": false
    }
  }
}
```

### 2. Настройка settings.json

Добавьте в `~/.config/Code/User/settings.json`:

```json
{
  "mcp.discovery.enabled": false,
  "mcp.servers": {
    "1c-syntax-helper": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://192.168.1.13:8002/mcp"
      ],
      "env": {},
      "cwd": "",
      "timeout": 60000
    }
  },
  "mcp.autoConnect": true,
  "mcp.logging.level": "debug"
}
```

## Доступные Endpoints

- **JSON-RPC**: `POST http://192.168.1.13:8002/mcp` ✅ (рекомендуется)
- **WebSocket**: `ws://192.168.1.13:8002/mcp/ws` ✅
- **Info**: `GET http://192.168.1.13:8002/mcp` ✅
- **Tools**: `GET http://192.168.1.13:8002/mcp/tools` ✅
- **Health**: `GET http://192.168.1.13:8002/health` ✅

## Что изменилось

1. **SSE endpoint отключен** - больше не вызывает ошибки "undefined"
2. **GET /mcp** теперь возвращает информацию о сервере вместо SSE потока
3. **JSON-RPC endpoint** работает стабильно через POST /mcp
4. **WebSocket endpoint** доступен для real-time соединений

## Тестирование

После настройки VS Code должен успешно подключаться к MCP серверу без ошибок SSE.

## Логи

Для отладки включите debug логирование в VS Code:
```json
"mcp.logging.level": "debug"
```

Это поможет увидеть детали подключения и возможные проблемы.
