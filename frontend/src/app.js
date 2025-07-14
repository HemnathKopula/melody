import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [accessToken, setAccessToken] = useState("");
  const [userId, setUserId] = useState("user123"); // Replace with actual user ID
  const [recommendations, setRecommendations] = useState([]);
  const [recType, setRecType] = useState("hybrid");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get("access_token");
    if (token) {
      setAccessToken(token);
      window.history.replaceState({}, document.title, "/");
    }
  }, []);

  useEffect(() => {
    if (accessToken) {
      setLoading(true);
      axios.get(`http://localhost:5000/recommendations?access_token=${accessToken}&user_id=${userId}&type=${recType}`)
        .then(response => {
          setRecommendations(response.data);
          setLoading(false);
        })
        .catch(error => {
          console.error("Error fetching recommendations:", error);
          setLoading(false);
        });
    }
  }, [accessToken, recType]);

  return (
    <div className="App">
      <h1>Melody</h1>
      {!accessToken ? (
        <a href="http://localhost:5000/login">Login with Spotify</a>
      ) : (
        <div>
          <h2>Recommended Songs</h2>
          <select value={recType} onChange={(e) => setRecType(e.target.value)}>
            <option value="cf">Collaborative Filtering</option>
            <option value="cbf">Genre-Based Filtering</option>
            <option value="hybrid">Hybrid</option>
          </select>
          {loading ? (
            <p>Loading recommendations...</p>
          ) : (
            <ul>
              {recommendations.map(song => (
                <li key={song.id}>{song.name} by {song.artist}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default App;