import requests
import pandas as pd
from flask import Flask, redirect, request, jsonify
from surprise import SVD, Dataset, Reader
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
import numpy as np
from urllib.parse import urlencode
import os
from dotenv import load_dotenv
import time

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
CLIENT_ID = os.getenv("CLIENT_ID", "")  # Fallback to empty string if not set
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")  # Fallback to empty string if not set
REDIRECT_URI = "http://127.0.0.1:5000/callback"
SPOTIFY_API = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS songs (id TEXT PRIMARY KEY, name TEXT, artist TEXT, artist_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_playlists (user_id TEXT, song_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS genres (song_id TEXT, genre TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_history (user_id TEXT, song_id TEXT)")
    conn.commit()
    conn.close()

init_db()

# Spotify authentication
@app.route("/login")
def login():
    scopes = "user-top-read playlist-read-private user-read-recently-played"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": scopes
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No code provided"}), 400
    
    token_response = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    
    if token_response.status_code != 200:
        return jsonify({"error": "Failed to get access token", "details": token_response.json()}), 400
    
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    return jsonify({"access_token": access_token, "refresh_token": refresh_token})

# Fetch playlists
def get_playlist_tracks(access_token, playlist_id, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        response = requests.get(f"{SPOTIFY_API}/playlists/{playlist_id}/tracks", headers=headers)
        if response.status_code == 429:
            time.sleep(2 ** i)
            continue
        return response.json().get("items", [])
    return []

# Fetch recently played tracks
def get_recently_played(access_token, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        response = requests.get(f"{SPOTIFY_API}/me/player/recently-played?limit=50", headers=headers)
        if response.status_code == 429:
            time.sleep(2 ** i)
            continue
        return response.json().get("items", [])
    return []

# Fetch top tracks
def get_top_tracks(access_token, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        response = requests.get(f"{SPOTIFY_API}/me/top/tracks?time_range=long_term&limit=5", headers=headers)
        if response.status_code == 429:
            time.sleep(2 ** i)
            continue
        return response.json().get("items", [])
    return []

# Fetch artist genres
def get_artist_genres(artist_ids, access_token, retries=3):
    headers = {"Authorization": f"Bearer {access_token}"}
    for i in range(retries):
        response = requests.get(f"{SPOTIFY_API}/artists?ids={','.join(artist_ids)}", headers=headers)
        if response.status_code == 429:
            time.sleep(2 ** i)
            continue
        return response.json().get("artists", [])
    return []

# Store playlist, history, and genres
def store_user_data(user_id, access_token):
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    
    # Fetch and store playlists
    playlists = requests.get(f"{SPOTIFY_API}/me/playlists", headers={"Authorization": f"Bearer {access_token}"}).json().get("items", [])
    for playlist in playlists[:1]:  # Limit for simplicity
        tracks = get_playlist_tracks(access_token, playlist["id"])
        for track in tracks:
            track_data = track["track"]
            if track_data:
                cursor.execute("INSERT OR IGNORE INTO songs (id, name, artist, artist_id) VALUES (?, ?, ?, ?)",
                              (track_data["id"], track_data["name"], track_data["artists"][0]["name"], track_data["artists"][0]["id"]))
                cursor.execute("INSERT INTO user_playlists (user_id, song_id) VALUES (?, ?)", (user_id, track_data["id"]))
    
    # Fetch and store recently played tracks
    recently_played = get_recently_played(access_token)
    for item in recently_played:
        track_data = item["track"]
        if track_data:
            cursor.execute("INSERT OR IGNORE INTO songs (id, name, artist, artist_id) VALUES (?, ?, ?, ?)",
                          (track_data["id"], track_data["name"], track_data["artists"][0]["name"], track_data["artists"][0]["id"]))
            cursor.execute("INSERT INTO user_history (user_id, song_id) VALUES (?, ?)", (user_id, track_data["id"]))
    
    # Fetch and store top tracks
    top_tracks = get_top_tracks(access_token)
    for track in top_tracks:
        if track:
            cursor.execute("INSERT OR IGNORE INTO songs (id, name, artist, artist_id) VALUES (?, ?, ?, ?)",
                          (track["id"], track["name"], track["artists"][0]["name"], track["artists"][0]["id"]))
            cursor.execute("INSERT INTO user_history (user_id, song_id) VALUES (?, ?)", (user_id, track["id"]))
    
    # Fetch and store genres
    cursor.execute("SELECT DISTINCT artist_id FROM songs")
    artist_ids = [row[0] for row in cursor.fetchall()]
    for i in range(0, len(artist_ids), 50):  # API limit: 50 artists per request
        artists = get_artist_genres(artist_ids[i:i+50], access_token)
        for artist in artists:
            for genre in artist.get("genres", []):
                cursor.execute("SELECT song_id FROM songs WHERE artist_id = ?", (artist["id"],))
                song_ids = [row[0] for row in cursor.fetchall()]
                for song_id in song_ids:
                    cursor.execute("INSERT OR IGNORE INTO genres (song_id, genre) VALUES (?, ?)", (song_id, genre))
    
    conn.commit()
    conn.close()

# Collaborative filtering with Surprise
def recommend_songs_cf(user_id, num_recommendations=5):
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, song_id, 1 as rating FROM user_playlists")
    data = pd.DataFrame(cursor.fetchall(), columns=["user", "item", "rating"])
    conn.close()
    
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

# Genre-based content-based filtering
def recommend_songs_cbf(user_id, num_recommendations=5):
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    
    # Get user’s preferred genres from playlists, history, and top tracks
    cursor.execute("SELECT DISTINCT genre FROM genres WHERE song_id IN (SELECT song_id FROM user_playlists WHERE user_id = ?)", (user_id,))
    user_genres = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT DISTINCT genre FROM genres WHERE song_id IN (SELECT song_id FROM user_history WHERE user_id = ?)", (user_id,))
    user_genres.update(row[0] for row in cursor.fetchall())
    
    # Get all songs and their genres
    cursor.execute("SELECT DISTINCT song_id, genre FROM genres")
    song_genres = cursor.fetchall()
    conn.close()
    
    if not user_genres:
        return []
    
    # Build genre vectors
    all_genres = list(set(g for _, g in song_genres))
    song_vectors = {}
    for song_id in set(s for s, _ in song_genres):
        genres = [g for s, g in song_genres if s == song_id]
        vector = [1 if g in genres else 0 for g in all_genres]
        song_vectors[song_id] = vector
    
    # Build user genre vector
    user_vector = [1 if g in user_genres else 0 for g in all_genres]
    
    # Compute cosine similarity
    song_ids = list(song_vectors.keys())
    vectors = np.array([song_vectors[sid] for sid in song_ids])
    similarities = cosine_similarity([user_vector], vectors)[0]
    top_indices = similarities.argsort()[-num_recommendations:][::-1]
    return [song_ids[i] for i in top_indices]

# Hybrid recommendations
def recommend_songs_hybrid(user_id, access_token, num_recommendations=5):
    cf_songs = recommend_songs_cf(user_id, num_recommendations * 2)
    cbf_songs = recommend_songs_cbf(user_id, num_recommendations * 2)
    combined_songs = list(set(cf_songs + cbf_songs))
    return combined_songs[:num_recommendations]

# Get song details
def get_song_details(song_ids, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SPOTIFY_API}/tracks?ids={','.join(song_ids)}", headers=headers)
    return [{"id": song["id"], "name": song["name"], "artist": song["artists"][0]["name"]} for song in response.json().get("tracks", [])]

# Recommendations endpoint
@app.route("/recommendations")
def get_recommendations():
    access_token = request.args.get("access_token")
    user_id = request.args.get("user_id", "user123")
    rec_type = request.args.get("type", "hybrid")
    
    store_user_data(user_id, access_token)
    
    if rec_type == "cf":
        recommended_song_ids = recommend_songs_cf(user_id)
    elif rec_type == "cbf":
        recommended_song_ids = recommend_songs_cbf(user_id)
    else:
        recommended_song_ids = recommend_songs_hybrid(user_id, access_token)
    
    recommendations = get_song_details(recommended_song_ids, access_token)
    return jsonify(recommendations)

if __name__ == "__main__":
    app.run(debug=True)