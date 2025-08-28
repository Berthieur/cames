import asyncio
import websockets
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Port assigné par Render (ou 8000 pour tests locaux)
PORT = int(os.getenv("PORT", 8000))

# Stockage des clients connectés
esp32_clients = set()  # Clients ESP32-CAM
android_clients = set()  # Clients Android

async def handle_client(websocket, path):
    """
    Gérer les connexions WebSocket des clients ESP32-CAM et Android.
    """
    # Identifier le type de client basé sur le chemin ou un message initial
    try:
        # Attendre un message initial pour identifier le client
        initial_message = await websocket.recv()
        if initial_message == "esp32-cam":
            logger.info("ESP32-CAM connecté")
            esp32_clients.add(websocket)
            try:
                async for message in websocket:
                    # Relayer les images de l'ESP32-CAM vers tous les clients Android
                    for client in android_clients:
                        if not client.closed:
                            try:
                                await client.send(message)
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi au client Android: {e}")
            except Exception as e:
                logger.error(f"Erreur avec l'ESP32-CAM: {e}")
            finally:
                esp32_clients.remove(websocket)
                logger.info("ESP32-CAM déconnecté")
        elif initial_message == "android-client":
            logger.info("Client Android connecté")
            android_clients.add(websocket)
            try:
                async for message in websocket:
                    # Relayer les commandes (ex. : start-stream, flash-on, flash-off) à l'ESP32-CAM
                    for esp32 in esp32_clients:
                        if not esp32.closed:
                            try:
                                await esp32.send(message)
                                logger.info(f"Commande envoyée à l'ESP32-CAM: {message}")
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi à l'ESP32-CAM: {e}")
                    # Envoyer un message d'erreur si aucun ESP32-CAM n'est connecté
                    if not esp32_clients:
                        error_message = '{"error": "Aucun ESP32-CAM connecté"}'
                        try:
                            await websocket.send(error_message)
                        except Exception as e:
                            logger.error(f"Erreur lors de l'envoi de l'erreur au client Android: {e}")
            except Exception as e:
                logger.error(f"Erreur avec le client Android: {e}")
            finally:
                android_clients.remove(websocket)
                logger.info("Client Android déconnecté")
        else:
            logger.warning(f"Client inconnu avec message initial: {initial_message}")
            await websocket.close()
    except Exception as e:
        logger.error(f"Erreur lors de l'identification du client: {e}")

async def main():
    """
    Démarrer le serveur WebSocket.
    """
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
