# Game10 Railway Backend

Deploy this folder's contents as the repository root.

- GET /health: health check
- POST /api/games: save a game; JSON body: {"name":"Demo","html":"<html>...</html>"}
- GET /games/{id}: open a saved game
- GET /api/games/{id}: read its record
- POST /api/builds: deliberately reports an error until a real Android build provider is integrated.

Set PUBLIC_BASE_URL to the deployed HTTPS URL.
Important: configure persistent storage for DATA_DIR on Railway, or saved games may be lost on redeploy.
This starter does not yet compile APKs.
