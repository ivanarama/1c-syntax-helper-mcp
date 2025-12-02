#!/usr/bin/env python3
"""
Простой HTTP MCP сервер для VS Code
Работает как прокси к основному серверу
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import threading
import time

class MCPProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обрабатывает POST запросы"""
        if self.path == '/mcp':
            try:
                # Читаем тело запроса
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Отправляем запрос на основной сервер
                req = urllib.request.Request(
                    'http://192.168.1.13:8002/mcp',
                    data=post_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = response.read()
                    
                    # Отправляем ответ
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(result)
                    
            except Exception as e:
                # Отправляем ошибку
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
                
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """Обрабатывает GET запросы"""
        if self.path == '/mcp':
            # Возвращаем информацию о сервере
            info = {
                "type": "mcp_proxy_info",
                "name": "1c-syntax-helper-proxy",
                "version": "1.0.0",
                "status": "running",
                "proxy_to": "http://192.168.1.13:8002/mcp",
                "message": "This is a proxy to the main MCP server"
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(info).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Отключаем логирование"""
        pass

def run_server(port=8003):
    """Запускает HTTP сервер"""
    server = HTTPServer(('localhost', port), MCPProxyHandler)
    print(f"MCP Proxy сервер запущен на порту {port}")
    print(f"URL: http://localhost:{port}/mcp")
    server.serve_forever()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
    run_server(port)
