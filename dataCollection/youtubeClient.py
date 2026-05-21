#
# COSC2671 Social Media and Network Analytics
# @author Hexu Chen, RMIT University, 2026
# @author Chenglong Ma, RMIT University, 2026
#
# YouTube API client (replacing Reddit/PRAW client)
#

from dotenv import load_dotenv
from googleapiclient.discovery import build
from os import getenv
import sys

def youtubeClient():
    """
        Setup YouTube Data API v3 authentication.
        Replace the API key with your own.

        To obtain an API key:
        1. Go to https://console.cloud.google.com/
        2. Create a new project (or select an existing one)
        3. Enable "YouTube Data API v3"
        4. Go to Credentials -> Create Credentials -> API Key

        @returns: YouTube API service object
    """
    load_dotenv()
    try:
        API_KEY = getenv('API_KEY')
        youtube = build('youtube', 'v3', developerKey=API_KEY)
    except Exception as e:
        sys.stderr.write("Failed to create YouTube client: {}\n".format(str(e)))
        sys.exit(1)

    return youtube
