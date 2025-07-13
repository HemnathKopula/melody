## Melody

A hybrid music recommendation system using Spotify’s API, combining collaborative filtering (ALS) and content-based filtering (cosine similarity) to deliver personalized song suggestions.

### Features
Collaborative filtering using playlist data.
Content-based filtering using Spotify audio features.
Hybrid recommendations for enhanced accuracy.
Built with Flask, React, and SQLite, deployable on Heroku and Netlify.

### Setup
Clone: git clone https://github.com/your-username/melody.git
Backend: cd backend && pip install -r requirements.txt
Frontend: cd frontend && npm install
Set Spotify API credentials in backend/app.py.

### Running
Backend: python app.py
Frontend: cd frontend && npm start