# Исправление проблемы: MCP работает в Cursor, но не работает в VS Code

## Проблема
MCP сервер успешно подключается в Cursor, но не работает в VS Code. Это распространенная проблема, связанная с конфликтом конфигураций между двумя редакторами.

## Причина
VS Code и Cursor используют разные файлы конфигурации для MCP, и VS Code может автоматически загружать конфигурацию из Cursor, что вызывает конфликты.

## Решение

### 1. Отключение автоматического обнаружения MCP в VS Code

**Через настройки UI:**
1. Откройте VS Code Settings (`Ctrl+,`)
2. Найдите "mcp" в поиске
3. Найдите параметр `Features > Chat > Mcp > Discovery: enabled`
4. Установите его в `false`

**Через settings.json:**
```json
{
  "mcp.discovery.enabled": false
}
```

### 2. Создание отдельной конфигурации для VS Code

#### Пути конфигурационных файлов:
- **Cursor**: `~/.cursor/mcp.json`
- **VS Code**: `~/Library/Application Support/Code/User/mcp.json` (macOS) или `%APPDATA%\Code\User\mcp.json` (Windows)

#### Создайте файл `mcp.json` для VS Code:

**macOS/Linux:**
```bash
# Создайте директорию если не существует
mkdir -p ~/Library/Application\ Support/Code/User/

# Создайте файл конфигурации
cat > ~/Library/Application\ Support/Code/User/mcp.json << 'EOF'
{
  "mcpServers": {
    "1c-syntax-helper": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://localhost:8000/mcp"
      ],
      "env": {},
      "cwd": "",
      "timeout": 30000
    }
  }
}
EOF
```

**Windows (PowerShell):**
```powershell
# Создайте директорию если не существует
$configDir = "$env:APPDATA\Code\User"
if (!(Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force
}

# Создайте файл конфигурации
@"
{
  "mcpServers": {
    "1c-syntax-helper": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://localhost:8000/mcp"
      ],
      "env": {},
      "cwd": "",
      "timeout": 30000
    }
  }
}
"@ | Out-File -FilePath "$configDir\mcp.json" -Encoding UTF8
```

### 3. Альтернативная конфигурация через settings.json VS Code

Если файл `mcp.json` не работает, используйте `settings.json`:

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
        "http://localhost:8000/mcp"
      ],
      "env": {},
      "cwd": "",
      "timeout": 30000
    }
  },
  "mcp.autoConnect": true,
  "mcp.logging.level": "info"
}
```

### 4. Проверка и тестирование

#### Проверьте статус сервера:
```bash
curl http://localhost:8000/health
```

#### Проверьте MCP endpoint:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {}
    }
  }'
```

#### В VS Code:
1. Откройте Command Palette (`Ctrl+Shift+P`)
2. Выполните: `MCP: Connect to Server`
3. Выберите `1c-syntax-helper`
4. Проверьте статус: `MCP: Show Server Status`

### 5. Дополнительные настройки

#### Если проблема persists, попробуйте:

**Очистка кэша VS Code:**
- Windows: Удалите `%APPDATA%\Code\User\workspaceStorage`
- macOS: Удалите `~/Library/Application Support/Code/User/workspaceStorage`
- Linux: Удалите `~/.config/Code/User/workspaceStorage`

**Переустановка MCP расширения:**
1. Откройте Extensions (`Ctrl+Shift+X`)
2. Найдите "Model Context Protocol"
3. Нажмите "Uninstall"
4. Перезапустите VS Code
5. Установите расширение заново

**Проверка версии VS Code:**
- Убедитесь, что VS Code версии 1.85+ (требуется для MCP)

### 6. Диагностика

#### Проверьте логи VS Code:
1. Command Palette → `Developer: Toggle Developer Tools`
2. Вкладка Console - ищите ошибки MCP

#### Проверьте логи MCP сервера:
```bash
# Если используете Docker
docker logs mcp-1c-helper

# Если запускаете напрямую
# Логи выводятся в консоль
```

## Альтернативное решение: Использование WebSocket

Если HTTP MCP не работает в VS Code, попробуйте WebSocket:

```json
{
  "mcp.discovery.enabled": false,
  "mcp.servers": {
    "1c-syntax-helper-ws": {
      "command": "node",
      "args": [
        "-e",
        "const WebSocket = require('ws'); const ws = new WebSocket('ws://localhost:8000/mcp/ws'); process.stdin.on('data', (data) => { ws.send(data); }); ws.on('message', (data) => { process.stdout.write(data); });"
      ],
      "env": {},
      "cwd": "",
      "timeout": 30000
    }
  }
}
```

## Резюме

Основные причины проблемы:
1. **Конфликт конфигураций** между Cursor и VS Code
2. **Автоматическое обнаружение MCP** в VS Code
3. **Разные пути** к конфигурационным файлам

Решение:
1. Отключите `mcp.discovery.enabled`
2. Создайте отдельный `mcp.json` для VS Code
3. Перезапустите VS Code
4. Проверьте подключение

После этих действий MCP сервер должен работать в обеих средах независимо! 🎉
