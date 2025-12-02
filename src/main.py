"""Главное приложение MCP сервера синтаксис-помощника 1С."""

import json
import sys
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from src.core.config import settings
from src.core.logging import get_logger
from src.core.elasticsearch import es_client
from src.core.validation import ValidationError
from src.core.rate_limiter import get_rate_limiter, RateLimitExceeded
from src.core.metrics import get_metrics_collector, get_system_monitor
from src.core.dependency_injection import setup_dependencies
from src.parsers.hbk_parser import HBKParser, HBKParserError
from src.parsers.indexer import indexer
from src.models.mcp_models import (
    MCPRequest, MCPResponse, HealthResponse, 
    MCPToolsResponse, MCPTool, MCPToolParameter, MCPToolType,
    Find1CHelpRequest, GetSyntaxInfoRequest, GetQuickReferenceRequest,
    SearchByContextRequest, ListObjectMembersRequest
)
from src.handlers.mcp_handlers import (
    handle_find_1c_help, handle_get_syntax_info, handle_get_quick_reference,
    handle_search_by_context, handle_list_object_members
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger = get_logger(__name__)
    metrics = get_metrics_collector()
    monitor = get_system_monitor()
    
    logger.info("Запуск MCP сервера синтаксис-помощника 1С")
    
    # Настройка dependency injection
    setup_dependencies()
    
    # Запуск мониторинга системы
    await monitor.start_monitoring(interval=60)
    
    # Подключаемся к Elasticsearch
    connected = await es_client.connect()
    if not connected:
        logger.error("Не удалось подключиться к Elasticsearch")
        await metrics.increment("startup.elasticsearch.connection_failed")
    else:
        logger.info("Успешно подключились к Elasticsearch")
        await metrics.increment("startup.elasticsearch.connection_success")
        
        # Проверяем наличие .hbk файла и запускаем автоиндексацию в фоне,
        # чтобы не блокировать обработку HTTP запросов во время парсинга
        asyncio.create_task(auto_index_on_startup())
    
    await metrics.increment("startup.completed")
    
    yield
    
    # Shutdown
    logger.info("Остановка MCP сервера")
    await monitor.stop_monitoring()
    await es_client.disconnect()
    await metrics.increment("shutdown.completed")


async def auto_index_on_startup():
    """Автоматическая индексация при запуске, если найден .hbk файл."""
    try:
        from pathlib import Path
        
        # Ищем .hbk файлы в директории данных
        hbk_dir = Path(settings.data.hbk_directory)
        if not hbk_dir.exists():
            logger.warning(f"Директория .hbk файлов не найдена: {hbk_dir}")
            return
        
        hbk_files = list(hbk_dir.glob("*.hbk"))
        if not hbk_files:
            logger.info(f"Файлы .hbk не найдены в {hbk_dir}. Индексация будет выполнена при загрузке файла.")
            return
        
        # Проверяем, нужна ли индексация
        index_exists = await es_client.index_exists()
        docs_count = await es_client.get_documents_count() if index_exists else 0
        
        if index_exists and docs_count and docs_count > 0:
            logger.info(f"Индекс уже существует с {docs_count} документами. Пропускаем автоиндексацию.")
            return
        
        # Запускаем индексацию первого найденного файла
        hbk_file = hbk_files[0]
        logger.info(f"Запускаем автоматическую индексацию файла: {hbk_file}")
        
        success = await index_hbk_file(str(hbk_file))
        if success:
            logger.info("Автоматическая индексация завершена успешно")
        else:
            logger.error("Ошибка автоматической индексации")
            
    except Exception as e:
        logger.error(f"Ошибка при автоматической индексации: {e}")


async def index_hbk_file(file_path: str) -> bool:
    """Индексирует .hbk файл в Elasticsearch."""
    try:
        logger.info(f"Начинаем индексацию файла: {file_path}")
        
        # Парсим .hbk файл
        parser = HBKParser()
        parsed_hbk = parser.parse_file(file_path)
        
        if not parsed_hbk:
            logger.error("Ошибка парсинга .hbk файла")
            return False
        
        if not parsed_hbk.documentation:
            logger.warning("В файле не найдена документация для индексации")
            return False
        
        logger.info(f"Найдено {len(parsed_hbk.documentation)} документов для индексации")
        
        # Индексируем в Elasticsearch
        success = await indexer.reindex_all(parsed_hbk)
        
        if success:
            docs_count = await es_client.get_documents_count()
            logger.info(f"Индексация завершена. Документов в индексе: {docs_count}")
        
        return success
        
    except Exception as e:
        logger.error(f"Ошибка индексации файла {file_path}: {e}")
        return False


# Создаем приложение FastAPI
app = FastAPI(
    title="1C Syntax Helper MCP Server",
    description="MCP сервер для поиска по синтаксису 1С",
    version="1.0.0",
    lifespan=lifespan
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware для rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Middleware для ограничения скорости запросов."""
    rate_limiter = get_rate_limiter()
    metrics = get_metrics_collector()
    logger.info("rate_limit_middleware")
    # Получаем IP клиента
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Глобальный отладочный принт для любого запроса (для уверенности)
        try:
            print(f"[DEBUG] middleware start path={request.url.path} method={request.method}")
            try:
                sys.stdout.flush()
            except Exception:
                pass
        except Exception:
            pass
        # Временный консольный лог для диагностики проблемного 400 на /mcp
        if request.url.path == "/mcp":
            try:
                body_bytes = await request.body()
                body_preview = body_bytes.decode("utf-8", errors="replace")
                if len(body_preview) > 2000:
                    body_preview = body_preview[:2000] + "...<truncated>"
                print(f"[DEBUG]/mcp middleware ip={client_ip} ct={request.headers.get('content-type','')} cl={request.headers.get('content-length','')} body={body_preview}")
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
            except Exception as _e:
                print(f"[DEBUG]/mcp middleware failed to read body: {_e}")
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
        # Проверяем rate limit
        await rate_limiter.check_rate_limit(client_ip)
        
        # Измеряем время выполнения запроса
        start_time = time.time()
        response = await call_next(request)
        response_time = time.time() - start_time
        
        # Записываем метрики
        await metrics.record_timer("request.duration", response_time, 
                                 {"method": request.method, "path": request.url.path})
        await metrics.update_performance_stats(
            success=200 <= response.status_code < 400,
            response_time=response_time
        )
        
        return response
        
    except RateLimitExceeded as e:
        await metrics.increment("requests.rate_limited", labels={"client_ip": client_ip})
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": str(e),
                "retry_after": e.retry_after
            },
            headers={"Retry-After": str(e.retry_after)}
        )
    except Exception as e:
        await metrics.increment("requests.middleware_error")
        logger.error(f"Error in rate limit middleware: {e}")
        
        response = await call_next(request)
        return response


# Обработчик глобальных исключений
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Обработчик ошибок валидации."""
    metrics = get_metrics_collector()
    await metrics.increment("errors.validation")
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation error",
            "message": str(exc)
        }
    )


@app.exception_handler(HBKParserError)
async def parser_exception_handler(request: Request, exc: HBKParserError):
    """Обработчик ошибок парсера."""
    metrics = get_metrics_collector()
    await metrics.increment("errors.parser")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Parser error", 
            "message": str(exc)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Общий обработчик исключений."""
    metrics = get_metrics_collector()
    await metrics.increment("errors.general")
    
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Логируем любые HTTP ошибки (включая 400), возникающие до/вне наших обработчиков."""
    logger.error(f"HTTPException {exc.status_code} at {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": str(exc.detail) if exc.detail else "HTTP error"
            }
        }
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("health_check")
    """Проверка состояния системы.

    Важно: не считаем сервер «нездоровым», если недоступен Elasticsearch.
    Это позволяет клиентам (например, Cursor) успешно проходить проверку
    работоспособности MCP сервера даже без внешних зависимостей.
    """
    metrics = get_metrics_collector()
    
    async with metrics.timer("health_check.duration"):
        # Не инициируем подключение к Elasticsearch в health-check, только проверяем текущее состояние
        es_connected = await es_client.is_connected()
        index_exists_response = await es_client.index_exists() if es_connected else False
        index_exists = bool(index_exists_response) if index_exists_response else False
        docs_count = await es_client.get_documents_count() if index_exists else None
    
    await metrics.increment("health_check.requests")
    
    return HealthResponse(
        status="healthy",  # сервер доступен и готов принимать MCP-запросы
        elasticsearch=es_connected,
        index_exists=index_exists,
        documents_count=docs_count
    )
@app.get("/")
async def root(request: Request) -> JSONResponse:
    return JSONResponse({"message": "MCP 1C Metadata Server запущен"})

@app.get("/index/status")
async def index_status():
    """Статус индексации."""
    es_connected = await es_client.is_connected()
    index_exists_response = await es_client.index_exists() if es_connected else False
    index_exists = bool(index_exists_response) if index_exists_response else False
    docs_count = await es_client.get_documents_count() if index_exists else 0
    
    return {
        "elasticsearch_connected": es_connected,
        "index_exists": index_exists,
        "documents_count": docs_count,
        "index_name": settings.elasticsearch.index_name
    }


@app.post("/index/rebuild")
async def rebuild_index():
    """Переиндексация документации из .hbk файла."""
    try:
        from pathlib import Path
        
        # Проверяем подключение к Elasticsearch
        if not await es_client.is_connected():
            raise HTTPException(
                status_code=503,
                detail="Elasticsearch недоступен"
            )
        
        # Ищем .hbk файлы
        hbk_dir = Path(settings.data.hbk_directory)
        if not hbk_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Директория .hbk файлов не найдена: {hbk_dir}"
            )
        
        hbk_files = list(hbk_dir.glob("*.hbk"))
        if not hbk_files:
            raise HTTPException(
                status_code=400,
                detail=f"Файлы .hbk не найдены в {hbk_dir}"
            )
        
        # Индексируем первый найденный файл
        hbk_file = hbk_files[0]
        logger.info(f"Начинаем переиндексацию файла: {hbk_file}")
        
        success = await index_hbk_file(str(hbk_file))
        
        if success:
            docs_count = await es_client.get_documents_count()
            return {
                "status": "success",
                "message": "Переиндексация завершена успешно",
                "file": str(hbk_file),
                "documents_count": docs_count
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Ошибка переиндексации"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка переиндексации: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка: {str(e)}"
        )


@app.get("/mcp/tools", response_model=MCPToolsResponse)
async def get_mcp_tools():
    logger.info("get_mcp_tools")
    """Возвращает список доступных MCP инструментов."""
    tools = [
        MCPTool(
            name=MCPToolType.FIND_1C_HELP,
            description="Универсальный поиск справки по любому элементу 1С",
            parameters=[
                MCPToolParameter(
                    name="query",
                    type="string",
                    description="Поисковый запрос (имя элемента, описание, ключевые слова)",
                    required=True
                ),
                MCPToolParameter(
                    name="limit",
                    type="number",
                    description="Максимальное количество результатов (по умолчанию: 10)",
                    required=False
                )
            ]
        ),
        MCPTool(
            name=MCPToolType.GET_SYNTAX_INFO,
            description="Получить полную техническую информацию об элементе с синтаксисом и параметрами",
            parameters=[
                MCPToolParameter(
                    name="element_name",
                    type="string",
                    description="Имя элемента (функции, метода, свойства)",
                    required=True
                ),
                MCPToolParameter(
                    name="object_name",
                    type="string",
                    description="Имя объекта (для методов объектов)",
                    required=False
                ),
                MCPToolParameter(
                    name="include_examples",
                    type="boolean",
                    description="Включить примеры использования",
                    required=False
                )
            ]
        ),
        MCPTool(
            name=MCPToolType.GET_QUICK_REFERENCE,
            description="Получить краткую справку об элементе (только синтаксис и описание)",
            parameters=[
                MCPToolParameter(
                    name="element_name",
                    type="string",
                    description="Имя элемента",
                    required=True
                ),
                MCPToolParameter(
                    name="object_name",
                    type="string",
                    description="Имя объекта (необязательно)",
                    required=False
                )
            ]
        ),
        MCPTool(
            name=MCPToolType.SEARCH_BY_CONTEXT,
            description="Поиск элементов с фильтром по контексту (глобальные функции или методы объектов)",
            parameters=[
                MCPToolParameter(
                    name="query",
                    type="string",
                    description="Поисковый запрос",
                    required=True
                ),
                MCPToolParameter(
                    name="context",
                    type="string",
                    description="Контекст поиска: global, object, all",
                    required=True
                ),
                MCPToolParameter(
                    name="object_name",
                    type="string",
                    description="Фильтр по конкретному объекту (для context=object)",
                    required=False
                ),
                MCPToolParameter(
                    name="limit",
                    type="number",
                    description="Максимальное количество результатов",
                    required=False
                )
            ]
        ),
        MCPTool(
            name=MCPToolType.LIST_OBJECT_MEMBERS,
            description="Получить список всех элементов объекта (методы, свойства, события)",
            parameters=[
                MCPToolParameter(
                    name="object_name",
                    type="string",
                    description="Имя объекта 1С",
                    required=True
                ),
                MCPToolParameter(
                    name="member_type",
                    type="string",
                    description="Тип элементов: all, methods, properties, events",
                    required=False
                ),
                MCPToolParameter(
                    name="limit",
                    type="number",
                    description="Максимальное количество результатов",
                    required=False
                )
            ]
        )
    ]
    
    return MCPToolsResponse(tools=tools)


@app.get("/mcp")
async def mcp_sse_endpoint():
    """MCP Server-Sent Events endpoint - поддержка SSE для MCP протокола."""
    from fastapi.responses import StreamingResponse
    
    logger.info("mcp_sse_endpoint - запуск SSE соединения")
    
    async def sse_event_stream():
        """Генератор SSE событий для MCP протокола"""
        import uuid
        import queue
        import threading
        
        # Генерируем уникальный session_id
        session_id = str(uuid.uuid4())
        
        # Создаем очередь для сообщений
        message_queue = asyncio.Queue()
        
        # Сохраняем очередь в глобальном хранилище сессий
        if not hasattr(app.state, 'sse_sessions'):
            app.state.sse_sessions = {}
        app.state.sse_sessions[session_id] = message_queue
        
        try:
            # Отправляем endpoint для сообщений (как первый сервер)
            yield f"event: endpoint\n"
            yield f"data: /mcp?session_id={session_id}\n\n"
            
            # Держим соединение открытым и отправляем сообщения из очереди
            while True:
                try:
                    # Ждем сообщение из очереди с таймаутом
                    message = await asyncio.wait_for(message_queue.get(), timeout=30.0)
                    
                    # Отправляем сообщение через SSE
                    yield f"event: message\n"
                    yield f"data: {json.dumps(message)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Отправляем ping каждые 30 секунд при отсутствии сообщений
                    yield f"event: ping\n"
                    yield f"data: {json.dumps({'timestamp': int(time.time())})}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"SSE соединение закрыто для session {session_id}")
            # Удаляем сессию из хранилища
            if hasattr(app.state, 'sse_sessions') and session_id in app.state.sse_sessions:
                del app.state.sse_sessions[session_id]
            raise
    
    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/mcp")
async def mcp_sse_or_jsonrpc_endpoint(request: Request):
    """Endpoint для обработки сообщений - поддерживает SSE и обычный JSON-RPC."""
    import json
    from fastapi.responses import JSONResponse
    
    try:
        # Проверяем, есть ли session_id (SSE режим)
        session_id = request.query_params.get("session_id")
        
        # Читаем JSON-RPC запрос
        data = await request.json()
        logger.info(f"Получен запрос{' для session ' + session_id if session_id else ''}: {data.get('method', 'unknown') if isinstance(data, dict) else 'batch'}")
        
        # Обрабатываем запрос
        if isinstance(data, list):
            results = []
            for item in data:
                result = await process_single_jsonrpc_request(item)
                results.append(result)
            response_data = results
        else:
            response_data = await process_single_jsonrpc_request(data)
        
        # Если это SSE запрос, отправляем ответ через очередь
        if session_id and hasattr(app.state, 'sse_sessions') and session_id in app.state.sse_sessions:
            queue = app.state.sse_sessions[session_id]
            await queue.put(response_data)
            # Возвращаем подтверждение приема
            return JSONResponse(content={"status": "queued"})
        else:
            # Обычный JSON-RPC ответ
            return JSONResponse(content=response_data)
            
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return JSONResponse(status_code=500, content=error_response)


async def process_single_jsonrpc_request(data):
    """Обрабатывает одиночный JSON-RPC запрос (переиспользуется для SSE и POST)."""
    if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": data.get("id") if isinstance(data, dict) else None,
            "error": {"code": -32600, "message": "Invalid Request"}
        }

    method = data.get("method")
    params = data.get("params", {})
    request_id = data.get("id")
    
    # Обрабатываем initialize запрос
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    },
                    "resources": {},
                    "prompts": {},
                    "roots": {"listChanged": False},
                    "sampling": {}
                },
                "serverInfo": {
                    "name": "1c-syntax-helper-mcp",
                    "version": "1.0.0"
                }
            }
        }
    
    # Обрабатываем tools/list запрос
    elif method == "tools/list":
        tools_response = await get_mcp_tools()
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                param.name: {
                                    "type": param.type,
                                    "description": param.description
                                }
                                for param in tool.parameters
                            },
                            "required": [param.name for param in tool.parameters if param.required]
                        }
                    }
                    for tool in tools_response.tools
                ]
            }
        }
    
    # Обрабатываем tools/call запрос
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        from src.models.mcp_models import MCPRequest
        mcp_request = MCPRequest(tool=tool_name, arguments=arguments)
        result = await mcp_endpoint_handler(mcp_request)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": result.content if hasattr(result, 'content') else result,
                "isError": False
            }
        }
    
    # Обрабатываем другие стандартные методы MCP
    elif method in ["prompts/list", "prompts/get", "resources/list", "resources/read", "roots/list"]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {} if method == "prompts/list" else {"error": "Not implemented"}
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


async def mcp_endpoint_handler(request: MCPRequest):
    """Внутренний обработчик MCP запросов."""
    logger.info(f"Получен MCP запрос: {request.tool}")
    
    try:
        # Проверяем подключение к Elasticsearch
        if not await es_client.is_connected():
            raise HTTPException(
                status_code=503, 
                detail="Elasticsearch недоступен"
            )
        
        # Маршрутизируем запрос к новым обработчикам
        if request.tool == MCPToolType.FIND_1C_HELP:
            return await handle_find_1c_help(Find1CHelpRequest(**request.arguments))
        elif request.tool == MCPToolType.GET_SYNTAX_INFO:
            return await handle_get_syntax_info(GetSyntaxInfoRequest(**request.arguments))
        elif request.tool == MCPToolType.GET_QUICK_REFERENCE:
            return await handle_get_quick_reference(GetQuickReferenceRequest(**request.arguments))
        elif request.tool == MCPToolType.SEARCH_BY_CONTEXT:
            return await handle_search_by_context(SearchByContextRequest(**request.arguments))
        elif request.tool == MCPToolType.LIST_OBJECT_MEMBERS:
            return await handle_list_object_members(ListObjectMembersRequest(**request.arguments))
        else:
            return MCPResponse(content=[], error=f"Неизвестный инструмент: {request.tool}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки MCP запроса: {e}")
        return MCPResponse(content=[], error=str(e))
@app.websocket("/mcp/ws")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """MCP WebSocket endpoint для обработки MCP протокола через WebSocket."""
    logger.info("WebSocket connection initiated")
    
    await websocket.accept()
    
    try:
        # Отправляем начальное событие подключения
        await websocket.send_json({
            "type": "connection", 
            "status": "connected",
            "timestamp": int(time.time())
        })
        
        while True:
            try:
                # Получаем сообщение от клиента
                message = await websocket.receive_json()
                logger.info(f"Получено WebSocket сообщение: {json.dumps(message, ensure_ascii=False)}")
                
                # Обрабатываем JSON-RPC запрос
                response = await process_jsonrpc_message(message)
                
                # Отправляем ответ
                await websocket.send_json(response)
                
            except WebSocketDisconnect:
                logger.info("WebSocket клиент отключился")
                break
            except json.JSONDecodeError:
                # Отправляем ошибку парсинга JSON
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                await websocket.send_json(error_response)
            except Exception as e:
                logger.error(f"Ошибка в WebSocket обработчике: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id") if isinstance(message, dict) else None,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                }
                await websocket.send_json(error_response)
                
    except Exception as e:
        logger.error(f"Критическая ошибка WebSocket соединения: {e}")
    finally:
        logger.info("WebSocket соединение закрыто")


async def process_jsonrpc_message(data):
    """Обрабатывает JSON-RPC сообщение (переиспользует логику из HTTP endpoint)."""
    # Поддержка batch запросов JSON-RPC
    if isinstance(data, list):
        # Пустой массив — некорректный JSON-RPC запрос
        if len(data) == 0:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request"}
            }
        
        results = []
        for item in data:
            result = await process_single_jsonrpc_message(item)
            results.append(result)
        return results
    else:
        # Обычный одиночный запрос
        return await process_single_jsonrpc_message(data)


async def process_single_jsonrpc_message(data):
    """Обрабатывает одиночное JSON-RPC сообщение."""
    if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": data.get("id") if isinstance(data, dict) else None,
            "error": {"code": -32600, "message": "Invalid Request"}
        }

    method = data.get("method")
    params = data.get("params", {})
    request_id = data.get("id")
    
    # Обрабатываем initialize запрос
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    },
                    "resources": {},
                    "prompts": {},
                    "roots": {"listChanged": False},
                    "sampling": {}
                },
                "serverInfo": {
                    "name": "1c-syntax-helper-mcp",
                    "version": "1.0.0"
                }
            }
        }
    
    # Обрабатываем tools/list запрос
    elif method == "tools/list":
        tools_response = await get_mcp_tools()
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                param.name: {
                                    "type": param.type,
                                    "description": param.description
                                }
                                for param in tool.parameters
                            },
                            "required": [param.name for param in tool.parameters if param.required]
                        }
                    }
                    for tool in tools_response.tools
                ]
            }
        }
    
    # Обрабатываем prompts/list запрос
    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "prompts": []
            }
        }
    
    # Обрабатываем prompts/get запрос
    elif method == "prompts/get":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Prompt not found"}
        }
    
    # Обрабатываем notifications/initialized
    elif method == "notifications/initialized":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {}
        }
    
    # Обрабатываем resources/list
    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": []}
        }
    
    # Обрабатываем resources/read
    elif method == "resources/read":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32004, "message": "Resource not found"}
        }
    
    # Обрабатываем roots/list
    elif method == "roots/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"roots": []}
        }
    
    # Обрабатываем sampling/create
    elif method == "sampling/create":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Sampling not supported"}
        }
    
    # Обрабатываем sampling/complete
    elif method == "sampling/complete":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Sampling not supported"}
        }
    
    # Обрабатываем tools/call запрос
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Преобразуем в наш формат MCPRequest
        from src.models.mcp_models import MCPRequest
        mcp_request = MCPRequest(tool=tool_name, arguments=arguments)
        
        # Вызываем наш существующий обработчик
        result = await mcp_endpoint_handler(mcp_request)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": result.content if hasattr(result, 'content') else result,
                "isError": False
            }
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


@app.get("/metrics")
async def get_metrics():
    """Получение метрик системы."""
    metrics = get_metrics_collector()
    rate_limiter = get_rate_limiter()
    
    all_metrics = await metrics.get_all_metrics()
    performance_stats = metrics.performance_stats
    global_rate_stats = rate_limiter.get_global_stats()
    
    return {
        "metrics": all_metrics,
        "performance": {
            "total_requests": performance_stats.total_requests,
            "successful_requests": performance_stats.successful_requests,
            "failed_requests": performance_stats.failed_requests,
            "success_rate": (performance_stats.successful_requests / max(performance_stats.total_requests, 1)) * 100,
            "avg_response_time": performance_stats.avg_response_time,
            "max_response_time": performance_stats.max_response_time,
            "min_response_time": performance_stats.min_response_time if performance_stats.min_response_time != float('inf') else 0,
            "current_active_requests": performance_stats.current_active_requests
        },
        "rate_limiting": global_rate_stats
    }


@app.get("/metrics/{client_id}")
async def get_client_metrics(client_id: str):
    """Получение метрик для конкретного клиента."""
    rate_limiter = get_rate_limiter()
    client_stats = rate_limiter.get_client_stats(client_id)
    
    return {
        "client_id": client_id,
        "rate_limiting": client_stats
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.server.host,
        port=settings.server.port,
        log_level=settings.server.log_level.lower(),
        reload=settings.debug
    )
