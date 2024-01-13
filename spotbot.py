from dotenv import load_dotenv
from requests import post, get
from urllib.parse import quote
from PIL import Image
from io import BytesIO
import streamlit as st
import spotipy
import openai
import os
import base64
import json
import time

load_dotenv()

# setting env variables/keys
openai.api_key=os.getenv("OPENAI_API_KEY")
client_id=os.environ['SPOTIFY_CLIENT_ID']
client_secret=os.environ['SPOTIFY_CLIENT_SECRET']
base_url=os.environ['BASE_URL']

# setting and encoding scopes for url
scopes = "playlist-modify-private ugc-image-upload user-top-read"
encoded_scopes = quote(scopes)

# authorization url
auth_url = f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri={base_url}&scope={encoded_scopes}"


# displays a login link to spotify using streamlit's query parameter functionality
# checks if authorization code is present in the URL. if not, it prompts the user to log in
def spotify_login():
    import streamlit as st

    # this initial check is for when the streamlit page is refreshed (main is called again)
    # but there is already a valid authorization code in the URL
    query_param = st.experimental_get_query_params()
    if query_param:
        return query_param["code"][0]

    st.subheader(f"First, please log in to your Spotify account", )
    st.markdown(f'<a href="{auth_url}" target="_blank">Login to Spotify</a>', unsafe_allow_html=True)
    st.caption(f"(p.s. we will only access information about your music taste (top tracks, artists, etc) and to create your curated playlists)")

    query_param = st.experimental_get_query_params()
    if query_param:
        return query_param["code"][0]


# takes spotify authorization code and exchanges it for access token using spotify's API and returns client object
@st.cache_data # decorator to check if function called w/ same params, if so, skip execution
def get_spotify_client(authorization_code):
    import streamlit as st

    response = post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": base_url,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    if response.status_code == 200:
        return spotipy.Spotify(auth=response.json()["access_token"])
    # if reach here then the authorization has expired/requires refresh token, to simplify, directly ask users to relogin
    else:
        st.warning("your spotify connection has expired, please log in again...")
        st.markdown(f'<a href="{auth_url}" target="_self">Re-login to Spotify</a>', unsafe_allow_html=True)

# renders local animation for loading progress
def render_animation():
    file_path = "./spotbotdog.gif" 
    with open(file_path, "rb") as file_:
        contents = file_.read()
        data_url = base64.b64encode(contents).decode("utf-8")
    return st.markdown(
        f'<img src="data:image/gif;base64,{data_url}" alt="dog gif">',
        unsafe_allow_html=True,
    )

# function for converting and encoding uploaded/dall-e created image for spotify API specifications
def convert_image(image, dall_e):
    if dall_e:
        # downloading the dall-e created image
        dalle_response = get(image)
        image_data = dalle_response.content
        image = Image.open(BytesIO(image_data))

    # convert image to jpeg format (this is required for spotify's upload cover image API)
    output_buffer = BytesIO()
    image.convert("RGB").save(output_buffer, format="JPEG")

    # encode to base64 string
    jpeg_image_str = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
    return jpeg_image_str

# function for rendering intro text/page routing with instructions
def intro ():
    import streamlit as st

    # function call for button click to render next page of application
    def nextpage():
        st.session_state.page_name = 'app'

    placeholder = st.empty()
    intro_text = (
        "Welcome to spotbot! Spotbot is a custom playlist generator for Spotify curated using tools such as "
        "OpenAI, Streamlit, and Spotipy."
    )

    description = ("Have you ever found yourself spending hours searching for the perfect playlist for your mood? "
        "Or is there a new genre of music you'd like to slowly explore? We extract your music tastes and history "
        "(specifically top 10 tracks and artists) to curate specially-tailored playlists designed by OpenAI's gpt models, based on "
        "your description of the playlist! Spotbot can even generate unique playlist titles and descriptions, and by using OpenAI's "
        "Dall-E model, can create an AI-generated cover image for you. All of this is then conveniently connected to your Spotify account "
        "so that you can save time searching, and start listening!"
    )

    disclaimer = ("Note: We'd like to remind you that Spotbot utilizes OpenAI's models to generate your playlists "
        "and cover arts. Although we cannot gaurantee that you'll instantly love every song on your generated playlist, "
        "we encourage you to give it a try!"
    )
    placeholder.markdown(f'<p class="big-font">{intro_text}\n\n{description}\n\n{disclaimer}\n\nWe hope you find spotbot useful <3</p>', unsafe_allow_html=True)
    st.button(":violet[let's get started!]", on_click=nextpage, key="start_button")

# function for rendering app content (note the login page for spotify is incorporated here as one page)
def app ():
    import streamlit as st

    authorization_code = spotify_login()
    if not authorization_code:
        return # this is such that the rest of the application (form) doesn't render if the user isn't authenticated
    spotify_client = get_spotify_client(authorization_code)

    # getting input from user
    with st.form("user_input"):
        prompt = st.text_input("what's the :rainbow[vibe]? describe the music you'd like this playlist to contain:", placeholder="chill indie bedroom pop for late nights", max_chars=100)
        song_count = st.slider("how many songs in the playlist?", 1, 30, 10)
        st.divider()

        st.markdown('<p class="big-font">feel free to add any of the following playlist specifications. if you choose to leave them blank, spotbot will auto generate each for you!</p>', unsafe_allow_html=True)

        user_title = st.text_input("add a playlist title...", placeholder="late indie bops", max_chars=100)
        user_description = st.text_input("add a playlist description...", placeholder="songs that always set the mood for me time!", max_chars=300)
        user_image = st.file_uploader("upload a playlist cover image...", type=['png','jpg'], help="note you can only upload jpg/png file types!")
        image_prompt = st.text_input("or alternatively, describe a cover for your playlist you'd like spotbot to generate!", placeholder="a cat listening to music inside a cozy room at night", max_chars=100)

        if user_image is not None:
            image_str = convert_image(user_image, False)

        submitted = st.form_submit_button(":violet[create!]")

        # check if prompt is empty after form submission (since prompt is required)
        if submitted and prompt.strip() == "":
            st.warning("Please provide a playlist description before submitting.")
            submitted = False

    if not submitted:
        return

    # displaying progress loading animation
    my_bar = st.progress(0, text='')
    left_co, cent_co, last_co = st.columns(3)
    gif_placeholder = cent_co.empty()
    with gif_placeholder:
        render_animation()

    for percent_complete in range(100):
        time.sleep(0.7)  
        my_bar.progress(percent_complete + 1, text="Spotbot's hard at work! Please wait.")

    # extracting user's listening history for openAI prompt
    user_top_tracks = spotify_client.current_user_top_tracks(limit=10, time_range='medium_term')
    track_names = [track['name'] for track in user_top_tracks['items']]
    user_top_artists = spotify_client.current_user_top_artists(limit=10, time_range='medium_term')
    artist_names = [artist['name'] for artist in user_top_artists['items']]


    try:
    # extracting user's listening history for OpenAI prompt
        user_top_tracks = spotify_client.current_user_top_tracks(limit=10, time_range='medium_term')
        track_names = [track['name'] for track in user_top_tracks['items']]
        user_top_artists = spotify_client.current_user_top_artists(limit=10, time_range='medium_term')
        artist_names = [artist['name'] for artist in user_top_artists['items']]
    except Exception as e:
        print("Error:", e)
        st.warning("your spotify connection has expired, please log in again...")
        st.markdown(f'<a href="{auth_url}" target="_self">Re-login to Spotify</a>', unsafe_allow_html=True)

    # constructing OpenAI message based on user inputs
    openai_messages = [
        {
            "role": "system",
            "content": "You are spotbot, world's best music recommendation AI. Given a description of a user's music history of their top 10 artists and top 10 tracks,"
                f"you will recommend different and fresh songs tailored to a description provided by the user.",
        },
        {
            "role": "user",
            "content": f"The following is the user's music history:"
                f"This user likes the following artists: {artist_names}"
                f"This user likes the following songs: {track_names}"
                f"create a playlist with {song_count} different and new songs that fits the following description: '''{prompt}'''.",
        },
    ]

    if user_title:
        openai_messages[1]["content"] += f"\nPlaylist Name: {user_title}"

    if user_description:
        openai_messages[1]["content"] += f"\nPlaylist Description: {user_description}"

    # openAI gpt call
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613",
        temperature=1,
        messages=openai_messages,
        functions=[
            {
                "name": "create_playlist",
                "description": "Creates a spotify playlist based on a list of songs that should be added to the list.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "playlist_name": {
                            "type": "string",
                            "description": "Unique and creative name of playlist",
                        },
                        "playlist_description": {
                            "type": "string",
                            "description": "Unique and creative description for the playlist.",
                        },
                        "songs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "songname": {
                                        "type": "string",
                                        "description": "Name of the song that should be added to the playlist",
                                    },
                                    "artists": {
                                        "type": "array",
                                        "description": "List of all artists",
                                        "items": {
                                            "type": "string",
                                            "description": "Name of artist of the song",
                                        },
                                    },
                                },
                                "required": ["songname", "artists"],
                            },
                        },
                    },
                    "required": ["songs", "playlist_name", "playlist_description"],
                },
            }
        ],
    )

    # openAI dall-e call if the user opts for spotbot to create the cover
    if image_prompt:
        dall_e_image = openai.Image.create(
            model = "dall-e-2",
            prompt = image_prompt + ". Please make this image less than 200kb file size",
            n = 1,
            size = "256x256"
        )

        dall_e_image_url = dall_e_image['data'][0]['url']
        dall_e_image_str = convert_image(dall_e_image_url, True)

    # from here we have all the required components from openAI calls to create the playlist, now use spotify API

    arguments = json.loads(
        response["choices"][0]["message"]["function_call"]["arguments"]
    )
    recommended_songs = arguments["songs"]

    # creating song_uris for adding to playlist
    song_uris = [
        spotify_client.search(
            q=f"{song['songname']} {','.join(song['artists'])}", limit=1
        )["tracks"]["items"][0]["uri"]
        for song in recommended_songs
    ]

    if user_title:
        playlist_title = user_title
    else:
        playlist_title = "spotbot - " + arguments["playlist_name"]
    if user_description:
        playlist_description = user_description
    else:
        playlist_description = arguments["playlist_description"] + "this playlist was generated by spotbot!"

    # creating playlist
    user_id = spotify_client.me()["id"]
    playlist = spotify_client.user_playlist_create(user_id, playlist_title, False, description=playlist_description)
    new_playlist_id = playlist["id"]
    spotify_client.playlist_add_items(new_playlist_id, song_uris)
    if user_image:
        spotify_client.playlist_upload_cover_image(new_playlist_id, image_str)
    elif image_prompt:
        spotify_client.playlist_upload_cover_image(new_playlist_id, dall_e_image_str)

    # clearing all of the loading progress animations
    my_bar.empty()
    gif_placeholder.empty()

    st.link_button("check out your curated playlist!", playlist['external_urls']['spotify'])

# main function that calls each of the pages/routing
def main ():
    st.set_page_config(
        page_title="spotbot",
        page_icon="🎵",
        layout="centered",
        initial_sidebar_state="auto"
    )
    st.markdown("""
        <style>
        .big-font {
            font-size:20px !important;
            font-weight: medium;
        }
        </style>
        """, unsafe_allow_html=True
    )

    st.title(":violet[spotbot] - your custom spotify playlist generator <3")
    st.divider()

    # first time opening spotbot
    if 'page_name' not in st.session_state:
        st.session_state['page_name'] = 'intro'

    # if we have query parameters from url then we already logged into spotify
    query_param = st.experimental_get_query_params()
    if query_param:
        st.session_state.page_name = 'app'

    if st.session_state.page_name == 'app':
        app()
    else:
        intro()


if __name__ == "__main__":
    main()
