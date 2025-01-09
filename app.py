from flask import Flask, render_template, redirect, request, session, url_for

import random
import string
import os
import time
import spotipy
from spotipy import Spotify
from spotipy import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler


app = Flask(__name__)
app.secret_key = 'key'
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

SPOTIPY_CLIENT_ID = '300661955f0e413a9269edef3554548f'
SPOTIPY_CLIENT_SECRET = '7ad892b090b24f868070e2f81933891e'
SPOTIPY_REDIRECT_URI = 'http://localhost:5000/callback'

user_data = {}

sp_oauth = SpotifyOAuth(
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    SPOTIPY_REDIRECT_URI,
    scope="user-read-recently-played",
    show_dialog=True
)

cache_handler = FlaskSessionCacheHandler(session)
sp = Spotify(auth_manager=sp_oauth)






@app.route('/login')
def login():
    session.pop('token_info', None)
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)





@app.route('/')
def index():
    if not session.get('token_info'):
        return render_template('login.html')
    
    
    token_info = session['token_info']
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    recently_played = sp.current_user_recently_played(limit=10)['items']
    
    # Extract relevant information
    tracks = []
    for item in recently_played:
        track = item['track']
        tracks.append({
            'name': track['name'],
            'artist': ', '.join([artist['name'] for artist in track['artists']]),
            'album': track['album']['name']
        })
    
    return render_template('profile.html', tracks=tracks)








@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/profile')






USER_KEYS_FILE = 'user_keys.txt'

# Function to load user keys from the file into a dictionary
def load_user_keys():
    user_keys = {}
    if os.path.exists(USER_KEYS_FILE):
        with open(USER_KEYS_FILE, 'r') as f:
            for line in f:
                user_id, user_key = line.strip().split(',')
                user_keys[user_id] = user_key
    return user_keys

# Function to save user keys to the file
def save_user_keys(user_keys):
    with open(USER_KEYS_FILE, 'w') as f:
        for user_id, user_key in user_keys.items():
            f.write(f"{user_id},{user_key}\n")

# Generate user key function (you can adjust the length as needed)
def generate_user_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/profile')
def profile():
    # Check if the user is logged in (i.e., token_info exists in the session)
    if not session.get('token_info'):
        return redirect(url_for('login'))  # Redirect to the login page if no token

    token_info = session['token_info']
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    # Get the Spotify user ID to create a unique identifier
    user_id = sp.current_user()['id']
    
    # Load user keys from the file
    user_keys = load_user_keys()  # Load user keys from the text file

    # Check if this user already has a key
    if user_id not in user_keys:
        # Generate a new user key and store it in the file
        user_key = generate_user_code()
        user_keys[user_id] = user_key
        save_user_keys(user_keys)  # Save the updated keys to the file
    else:
        # Use the existing user key for this user
        user_key = user_keys[user_id]
    
    # Store the user key in the session (for future use if needed)
    session['user_key'] = user_key



    try:
        # Fetch the most recently played tracks from Spotify
        recently_played = sp.current_user_recently_played(limit=10)['items']
        tracks = [{
            'name': track['track']['name'],
            'artist': ', '.join([artist['name'] for artist in track['track']['artists']]),
            'album': track['track']['album']['name']
        } for track in recently_played]
    except Exception as e:
        # Handle any errors that occur when fetching Spotify data
        return render_template('error.html', error_message=str(e))

    # Pass the user key and tracks to the template
    return render_template('profile.html', user_key=user_key, tracks=tracks)








@app.route('/add_friend', methods=['POST'])
def add_friend():
    if not session.get('token_info'):
        return render_template('login.html')
    
    # Get the Spotify user ID from the session
    token_info = session['token_info']
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']

    # Get the friend's code from the form
    friend_code = request.form['friend_code']
    
    # Find the user who matches this friend code
    friend_user_id = None
    for uid, data in user_data.items():
        if data['friend_code'] == friend_code:
            friend_user_id = uid
            break
    
    if not friend_user_id:
        return "Friend code not found!", 404
    
    # Add the friend to the user's list
    if friend_user_id not in user_data[user_id]['friends']:
        user_data[user_id]['friends'].append(friend_user_id)
    
    return redirect('/friends')





@app.route('/friends', methods=['GET', 'POST'])
def friends():
    if not session.get('token_info'):
        return render_template('login.html')
    
    # Get the user's key from the session
    user_key = session.get('user_key')

    if not user_key:
        return redirect('/')  # if no user key, redirect to the main page
    
    # Get the user's friends list from user_data
    friends_data = []
    sp = spotipy.Spotify(auth=session['token_info']['access_token'])
    
    for friend_id in user_data[user_key]['friends']:
        friend = user_data.get(friend_id)
        if friend:
            friend_name = sp.user(friend_id)['display_name']
            friends_data.append({
                'friend_id': friend_id,
                'friend_name': friend_name,
                'friend_tracks': get_recently_played(friend_id)  # Fetch tracks for friend
            })
    
    # Handling the POST request (to add a friend)
    if request.method == 'POST':
        friend_code = request.form.get('friend_code')
        
        # Find the user with the friend code
        friend_user_id = None
        for uid, data in user_data.items():
            if data['friend_code'] == friend_code:
                friend_user_id = uid
                break
        
        if not friend_user_id:
            return "Friend code not found!", 404
        
        # Add friend to the user's friend list if not already added
        if friend_user_id not in user_data[user_key]['friends']:
            user_data[user_key]['friends'].append(friend_user_id)
        
        return redirect('/friends')
    
    # Handling friend removal
    if 'remove_friend_id' in request.args:
        remove_friend_id = request.args.get('remove_friend_id')
        
        if remove_friend_id in user_data[user_key]['friends']:
            user_data[user_key]['friends'].remove(remove_friend_id)
        
        return redirect('/friends')

    return render_template('friends.html', friends=friends_data)






# Function to get the last 10 tracks of a friend
def get_recently_played(user_id):
    sp = spotipy.Spotify(auth=session['token_info']['access_token'])
    tracks = []
    try:
        recently_played = sp.current_user_recently_played(limit=10)['items']
        tracks = [{
            'name': track['track']['name'],
            'artist': ', '.join([artist['name'] for artist in track['track']['artists']]),
            'album': track['track']['album']['name']
        } for track in recently_played]
    except spotipy.exceptions.SpotifyException:
        pass
    return tracks





@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()  # Clear all session data
    return redirect('/')  # Redirect to the home page (or any other page you prefer)





if __name__ == '__main__':
    app.run(debug=True)