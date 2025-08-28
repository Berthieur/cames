import asyncio
import websockets
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL WebSocket de l'ESP32-CAM (update with your public IP and port)
ESP32_CAM_WS_URL = "ws://129.222.109.22:12345"  # Replace with your public IP and forwarded port
PORT = int(os.getenv("PORT", 8000))  # Render assigns PORT; default to 8000 for local testing

# Set to store connected Android clients
clients = set()

async def connect_to_esp32():
    """
    Connect to the ESP32-CAM WebSocket server and relay images to clients.
    """
    while True:
        try:
            async with websockets.connect(
                ESP32_CAM_WS_URL,
                timeout=10,
                ping_interval=10,
                ping_timeout=10
            ) as esp32_socket:
                logger.info(f"Connecté au WebSocket de l'ESP32-CAM: {ESP32_CAM_WS_URL}")
                async for message in esp32_socket:
                    # Relay images to all connected Android clients
                    for client in clients:
                        if not client.closed:
                            try:
                                await client.send(message)
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi au client: {e}")
        except Exception as e:
            logger.error(f"Erreur WebSocket ESP32-CAM: {e}, URL: {ESP32_CAM_WS_URL}")
            await asyncio.sleep(5)  # Wait before retrying

async def handle_client(websocket, path):
    """
    Handle incoming Android client connections and relay commands to ESP32-CAM.
    """
    logger.info("Nouveau client Android connecté")
    clients.add(websocket)
    try:
        async for message in websocket:
            # Relay commands (e.g., start-stream, flash-on, flash-off) to ESP32-CAM
            try:
                async with websockets.connect(
                    ESP32_CAM_WS_URL,
                    timeout=10,
                    ping_interval=10,
                    ping_timeout=10
                ) as esp32_socket:
                    await esp32_socket.send(message)
                    logger.info(f"Commande envoyée à l'ESP32-CAM: {message}")
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi de la commande à l'ESP32-CAM: {e}, URL: {ESP32_CAM_WS_URL}")
                error_message = f'{{"error": "ESP32-CAM non connecté: {str(e)}"}}'
                try:
                    await websocket.send(error_message)
                except Exception as e:
                    logger.error(f"Erreur lors de l'envoi de l'erreur au client: {e}")
    except Exception as e:
        logger.error(f"Erreur WebSocket client: {e}")
    finally:
        clients.remove(websocket)
        logger.info("Client Android déconnecté")

async def main():
    """
    Start the WebSocket server and the ESP32-CAM connection task.
    """
    # Start the task to connect to ESP32-CAM
    asyncio.create_task(connect_to_esp32())
    # Start the WebSocket server for Android clients
    try:
        server = await websockets.serve(handle_client, "0.0.0.0", PORT)
        logger.info(f"Serveur WebSocket démarré sur le port {PORT}")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du serveur WebSocket: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Serveur arrêté par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur principale du serveur: {e}")
