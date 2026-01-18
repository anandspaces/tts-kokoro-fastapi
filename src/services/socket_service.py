import socketio
import asyncio

class SocketManager:
    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
        self.app = socketio.ASGIApp(self.sio)
        self.setup_handlers()

    def setup_handlers(self):
        @self.sio.event
        async def connect(sid, environ):
            print(f"Socket Client connected: {sid}")
            await self.sio.emit('status', {'msg': 'Connected to TTS Server'}, to=sid)

        @self.sio.event
        async def disconnect(sid):
            print(f"Socket Client disconnected: {sid}")
            
        @self.sio.on('ping')
        async def on_ping(sid, data):
            print(f"Ping from {sid}: {data}")
            await self.sio.emit('pong', {'data': data}, to=sid)

    async def emit_progress(self, message: str, percent: int = 0):
        """Emit a progress update to all clients (broadcast)"""
        await self.sio.emit('progress', {'message': message, 'percent': percent})

    async def emit_status(self, status: str, details: dict = None):
        """Emit a status update"""
        payload = {'status': status}
        if details:
            payload.update(details)
        await self.sio.emit('status', payload)

# Global instance
socket_manager = SocketManager()
