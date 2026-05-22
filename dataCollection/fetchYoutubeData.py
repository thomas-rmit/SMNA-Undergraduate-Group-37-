#
# COSC2671 Social Media and Network Analytics
# @author Hexu Chen, RMIT University, 2026
# @author Chenglong Ma, RMIT University, 2026
#
# Utility script to fetch YouTube data and save as a JSON file.
# This produces a data dump in the same structure as youtubeDataDump.json
# so it can be used with the offline analysis scripts
# (youtubeTextProcessing.py, youtubeSentimentAnalysis.py).
#
# Usage:
#   python fetchYoutubeData.py
#
# Make sure to set your API key in youtubeClient.py first!
#

import json
import sys
from urllib.parse import urlparse, parse_qs
from youtubeClient import youtubeClient


def extractVideoId(url):
    """
    Extract a YouTube video ID from a URL.
    Supports formats:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
    Returns the video ID string, or the input itself if it looks like a bare ID.
    """
    parsed = urlparse(url)
    if parsed.hostname in ('youtu.be',):
        return parsed.path.lstrip('/')
    if parsed.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed.path == '/watch':
            return parse_qs(parsed.query).get('v', [None])[0]
        if parsed.path.startswith('/shorts/'):
            return parsed.path.split('/shorts/')[1]
    # Assume bare video ID was passed
    return url


def fetchYoutubeData(searchQuery, maxVideos=25, maxCommentsPerVideo=None, outputFile='youtubeDataDump.json'):
    """
    Fetch YouTube videos and their comments, then save to a JSON file.

    @param searchQuery: search query string (e.g. 'RMIT University')
    @param maxVideos: maximum number of videos to retrieve
    @param maxCommentsPerVideo: maximum number of comments per video (None = fetch all)
    @param outputFile: output JSON filename
    """

    client = youtubeClient()

    # Step 1: Search for videos
    print(f"Searching for videos with query: '{searchQuery}'...")
    searchResponse = client.search().list(
        q=searchQuery,
        part='snippet',
        type='video',
        order='viewCount',
        maxResults=min(maxVideos, 50),  # YouTube API max per request is 50
        publishedAfter='2026-02-14T00:00:00Z',
        publishedBefore='2026-03-01T00:00:00Z'
    ).execute()

    videoIds = []
    videoSnippets = {}
    for item in searchResponse.get('items', []):
        videoId = item['id']['videoId']
        videoIds.append(videoId)
        videoSnippets[videoId] = item['snippet']

    print(f"  Found {len(videoIds)} videos.")

    # Step 2: Get video statistics (viewCount, likeCount)
    print("Fetching video statistics...")
    statsResponse = client.videos().list(
        id=','.join(videoIds),
        part='statistics'
    ).execute()

    videoStats = {}
    for item in statsResponse.get('items', []):
        videoStats[item['id']] = item['statistics']

    # Step 3: Get comments for each video
    print("Fetching comments...")
    videos = []

    for videoId in videoIds:
        snippet = videoSnippets[videoId]
        stats = videoStats.get(videoId, {})

        video = {
            'title': snippet['title'],
            'videoId': videoId,
            'channelTitle': snippet['channelTitle'],
            'publishedAt': snippet['publishedAt'],
            'viewCount': int(stats.get('viewCount', 0)),
            'likeCount': int(stats.get('likeCount', 0)),
            'comments': []
        }

        try:
            comments_fetched = 0
            next_page_token = None

            while True:
                if maxCommentsPerVideo is not None:
                    request_limit = min(100, maxCommentsPerVideo - comments_fetched)
                else:
                    request_limit = 100

                commentResponse = client.commentThreads().list(
                    videoId=videoId,
                    part='snippet',
                    maxResults=request_limit,
                    pageToken=next_page_token,
                    textFormat='plainText'
                ).execute()

                for commentThread in commentResponse.get('items', []):
                    topComment = commentThread['snippet']['topLevelComment']['snippet']
                    video['comments'].append({
                        'author': topComment['authorDisplayName'],
                        'text': topComment['textDisplay'],
                        'publishedAt': topComment['publishedAt'],
                        'likeCount': topComment.get('likeCount', 0)
                    })
                    comments_fetched += 1

                    if maxCommentsPerVideo is not None and comments_fetched >= maxCommentsPerVideo:
                        break

                # if comments_fetched >= maxCommentsPerVideo:， break
                if maxCommentsPerVideo is not None and comments_fetched >= maxCommentsPerVideo:
                    break

                next_page_token = commentResponse.get('nextPageToken')
                if not next_page_token:
                    break

            print(f"  {snippet['title'][:50]}... → {len(video['comments'])} comments")

        except Exception as e:
            print(f"  {snippet['title'][:50]}... → Comments disabled or error: {e}")

        videos.append(video)

    # Step 4: Save to JSON
    data = {'videos': videos}
    with open(outputFile, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Saved {len(videos)} videos to '{outputFile}'.")


def fetchYoutubeDataByLinks(videoLinks, maxCommentsPerVideo=None, outputFile='youtubeDataDump.json'):
    """
    Fetch YouTube videos and their comments for a given list of video URLs or IDs,
    then save to a JSON file.

    @param videoLinks: list of YouTube video URLs or bare video IDs
    @param maxCommentsPerVideo: maximum number of comments per video (None = fetch all)
    @param outputFile: output JSON filename
    """
    client = youtubeClient()

    videoIds = [extractVideoId(link) for link in videoLinks]
    videoIds = [vid for vid in videoIds if vid]  # drop any None values
    print(f"Processing {len(videoIds)} video(s)...")

    # Step 1: Get video metadata + statistics
    statsResponse = client.videos().list(
        id=','.join(videoIds),
        part='snippet,statistics'
    ).execute()

    videoInfo = {}
    for item in statsResponse.get('items', []):
        videoInfo[item['id']] = {
            'snippet': item['snippet'],
            'statistics': item['statistics']
        }

    # Step 2: Get comments for each video
    videos = []
    for videoId in videoIds:
        info = videoInfo.get(videoId)
        if not info:
            print(f"  Video {videoId} not found or unavailable, skipping.")
            continue

        snippet = info['snippet']
        stats = info['statistics']

        video = {
            'title': snippet['title'],
            'videoId': videoId,
            'channelTitle': snippet['channelTitle'],
            'publishedAt': snippet['publishedAt'],
            'viewCount': int(stats.get('viewCount', 0)),
            'likeCount': int(stats.get('likeCount', 0)),
            'comments': []
        }

        try:
            comments_fetched = 0
            next_page_token = None

            while True:
                if maxCommentsPerVideo is not None:
                    request_limit = min(100, maxCommentsPerVideo - comments_fetched)
                else:
                    request_limit = 100

                commentResponse = client.commentThreads().list(
                    videoId=videoId,
                    part='snippet',
                    maxResults=request_limit,
                    pageToken=next_page_token,
                    textFormat='plainText'
                ).execute()

                for commentThread in commentResponse.get('items', []):
                    topComment = commentThread['snippet']['topLevelComment']['snippet']
                    video['comments'].append({
                        'author': topComment['authorDisplayName'],
                        'text': topComment['textDisplay'],
                        'publishedAt': topComment['publishedAt'],
                        'likeCount': topComment.get('likeCount', 0)
                    })
                    comments_fetched += 1

                    if maxCommentsPerVideo is not None and comments_fetched >= maxCommentsPerVideo:
                        break

                if maxCommentsPerVideo is not None and comments_fetched >= maxCommentsPerVideo:
                    break

                next_page_token = commentResponse.get('nextPageToken')
                if not next_page_token:
                    break

            print(f"  {snippet['title'][:50]}... → {len(video['comments'])} comments")

        except Exception as e:
            print(f"  {snippet['title'][:50]}... → Comments disabled or error: {e}")

        videos.append(video)

    # Step 3: Save to JSON
    data = {'videos': videos}
    with open(outputFile, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Saved {len(videos)} videos to '{outputFile}'.")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    # --- Option A: Search by query ---
    #SEARCH_QUERY = 'Ukraine War'
    #MAX_VIDEOS = 10
    #MAX_COMMENTS = 200
    #OUTPUT_FILE = 'youtubeDataDump.json'
    #fetchYoutubeData(SEARCH_QUERY, MAX_VIDEOS, MAX_COMMENTS, OUTPUT_FILE)

    # --- Option B: Fetch from a list of video links ---
    VIDEO_LINKS = [
# Sky News Pre War
        'https://www.youtube.com/watch?v=euNsW7kvNJc',
        'https://www.youtube.com/watch?v=ijDBAfPUTas',

        # Sky News 2022
        'https://www.youtube.com/watch?v=4N-914wIMPY',
        'https://www.youtube.com/watch?v=NhQeU4rj50Q',

        # Sky News 2024
        'https://www.youtube.com/watch?v=L2E44vC8mzY',
        'https://www.youtube.com/watch?v=_RSU0OxVBeg',

        # BBC Pre War
        'https://www.youtube.com/watch?v=yhe0ZOOHmVQ',
        'https://www.youtube.com/watch?v=IjH-hJQBM38',

        # BBC 2022
        'https://www.youtube.com/watch?v=6tOKJU9WevI',
        'https://www.youtube.com/watch?v=HoiEu7F2OWg',

        # BBC 2024
        'https://www.youtube.com/watch?v=HHusgEBIYhs',
        'https://www.youtube.com/watch?v=MaY-t2YGdA8',

        # DW Pre War
        'https://www.youtube.com/watch?v=qTs0rbHGDk8',
        'https://www.youtube.com/watch?v=gzPbolzX9KM',

        # DW 2022
        'https://www.youtube.com/watch?v=h9FlJKFWawM',
        'https://www.youtube.com/watch?v=GjGdyVBagzc',

        # DW 2024
        'https://www.youtube.com/watch?v=iNnA-CJh_e8',
        'https://www.youtube.com/watch?v=rvhLrIWNCWg'

    ]
    MAX_COMMENTS = 1000   # None = fetch ALL comments per video
    OUTPUT_FILE = 'dataCollection/data/data.json'
    fetchYoutubeDataByLinks(VIDEO_LINKS, MAX_COMMENTS, OUTPUT_FILE)
