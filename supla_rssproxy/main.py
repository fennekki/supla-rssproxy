import datetime
import json

import click
import requests

from email.utils import format_datetime
from xml.etree import ElementTree


API_PODCAST_ENDPOINT = "https://prod-component-api.nm-services.nelonenmedia.fi/api/podcast/{}"
API_EPISODES_ENDPOINT = "https://prod-component-api.nm-services.nelonenmedia.fi/api/component/260010351"
API_SINGLE_EPISODE_ENDPOINT = "https://appdata.richie.fi/books/feeds/v3/Nelonen/podcast_episode/{}.json"

API_APP_NAME = "supla"
API_CLIENT_NAME = "webplus"


def get_podcast_data(podcast_id, *, limit):
    podcast_params = {
        "app": API_APP_NAME,
        "client": API_CLIENT_NAME,
        "userroles": "Non_Logged_In_User",
    }
    podcast_data = json.loads(
        requests.get(
            API_PODCAST_ENDPOINT.format(podcast_id), params=podcast_params
        ).text)["metadata"]["jsonld"]

    podcast = {
        "title": podcast_data["name"],
        "link": podcast_data["thumbnailUrl"],
        "description": podcast_data["description"],
        "pubDate": podcast_data["datePublished"],  # TODO: WRONG!! parse and format!!
        "link": podcast_data["contentUrl"],
        "episodes": []
    }
    
    params = {
        "limit": limit,
        "current_podcast_id": podcast_id,
        "switch_sorting": 0,
        "app": API_APP_NAME,
        "client": API_CLIENT_NAME,
        "offset": 0  # TODO: paging!
    }
    data = json.loads(requests.get(API_EPISODES_ENDPOINT, params=params).text)
    for item in data["items"]:
        item_id = item["id"]
        item_data = json.loads(
            requests.get(API_SINGLE_EPISODE_ENDPOINT.format(item_id)).text
        )["data"]


        title = item_data["title"]
        series_title = item_data["series_title"]
        description = item_data["description"]
        audio_url = item_data["audio_url"]
        audio_duration = item_data["audio_duration"]
        audio_length = item_data["audio_length"]
        last_modified = item_data["last_modified"]
        cover_url = item_data["cover_url"]

        duration_str = str(datetime.timedelta(seconds=int(audio_duration)))
        # TODO might want something other than modified date, we can
        # probly get other data too
        modified_datetime = format_datetime(
            # the times look like 2022-09-20T22:32:58.932060Z but
            # strtime doesnt understand micros
            # we also need to put in the UTC timezone
            datetime.datetime.strptime(
                last_modified.split(".")[0],
                "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=datetime.timezone.utc))

        episode = {
            "title": title,
            "pubDate": modified_datetime,
            "guid": item_id,
            "description": description,
            "content:encoded": description,
            "enclosure": {
                "length": audio_length,
                "type": "audio/mpeg",  # TODO detect this instead of guessing here
                "url": audio_url,
            },
            "itunes:duration": duration_str,
            "itunes:image": cover_url,
        }

        podcast["episodes"].append(episode)

    return podcast


@click.command()
# @click.option("--config-file", required=True,
#     type=click.File(mode="r", encoding="UTF-8", lazy=False),
#     help="Location of json file to read config from")
# def main(config_file):
def main():
    p = get_podcast_data("87c45b04-6e54-4cff-82d9-4aa9589a397a", limit=3)
    print(p)


if __name__ == "__main__":
    main()
