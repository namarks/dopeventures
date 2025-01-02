# Dopetracks

The impetus for this project was a desire to automatically create a Spotify playlist that contained all the songs my friends had sent to eachother in the Dopetracks chat group. 

The solution to this problem turns out to be relatively straightforward once you figure things out: 
1. Extract Apple Messages data from the `chat.db` database stored on your Macbook (/Users/{yourusername}/Library/Messages/chat.db)
2. Find messages containing Spotify links
2. Generate Spotify playlist and populate with identified songs


To 

### Caching

This project uses an SQLite database to cache metadata for Spotify URLs, stored in the user's home directory at `~/.spotify_cache/spotify_cache.db`. This ensures efficient reuse of metadata and reduces API calls.

To initialize the cache, simply run the script. The cache directory will be created automatically if it doesn't exist.

The cache file is not included in this repository to ensure user privacy and prevent unnecessary commits.


### Useful resources
- typedstream library to parse Apple-formatted binary https://github.com/dgelessus/python-typedstream
- Other projects that parse iMessage data
    - https://github.com/yortos/imessage-analysis/blob/master/notebooks/imessages-analysis.ipynb
    - https://github.com/caleb531/imessage-conversation-analyzer/tree/167fb9c9a9082df453857f640d60904b30690443
    - BAIB project: https://github.com/arjunpat/treehacks24/blob/eb97a81c97b577e37a85d5dbdfdb2464c9fd7bfa/README.md
- List of music-related APIs: https://musicmachinery.com/music-apis/