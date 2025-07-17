import pandas as pd
from flask import Flask, redirect, request, jsonify
import requests
from surprise import SVD, Dataset, Reader
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
import numpy as np
from urllib.parse import urlencode
import os
from dotenv import load_dotenv
import time
import logging

from flask_cors import CORS
app = Flask(__name__)
CORS(app, resources={r"/login": {"origins": "http://localhost:5173"}, r"/callback": {"origins": "http://localhost:5173"}, r"/recommendations": {"origins": "http://localhost:5173"}})

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
from flask_cors import CORS
CORS(app, resources={r"/login": {"origins": "http://localhost:5173"}, r"/callback": {"origins": "http://localhost:5173"}, r"/recommendations": {"origins": "http://localhost:5173"}})  # Add CORS for all relevant routes
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REDIRECT_URI = "http://127.0.0.1:5000/callback"
SPOTIFY_API = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Initialize SQLite database
def init_db():
    try:
        conn = sqlite3.connect("music.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS songs (id TEXT PRIMARY KEY, name TEXT, artist TEXT, artist_id TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS user_playlists (user_id TEXT, song_id TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS genres (song_id TEXT, genre TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS user_history (user_id TEXT, song_id TEXT)")
        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {str(e)}")
    finally:
        conn.close()

init_db()

# Spotify authentication
@app.route("/login")
def login():
    try:
        if not CLIENT_ID or not CLIENT_SECRET:
            logger.error("Missing CLIENT_ID or CLIENT_SECRET in .env")
            return jsonify({"error": "Server configuration error", "details": "Missing credentials"}), 500

        scopes = "user-top-read playlist-read-private user-read-recently-played"
        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": scopes
        }
        auth_url = f"{AUTH_URL}?{urlencode(params)}"
        logger.info(f"Redirecting to Spotify authorization: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Login route failed: {str(e)}")
        return jsonify({"error": "Login initiation failed", "details": str(e)}), 500

@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            logger.error("No authorization code received in callback")
            return jsonify({"error": "No code provided"}), 400

        logger.info(f"Received authorization code: {code}")
        token_response = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})

        if token_response.status_code != 200:
            error_details = token_response.json()
            logger.error(f"Token request failed with status {token_response.status_code}: {error_details}")
            return jsonify({"error": "Failed to get access token", "details": error_details}), 400

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            logger.error("No access token received in token response")
            return jsonify({"error": "No access token received"}), 400

        logger.info(f"Successfully obtained access token: {access_token[:10]}...")  # Log first 10 chars for security
        return redirect(f"http://localhost:5173?access_token={access_token}")
    except requests.RequestException as e:
        logger.error(f"Network error in callback: {str(e)}")
        return jsonify({"error": "Network error", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"Callback route failed: {str(e)}")
        return jsonify({"error": "Callback processing failed", "details": str(e)}), 500
    
# Fetch playlists
def get_playlist_tracks(access_token, playlist_id, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        try:
            response = requests.get(f"{SPOTIFY_API}/playlists/{playlist_id}/tracks", headers=headers)
            if response.status_code == 429:
                time.sleep(2 ** i)
                continue
            if response.status_code != 200:
                logger.error(f"Failed to fetch playlist tracks: {response.status_code} - {response.text}")
                return []
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Playlist tracks request failed: {str(e)}")
            return []
    return []

# Fetch recently played tracks
def get_recently_played(access_token, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        try:
            response = requests.get(f"{SPOTIFY_API}/me/player/recently-played?limit=50", headers=headers)
            if response.status_code == 429:
                time.sleep(2 ** i)
                continue
            if response.status_code != 200:
                logger.error(f"Failed to fetch recently played tracks: {response.status_code} - {response.text}")
                return []
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Recently played request failed: {str(e)}")
            return []
    return []

# Fetch top tracks
def get_top_tracks(access_token, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        try:
            response = requests.get(f"{SPOTIFY_API}/me/top/tracks?time_range=long_term&limit=5", headers=headers)
            if response.status_code == 429:
                time.sleep(2 ** i)
                continue
            if response.status_code != 200:
                logger.error(f"Failed to fetch top tracks: {response.status_code} - {response.text}")
                return []
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Top tracks request failed: {str(e)}")
            return []
    return []

# Fetch artist genres
def get_artist_genres(artist_ids, access_token, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        try:
            response = requests.get(f"{SPOTIFY_API}/artists?ids={','.join(artist_ids)}", headers=headers)
            if response.status_code == 429:
                time.sleep(2 ** i)
                continue
            if response.status_code != 200:
                logger.error(f"Failed to fetch artist genres: {response.status_code} - {response.text}")
                return []
            return response.json().get("artists", [])
        except Exception as e:
            logger.error(f"Artist genres request failed: {str(e)}")
            return []
    return []

# Store playlist, history, and genres
def store_user_data(access_token, user_id):
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        print("Fetching top tracks...")
        top_tracks_response = requests.get(
            "https://api.spotify.com/v1/me/top/tracks?limit=20",
            headers=headers
        )
        top_tracks_data = top_tracks_response.json()
        print("Top tracks fetched.")

        conn = sqlite3.connect("music.db")
        cursor = conn.cursor()

        for track in top_tracks_data.get("items", []):
            song_id = track["id"]
            song_name = track["name"]
            artist = track["artists"][0]["name"]
            genre = "unknown"

            print(f"Inserting song: {song_name} by {artist}")

            cursor.execute("INSERT OR IGNORE INTO songs VALUES (?, ?, ?, ?)", (song_id, song_name, artist, genre))
            cursor.execute("INSERT INTO user_history VALUES (?, ?)", (user_id, song_id))

        conn.commit()
        conn.close()
        print("User data stored successfully.")
    except Exception as e:
        print(f"Error while storing user data: {e}")


# Collaborative filtering with Surprise
def recommend_songs_cf(user_id, num_recommendations=5):
    try:
        conn = sqlite3.connect("music.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, song_id, 1 as rating FROM user_playlists")
        data = pd.DataFrame(cursor.fetchall(), columns=["user", "item", "rating"])
        
        
        reader = Reader(rating_scale=(0, 1))
        dataset = Dataset.load_from_df(data, reader)
        trainset = dataset.build_full_trainset()
        model = SVD()
        model.fit(trainset)
        
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT song_id FROM songs WHERE song_id NOT IN (SELECT song_id FROM user_playlists WHERE user_id = ?)", (user_id,))
        song_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        predictions = [(song_id, model.predict(user_id, song_id).est) for song_id in song_ids]
        predictions.sort(key=lambda x: x[1], reverse=True)
        return [song_id for song_id, _ in predictions[:num_recommendations]]
    except Exception as e:
        logger.error(f"CF recommendation failed: {str(e)}")
        return []

# Genre-based content-based filtering
def recommend_songs_cbf(user_id, num_recommendations=5):
    try:
        conn = sqlite3.connect("music.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT genre FROM genres WHERE song_id IN (SELECT song_id FROM user_playlists WHERE user_id = ?)", (user_id,))
        user_genres = set(row[0] for row in cursor.fetchall())
        cursor.execute("SELECT DISTINCT genre FROM genres WHERE song_id IN (SELECT song_id FROM user_history WHERE user_id = ?)", (user_id,))
        user_genres.update(row[0] for row in cursor.fetchall())
        
        cursor.execute("SELECT DISTINCT song_id, genre FROM genres")
        song_genres = cursor.fetchall()
        conn.close()
        
        if not user_genres:
            return []
        
        all_genres = list(set(g for _, g in song_genres))
        song_vectors = {}
        for song_id in set(s for s, _ in song_genres):
            genres = [g for s, g in song_genres if s == song_id]
            vector = [1 if g in genres else 0 for g in all_genres]
            song_vectors[song_id] = vector
        
        user_vector = [1 if g in user_genres else 0 for g in all_genres]
        song_ids = list(song_vectors.keys())
        vectors = np.array([song_vectors[sid] for sid in song_ids])
        similarities = cosine_similarity([user_vector], vectors)[0]
        top_indices = similarities.argsort()[-num_recommendations:][::-1]
        return [song_ids[i] for i in top_indices]
    except Exception as e:
        logger.error(f"CBF recommendation failed: {str(e)}")
        return []

# Hybrid recommendations
def recommend_songs_hybrid(user_id, access_token, num_recommendations=5):
    try:
        cf_songs = recommend_songs_cf(user_id, num_recommendations * 2)
        cbf_songs = recommend_songs_cbf(user_id, num_recommendations * 2)
        combined_songs = list(set(cf_songs + cbf_songs))
        return combined_songs[:num_recommendations]
    except Exception as e:
        logger.error(f"Hybrid recommendation failed: {str(e)}")
        return []

# Get song details
def get_song_details(song_ids, access_token):
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{SPOTIFY_API}/tracks?ids={','.join(song_ids)}", headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch song details: {response.status_code} - {response.text}")
            return []
        return [{"id": song["id"], "name": song["name"], "artist": song["artists"][0]["name"]} for song in response.json().get("tracks", [])]
    except Exception as e:
        logger.error(f"Song details request failed: {str(e)}")
        return []

# Recommendations endpoint
@app.route("/recommendations")
def get_recommendations():
    try:
        access_token = request.args.get("access_token")
        user_id = request.args.get("user_id", "user123")
        rec_type = request.args.get("type", "hybrid")
        
        if not access_token:
            logger.error("No access token provided in recommendations request")
            return jsonify({"error": "No access token"}), 400

        store_user_data(user_id, access_token)
        
        if rec_type == "cf":
            recommended_song_ids = recommend_songs_cf(user_id)
        elif rec_type == "cbf":
            recommended_song_ids = recommend_songs_cbf(user_id)
        else:
            recommended_song_ids = recommend_songs_hybrid(user_id, access_token)
        
        recommendations = get_song_details(recommended_song_ids, access_token)
        logger.info(f"Recommendations fetched successfully for user {user_id}")
        return jsonify(recommendations)
    except Exception as e:
        logger.error(f"Recommendations route failed: {str(e)}")
        return jsonify({"error": "Failed to get recommendations", "details": str(e)}), 500

@app.route("/store_data")
def store_data():
    access_token = request.args.get("access_token")
    user_id = request.args.get("user_id", "user123")

    if not access_token:
        return jsonify({"error": "Missing access_token"}), 400

    store_user_data(access_token, user_id)
    return jsonify({"message": "User data stored."})

if __name__ == "__main__":
    app.run(debug=True)