const SongTile = ({ song }) => {
  if (!song || !song.name || !song.artist) return null;

  return (
    <div className="song-tile">
      <h3>{song.name}</h3>
      <p>{song.artist}</p>
    </div>
  );
};

export default SongTile;
