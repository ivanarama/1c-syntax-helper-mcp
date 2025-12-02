# VS Code MCP Configuration - NO SSE

## ⚠️ ВАЖНО: SSE НЕ ПОДДЕРЖИВАЕТСЯ!

Сервер **НЕ ПОДДЕРЖИВАЕТ** Server-Sent Events (SSE). Используйте только JSON-RPC через `command` + `args`.

## Правильная конфигурация VS Code

### 1. mcp.json (ОБЯЗАТЕЛЬНО)

Создайте файл `~/.config/Code/User/globalStorage/mcp.json`:

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

### 2. settings.json (ОБЯЗАТЕЛЬНО)

Добавьте в `~/.config/Code/User/settings.json`:

```json
{
  "mcp.discovery.enabled": false,
  "mcp.autoConnect": true,
  "mcp.logging.level": "debug"
}
```

## ❌ НЕ ИСПОЛЬЗУЙТЕ:

```json
// НЕПРАВИЛЬНО - НЕ РАБОТАЕТ!
{
  "mcpServers": {
    "1c-syntax-helper": {
      "url": "http://192.168.1.13:8002/mcp"
    }
  }
}
```

## ✅ ПРАВИЛЬНО:

```json
// ПРАВИЛЬНО - РАБОТАЕТ!
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
      "timeout": 60000
    }
  }
}
```

## Доступные endpoints:

- ✅ **JSON-RPC**: `POST http://192.168.1.13:8002/mcp` (используйте этот!)
- ✅ **WebSocket**: `ws://192.168.1.13:8002/mcp/ws`
- ✅ **Info**: `GET http://192.168.1.13:8002/mcp`
- ❌ **SSE**: `GET http://192.168.1.13:8002/mcp/sse` (НЕ ПОДДЕРЖИВАЕТСЯ!)

## Если все еще видите ошибку SSE:

1. **Перезапустите VS Code** полностью
2. **Очистите кэш MCP**: Удалите `~/.config/Code/User/globalStorage/mcp.json` и создайте заново
3. **Проверьте настройки**: Убедитесь, что `mcp.discovery.enabled: false`
4. **Используйте только command + args** конфигурацию

## Тестирование:

После настройки VS Code должен успешно подключаться и показывать 5 инструментов для работы с 1C:

- find_1c_help
- get_syntax_info  
- get_quick_reference
- search_by_context
- list_object_members
