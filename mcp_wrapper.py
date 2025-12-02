#!/usr/bin/env python3
"""
MCP Wrapper для VS Code
Пересылает JSON-RPC запросы на наш MCP сервер
"""
import sys
import json
import urllib.request
import urllib.parse

def main():
    try:
        # Читаем JSON-RPC запрос из stdin
        request_data = sys.stdin.read()
        
        # Создаем HTTP запрос
        req = urllib.request.Request(
            'http://192.168.1.13:8002/mcp',
            data=request_data.encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        # Отправляем запрос
        with urllib.request.urlopen(req, timeout=60) as response:
            result = response.read().decode('utf-8')
            print(result)
            
    except Exception as e:
        # Возвращаем ошибку в JSON-RPC формате
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        print(json.dumps(error_response))

if __name__ == "__main__":
    main()
