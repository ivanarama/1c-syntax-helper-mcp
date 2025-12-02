#!/usr/bin/env python3
"""
Локальный MCP сервер для VS Code
Запускается как процесс и общается через stdin/stdout
"""
import sys
import json
import asyncio
import urllib.request
import urllib.parse
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalMCPServer:
    def __init__(self):
        self.server_url = "http://192.168.1.13:8002/mcp"
        
    async def handle_request(self, request):
        """Обрабатывает JSON-RPC запрос"""
        try:
            # Отправляем запрос на удаленный сервер
            req = urllib.request.Request(
                self.server_url,
                data=json.dumps(request).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
                
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def run(self):
        """Основной цикл сервера"""
        logger.info("Локальный MCP сервер запущен")
        
        while True:
            try:
                # Читаем запрос из stdin
                line = sys.stdin.readline()
                if not line:
                    break
                    
                request = json.loads(line.strip())
                logger.info(f"Получен запрос: {request.get('method', 'unknown')}")
                
                # Обрабатываем запрос
                response = await self.handle_request(request)
                
                # Отправляем ответ в stdout
                print(json.dumps(response))
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                print(json.dumps(error_response))
                sys.stdout.flush()
                
            except Exception as e:
                logger.error(f"Неожиданная ошибка: {e}")
                break

async def main():
    server = LocalMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
