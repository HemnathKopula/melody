## Melody
A hybrid music recommendation system using Spotify’s API, combining collaborative filtering (Surprise SVD) and genre-based content-based filtering to deliver personalized song suggestions.
Features

Collaborative filtering using playlist data (Surprise SVD).
Content-based filtering using genres from playlists, recently played tracks, and top tracks.
Hybrid recommendations combining CF and CBF.
Built with Flask, React, and SQLite, deployable on Heroku and Netlify.

### Setup

Clone: git clone https://github.com/your-username/melody.git

#### Backend:
cd backend
Create a virtual environment: python -m venv venv
Activate: source venv/bin/activate (Linux/Mac) or venv\Scripts\activate (Windows)
Install dependencies: pip install -r requirements.txt
Windows Users: Install Microsoft C++ Build Tools from https://visualstudio.microsoft.com/visual-cpp-build-tools/ (select “Desktop development with C++”).
Create a .env file in backend/ with:CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret


Set Redirect URI in Spotify Developer Dashboard to http://127.0.0.1:5000/callback.


#### Frontend:
cd frontend
Install dependencies: npm install


Run backend: python app.py
Run frontend: npm start

APIs Used

#### Spotify Web API:
/v1/me/playlists: Fetch user playlists.
/v1/playlists/{playlist_id}/tracks: Get playlist tracks.
/v1/me/player/recently-played: Fetch listening history.
/v1/me/top/tracks: Fetch top tracks.
/v1/tracks, /v1/artists: Fetch genres for CBF.


