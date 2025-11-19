import os
from flask import Flask, session, redirect, url_for, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime
import time

# Import para la db
from config import Config
from extensions import db
from models import *

load_dotenv()

app = Flask(__name__)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

CORS(app, supports_credentials=True, origins=[
    "https://intramusic.netlify.app",  # Servidor produccion (Usable si se tienen creditos en netfly)
    "http://127.0.0.1:5500"           # Servidor local (No esta disponible netfly por creditos)
])

# Configuraciones de la db
app.config.from_object(Config)
db.init_app(app)
with app.app_context():
    db.create_all()

# Definicion de variables de entorno
client_id = os.environ.get('SPOTIPY_CLIENT_ID')
client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
FRONTEND_URL = os.environ.get('FRONTEND_URL') 
redirect_uri = os.environ.get('SPOTIPY_REDIRECT_URI') 
scope = "user-read-recently-played user-top-read user-read-private"

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

# Ruta principal que redirige a inicio de sesion en Spotify
@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Ruta para cerrar sesión
@app.route('/api/logout', methods=['POST'])
def logout():
    try:
        session.clear()
        print("Sesión cerrada para el usuario.")
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        print(f"Error durante el cierre de sesión: {e}")
        return jsonify({'error': 'Failed to log out'}), 500

# Ruta para ingreso de sesion y guardado de los datos en la db
@app.route('/callback')
def callback():
    try:
        sp_oauth.get_access_token(request.args['code'])
        user_profile = sp.current_user()
        user_id = user_profile['id']
        session['user_id'] = user_id
        user_name = user_profile['display_name']
        image_url = user_profile['images'][0]['url'] if user_profile['images'] else "https://placehold.co/300x300/7c3aed/ffffff?text=User"
        product = user_profile.get('product', 'unknown').capitalize()
        usuario_existente = User.query.get(user_id)
        if not usuario_existente:
            nuevo_usuario = User(
                id=user_id,
                username=user_name,
                image_url=image_url,
                product=product
            )
            db.session.add(nuevo_usuario)
            print(f"Nuevo usuario {user_name} guardado.")
        else:
            update_needed = False
            if usuario_existente.username != user_name:
                usuario_existente.username = user_name
                update_needed = True
            if usuario_existente.image_url != image_url:
                usuario_existente.image_url = image_url
                update_needed = True
            if usuario_existente.product != product:
                usuario_existente.product = product
                update_needed = True 
            if update_needed:
                print(f"Datos del usuario {user_name} actualizados.")
        db.session.commit() 
    except Exception as e:
        db.session.rollback()
        print(f"Error en el callback de autenticación: {e}")
        return redirect(FRONTEND_URL + '?error=auth_failed') 
    cache_buster = str(int(time.time()))
    return redirect(FRONTEND_URL + '?auth=success&v=' + cache_buster)

# Ruta para obtener los artistas mas escuchados
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
        shape = "rounded-full"
        artists_data.append({
            'name': artist['name'],
            'imageUrl': image_url,
            'shape': shape,
            'description': f"Genero: {artist['genres'][0] if artist['genres'] else 'Indefinido'}"
        })
    return jsonify(artists_data)

# Ruta para obtener las canciones mas escuchadas
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
        image_url = track['album']['images'][0]['url'] if track['album']['images'] else "https://placehold.co/300x300/7c3aed/ffffff?text=Track"
        tracks_data.append({
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'imageUrl': image_url 
        })
    return jsonify(tracks_data)

# Ruta para obtener las canciones recientemente reproducidas
@app.route('/api/recently-played')
def get_recently_played():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User session not found'}), 401
    try: 
        recently_played = sp.current_user_recently_played(limit=50)
        nuevas_canciones = 0
        for item in recently_played['items']:
            track = item['track']
            fecha_escucha_dt = datetime.strptime(item['played_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
            existe = Canciones_Escuchadas.query.filter_by(
                idUsuario = user_id,
                fechaEscucha = fecha_escucha_dt
            ).first()
            if not existe:
                duracion_segundos = 0 
                if track and 'duration_ms' in track:
                    duracion_segundos = track['duration_ms'] // 1000 # Convertir ms a minutos
                nueva_cancion = Canciones_Escuchadas(
                    idUsuario = user_id,
                    cancion = track['name'],
                    artista = track['artists'][0]['name'],
                    fechaEscucha = fecha_escucha_dt,
                    duracionSegundos = duracion_segundos  
                    )
                db.session.add(nueva_cancion)
                nuevas_canciones += 1  
        if nuevas_canciones > 0:
            db.session.commit()
            print(f"Agregadas {nuevas_canciones} nuevas canciones (con duración) a la DB.")
        historial_local = Canciones_Escuchadas.query.filter_by(idUsuario=user_id).order_by(Canciones_Escuchadas.fechaEscucha.desc()).limit(10).all()
        played_data = []
        for cancion_db in historial_local:
            played_data.append({
                'name': cancion_db.cancion,
                'artist': cancion_db.artista
            })
        return jsonify(played_data)
    except Exception as e:
        db.session.rollback()
        print(f"Error en get_recently_played: {e}") 
        return jsonify({'error': 'Failed to process recently played tracks'}), 500

# Ruta para obtener minutos escuchados por el usuario 
@app.route('/api/listening-minutes')
def get_listening_minutes():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User session not found'}), 401
    try:
        total_segundos = db.session.query(db.func.sum(Canciones_Escuchadas.duracionSegundos)).filter_by(idUsuario=user_id).scalar()
        if total_segundos is None:
            total_segundos = 0
        total_minutos_decimal = total_segundos / 60.0
        return jsonify({'totalMinutes': total_minutos_decimal})
    except Exception as e:
        db.session.rollback()
        print(f"Error en get_listening_minutes: {e}")
        return jsonify({'error': 'Failed to calculate listening minutes'}), 500

# Ruta para obtener datos del perfil del usuario
@app.route('/api/user-profile')
def get_user_profile():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    # Nueva forma de obtener datos del usuario, desde la base de datos
    # Evita llamadas constantes a la API
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authorization required'}, 401)
    try: 
        usuario = User.query.get(user_id)
        if not usuario:
            return jsonify({'error': 'User not found in database'}), 404
        profile_data = {
            'name': usuario.username,
            'imageUrl': usuario.image_url,
            'product': usuario.product
        }
        return jsonify(profile_data)
    except Exception as e:
        print(f"Error al consultar el perfil de usuario en la DB: {e}")
        return jsonify({'error': 'Database error'}), 500

    # Forma antigua de obtener datos del usuario
    # No eliminar el codigo por si ocurre un fallo con la db en la entrega final
    #user_profile = sp.current_user()
    #profile_data = {
    #    'name': user_profile.get('display_name'),
    #    'imageUrl': user_profile['images'][0]['url'] if user_profile['images'] else "https://placehold.co/300x300/7c3aed/ffffff?text=User",
    #    'product': user_profile.get('product').capitalize()
    #}
    #return jsonify(profile_data)

# Ruta para obtener los generos mas escuchados
@app.route('/api/top-genres')
def get_top_genres():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    try:
        top_artists = sp.current_user_top_artists(limit=50, time_range='medium_term')
        if not top_artists['items']:
            return jsonify([])
        all_genres = []
        for artist in top_artists['items']:
            all_genres.extend(artist['genres'])
        if not all_genres:
            return jsonify([]) 
        genre_counts = Counter(all_genres)
        formatted_genres = [{'genre': genre, 'count': count} for genre, count in genre_counts.most_common(10)]
        return jsonify(formatted_genres)
    except Exception as e:
        print(f"Error en get_top_genres: {e}")
        return jsonify({'error': 'Failed to get top genres'}), 500

# Ruta para obtener una recomendacion de genero
@app.route('/api/genre-recommendation')
def get_genre_recommendation():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User session not found'}), 401
    token_info = sp_oauth.get_cached_token()
    if not token_info or 'access_token' not in token_info:
        return jsonify({'error': 'Token no encontrado en caché'}), 401
    sp_local = spotipy.Spotify(auth=token_info['access_token'])
    try:
        top_artists_result = sp_local.current_user_top_artists(limit=50, time_range='medium_term')
        if not top_artists_result.get('items'):
            return jsonify({'error': 'No se encontraron artistas top.'}), 404
        all_artists = top_artists_result['items']
        all_genres_list = []
        top_artist_name_set = set() 
        for artist in all_artists:
            all_genres_list.extend(artist['genres'])
            top_artist_name_set.add(artist['name'].lower())
        if not all_genres_list:
            return jsonify({'error': 'No se encontraron géneros.'}), 404
        genre_counts = Counter(all_genres_list)
        try:
            recent_artists_db = db.session.query(Canciones_Escuchadas.artista).filter_by(idUsuario=user_id).distinct().all()
            recent_artist_name_set = {name[0].lower() for name in recent_artists_db}
        except Exception as e:
            print(f"Error consultando artistas recientes de la DB: {e}")
            recent_artist_name_set = set() 
        known_artist_name_set = top_artist_name_set.union(recent_artist_name_set)
        mainstream_genres = set([genre for genre, count in genre_counts.most_common(5)])
        fringe_genres = {genre: count for genre, count in genre_counts.items() if genre not in mainstream_genres}
        if not fringe_genres:
            fringe_genres_list = [item for item in genre_counts.most_common(10) if item[0] not in mainstream_genres]
            if not fringe_genres_list:
                 return jsonify({'error': 'No se pudo encontrar un género para recomendar.'}), 404
            fringe_genres = dict(fringe_genres_list)
        sorted_fringe_genres = sorted(fringe_genres.items(), key=lambda item: item[1], reverse=True)
        
        recommended_genre = None
        if sorted_fringe_genres:
            recommended_genre = sorted_fringe_genres[0][0]
        else:
             return jsonify({'error': 'No se pudo encontrar un género nicho.'}), 404
        print(f"Buscando artistas nuevos para el género: {recommended_genre}")
        search_results = sp_local.search(q=f'genre:"{recommended_genre}"', type='artist', limit=10)
        if not search_results or not search_results['artists']['items']:
            return jsonify({'error': 'No se encontraron artistas para ese género.'}), 404
        new_artist_to_recommend = None
        for artist in search_results['artists']['items']:
            if artist['name'].lower() not in known_artist_name_set: 
                new_artist_to_recommend = artist
                break
        if not new_artist_to_recommend:
            print("El usuario ya conoce a los 10 artistas top del género, recomendando el #1.")
            new_artist_to_recommend = search_results['artists']['items'][0]
        based_on_name = genre_counts.most_common(1)[0][0].capitalize()
        based_on_name_to_send = based_on_name 
        connection_artist = next((artist for artist in all_artists 
                                  if recommended_genre.lower() in artist['genres']), None)
        if connection_artist:
            based_on_name_to_send = connection_artist['name']
        image_url = new_artist_to_recommend['images'][0]['url'] if new_artist_to_recommend['images'] else "https://placehold.co/400x400/7c3aed/ffffff?text=Genre"
        return jsonify({
            'genre': recommended_genre.capitalize(),
            'artist': new_artist_to_recommend['name'],
            'imageUrl': image_url,
            'basedOn': based_on_name_to_send 
        })
            
    except Exception as e:
        print(f"Error en /api/genre-recommendation (logic v8-full-check): {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

# Ruta para eliminar los datos del usuario
@app.route('/api/delete-my-data', methods=['POST'])
def delete_user_data():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return jsonify({'error': 'Authorization required'}), 401
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User session not found'}), 401
    try:
        Canciones_Escuchadas.query.filter_by(idUsuario=user_id).delete()
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        session.clear()
        return jsonify({'message': 'User data deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al eliminar datos del usuario: {e}")
        return jsonify({'error': 'Failed to delete user data'}), 500
    
# Ruta para verificar configuraciones
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

# Ejecucion
if __name__ == "__main__":
    app.run(debug=True, port=5000)