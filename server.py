import asyncio
import websockets
import os
import logging
from logtail import LogtailHandler

# Configuration des logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Activer DEBUG pour plus de détails

# Configuration du gestionnaire Logtail
logtail_token = os.getenv("LOGTAIL_TOKEN", "")
if logtail_token:
    handler = LogtailHandler(source_token=logtail_token)
else:
    handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PORT = int(os.getenv("PORT", 10000))
esp32_clients = set()
android_clients = set()

async def handle_client(websocket, path):
    client_ip = websocket.remote_address[0]
    logger.info(f"Nouvelle connexion depuis {client_ip}, chemin: {path}")
    logger.debug(f"En-têtes WebSocket: {websocket.request_headers}")
    try:
        initial_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        logger.info(f"Message initial reçu de {client_ip}: {initial_message}")
        if initial_message == "esp32-cam":
            logger.info(f"ESP32-CAM connecté depuis {client_ip}")
            esp32_clients.add(websocket)
            try:
                async for message in websocket:
                    logger.info(f"Message reçu de l'ESP32-CAM ({client_ip}): {len(message)} octets")
                    for client in android_clients:
                        if not client.closed:
                            try:
                                await client.send(message)
                                logger.debug(f"Image envoyée au client Android: {client.remote_address[0]}")
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi au client Android {client.remote_address[0]}: {e}")
            except Exception as e:
                logger.error(f"Erreur avec l'ESP32-CAM ({client_ip}): {e}")
            finally:
                esp32_clients.remove(websocket)
                logger.info(f"ESP32-CAM déconnecté: {client_ip}")
        elif initial_message == "android-client":
            logger.info(f"Client Android connecté depuis {client_ip}")
            android_clients.add(websocket)
            try:
                async for message in websocket:
                    logger.info(f"Commande reçue du client Android ({client_ip}): {message}")
                    for esp32 in esp32_clients:
                        if not esp32.closed:
                            try:
                                await esp32.send(message)
                                logger.debug(f"Commande envoyée à l'ESP32-CAM: {esp32.remote_address[0]}")
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi à l'ESP32-CAM {esp32.remote_address[0]}: {e}")
                    if not esp32_clients:
                        error_message = '{"error": "Aucun ESP32-CAM connecté"}'
                        try:
                            await websocket.send(error_message)
                            logger.warning(f"Aucun ESP32-CAM connecté, erreur envoyée à {client_ip}")
                        except Exception as e:
                            logger.error(f"Erreur lors de l'envoi de l'erreur au client Android {client_ip}: {e}")
            except Exception as e:
                logger.error(f"Erreur avec le client Android ({client_ip}): {e}")
            finally:
                android_clients.remove(websocket)
                logger.info(f"Client Android déconnecté: {client_ip}")
        else:
            logger.warning(f"Client inconnu depuis {client_ip} avec message: {initial_message}")
            await websocket.close(code=1008, reason=f"Message initial non valide: {initial_message}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout: Aucun message initial reçu de {client_ip}")
        await websocket.close(code=1008, reason="Aucun message initial")
    except Exception as e:
        logger.error(f"Erreur lors de la gestion de la connexion ({client_ip}): {e}")
        await websocket.close(code=1000, reason="Erreur serveur")

async def main():
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
