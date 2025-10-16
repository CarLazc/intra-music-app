import os
from flask import Flask, session, redirect, url_for, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv() # Carga variables de .env si existe (para desarrollo local)

app = Flask(__name__)
#app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
#db=SQLAlchemy(app)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
CORS(app, supports_credentials=True, origins=["https://intramusic.netlify.app"])

#Implementacion de base de datos en proceso
#Su finalizacion y uso aun se encuentra en consideracion

#class Usuario(db.Model):
 #   id = db.column(db.Integer, primary_key=True)
  #  display_name = db.column(db.String(50))

#class Artista_por_usuario(db.Model):
 #   id = db.column(db.Integer, primary_key=True)
  #  Usuario.id = db.column(db.Integer, db.ForeignKey('usuario.id'))
   # nombre_artista = db.column(dv.String(50))
    #id_artista = db.column(db.String(62))


client_id = os.environ.get('SPOTIPY_CLIENT_ID')
client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
FRONTEND_URL = os.environ.get('FRONTEND_URL') 
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

@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(FRONTEND_URL)

@app.route('/api/top-artists')
def get_top_artists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    time_range_elegido = request.args.get('time_range', 'long_term')
    if time_range_elegido not in ['short_term', 'medium_term', 'long_term']:
        return jsonify({'error': 'Invalid time_range parameter'}), 400
    top_artists = sp.current_user_top_artists(limit=3, time_range=time_range_elegido)
    artists_data = []
    for i, artist in enumerate(top_artists['items']):
        image_url = artist['images'][0]['url'] if artist['images'] else "https://placehold.co/208x208/7c3aed/ffffff?text=Artist"
        shape = "rounded-full" #if i == 1 else "rounded-3xl"
        artists_data.append({
            'name': artist['name'],
            'imageUrl': image_url,
            'shape': shape,
            'description': f"Genero: {artist['genres'][0] if artist['genres'] else 'Indefinido'}"
        })
    return jsonify(artists_data)

@app.route('/api/top-tracks')
def get_top_tracks():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    time_range_elegido = request.args.get('time_range', 'long_term')
    if time_range_elegido not in ['short_term', 'medium_term', 'long_term']:
        return jsonify({'error': 'Invalid time_range parameter'}), 400
    top_tracks = sp.current_user_top_tracks(limit=10, time_range=time_range_elegido)
    tracks_data = []
    for track in top_tracks['items']:
        tracks_data.append({
            'name': track['name'],
            'artist': track['artists'][0]['name']
        })
    return jsonify(tracks_data)

@app.route('/api/recently-played')
def get_recently_played():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    recently_played = sp.current_user_recently_played(limit=10)
    played_data = []
    for item in recently_played['items']:
        track = item['track']
        played_data.append({
            'name': track['name'],
            'artist': track['artists'][0]['name']
        })
    return jsonify(played_data) 

@app.route('/debug-config')
def debug_config():
    config_data = {
        "SECRET_KEY_EXISTS": 'SECRET_KEY' in os.environ and bool(os.environ.get('SECRET_KEY')),
        "SPOTIPY_CLIENT_ID_EXISTS": 'SPOTIPY_CLIENT_ID' in os.environ,
        "SPOTIPY_CLIENT_SECRET_EXISTS": 'SPOTIPY_CLIENT_SECRET' in os.environ,
        "SPOTIPY_REDIRECT_URI_VALUE": os.environ.get('SPOTIPY_REDIRECT_URI'),
        "FRONTEND_URL_VALUE": os.environ.get('FRONTEND_URL'),
        "FLASK_CONFIG_SESSION_COOKIE_SAMESITE": app.config.get('SESSION_COOKIE_SAMESITE'),
        "FLASK_CONFIG_SESSION_COOKIE_SECURE": app.config.get('SESSION_COOKIE_SECURE')
    }
    return jsonify(config_data)

if __name__ == "__main__":
    app.run(debug=True, port=5000)