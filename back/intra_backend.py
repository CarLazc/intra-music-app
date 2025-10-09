# intra_backend.py (modificado)
import os
from flask import Flask, session, redirect, url_for, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from dotenv import load_dotenv # Opcional, para desarrollo local

load_dotenv() # Carga variables de .env si existe (para desarrollo local)

app = Flask(__name__)
# NUNCA dejes os.urandom en producción para la secret key.
# Génerala una vez y guárdala como variable de entorno.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') 
CORS(app, supports_credentials=True, origins=[os.environ.get('FRONTEND_URL')]) # Mayor seguridad

client_id = os.environ.get('SPOTIPY_CLIENT_ID')
client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
# La URL del frontend ahora viene del entorno
FRONTEND_URL = os.environ.get('FRONTEND_URL') 
# La URL de redirección debe coincidir con la de producción
redirect_uri = os.environ.get('SPOTIPY_REDIRECT_URI') 
scope = "user-read-recently-played user-top-read"

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)
sp = spotipy.Spotify(auth_manager=sp_oauth)

# ... (tus rutas @app.route se mantienen igual) ...
# ... (asegúrate que la ruta de callback use la variable FRONTEND_URL) ...
@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(FRONTEND_URL)

# La sección if __name__ == "__main__": no se ejecutará en producción.
# El servidor WSGI se encargará de correr la app.
if __name__ == "__main__":
    app.run(debug=True, port=5000)