import { useState, useEffect } from 'react';
import axios from 'axios';
import SongTile from './SongTile';
import '../styles/RecommendationDashboard.css';

const RecommendationDashboard = () => {
  const [accessToken, setAccessToken] = useState('');
  const [userId] = useState('user123');
  const [recType, setRecType] = useState('hybrid');
  const [recommendations, setRecommendations] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access_token');
    if (accessToken) {
      setAccessToken(accessToken);
      window.history.replaceState({}, document.title, '/');
    }
  }, []);

  const fetchRecommendations = async () => {
    try {
      console.log("Fetching with:", { accessToken, userId, recType });
      const res = await axios.get(
        `http://127.0.0.1:5000/recommendations?access_token=${accessToken}&user_id=${userId}&type=${recType}`
      );
      console.log("Recommendations:", res.data);
      setRecommendations(res.data);
      setError('');
    } catch (err) {
      console.error(err);
      setError(`Failed to fetch: ${err.message}`);
    }
  };

  const handleLogin = () => {
    window.location.href = "http://127.0.0.1:5000/login";
  };

  return (
    <div className="dashboard">
      <h1>Melody Music Recommendations</h1>
      {!accessToken ? (
        <button onClick={handleLogin} className="spotify-button">
          Login with Spotify
        </button>
      ) : (
        <div>
          <div className="controls">
            <select value={recType} onChange={(e) => setRecType(e.target.value)} className="select">
              <option value="hybrid">Hybrid</option>
              <option value="cf">Collaborative Filtering</option>
              <option value="cbf">Genre-Based Filtering</option>
            </select>
            <button onClick={fetchRecommendations} className="fetch-button">
              Get Recommendations
            </button>
          </div>
          {error && <p className="error">{error}</p>}
          <div className="song-grid">
            {recommendations.length > 0 ? (
              recommendations.map((song) => (
                <SongTile key={song.id} song={song} />
              ))
            ) : (
              <p className="info">No recommendations yet. Try fetching!</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default RecommendationDashboard;
