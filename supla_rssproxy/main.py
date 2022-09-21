import datetime
import json
import uuid

import click
import requests

from email.utils import format_datetime
from html.parser import HTMLParser
from xml.etree import ElementTree


API_PODCAST_ENDPOINT = "https://prod-component-api.nm-services.nelonenmedia.fi/api/podcast/{}"
API_EPISODES_ENDPOINT = "https://prod-component-api.nm-services.nelonenmedia.fi/api/component/260010351"
API_SINGLE_EPISODE_ENDPOINT = "https://appdata.richie.fi/books/feeds/v3/Nelonen/podcast_episode/{}.json"
SUPLA_BASE_URL = "https://www.supla.fi"

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
        "image": podcast_data["thumbnailUrl"],
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
        item_permalink = SUPLA_BASE_URL + item["link"]["href"]
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
            "guid": item_permalink,
            "description": description,
            "enclosure": {
                "length": str(audio_length),
                "type": "audio/mpeg",  # TODO detect this instead of guessing here
                "url": audio_url,
            },
            "itunes:duration": duration_str,
            "itunes:image": {
                "href": cover_url,
            },
        }

        podcast["episodes"].append(episode)

    return podcast


def generate_rss(podcast, rss_url):
    last_build_date_data = datetime.datetime.now().astimezone()

    rss = ElementTree.Element(
        "rss",
        attrib={
            "version": "2.0",
            "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
            "xmlns:atom": "http://www.w3.org/2005/Atom",
        })
    channel = ElementTree.SubElement(rss, "channel")

    title = ElementTree.SubElement(channel, "title")
    title.text = podcast["title"]

    description = ElementTree.SubElement(channel, "description")
    description.text = podcast["description"]

    # Link to the website of the podcast, I believe
    link = ElementTree.SubElement(channel, "link")
    link.text = podcast["link"]

    image = ElementTree.SubElement(channel, "image")
    image_url = ElementTree.SubElement(image, "url")
    image_url.text = podcast["image"]
    image_title = ElementTree.SubElement(image, "title")
    image_title.text = podcast["title"]
    image_link = ElementTree.SubElement(image, "link")
    image_link.text = podcast["link"]

    # Not an unfair assumption, on a finnish language website
    language = ElementTree.SubElement(channel, "language")
    language.text = "fi-FI"

    # Recommended link to self
    atom_link = ElementTree.SubElement(channel, "atom:link", attrib={
        "href": rss_url,
        "rel": "self",
        "type": "application/rss+xml"})

    generator = ElementTree.SubElement(channel, "generator")
    generator.text = "supla-rssproxy"

    last_build_date = ElementTree.SubElement(channel, "lastBuildDate")
    last_build_date.text = str(format_datetime(last_build_date_data))

    for ep in podcast["episodes"]:
        item = ElementTree.SubElement(channel, "item")
        for key in ep:
            if type(ep[key]) is dict:
                ElementTree.SubElement(item, key, attrib=ep[key])
            else:
                e = ElementTree.SubElement(item, key)
                e.text = ep[key]

    return rss


class HTMLParserAdapter(HTMLParser):
    """Adapter class to make HTMLParser behave like XMLParser."""
    def __init__(self, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.treebuilder = ElementTree.TreeBuilder()

    def handle_starttag(self, tag, attrs):
        self.treebuilder.start(tag, dict(attrs))

    def handle_endtag(self, tag):
        self.treebuilder.end(tag)

    def handle_data(self, data):
        self.treebuilder.data(data)

    def close(self):
        HTMLParser.close(self)
        return self.treebuilder.close()


def resolve_id(id_or_url):
    try:
        supla_id = str(uuid.UUID(id_or_url))
    except ValueError:
        # Assume it's a URL for the podcast page
        contents = requests.get(id_or_url).text 
        html = ElementTree.fromstring(contents, parser=HTMLParserAdapter())

        app_url = html.find(
            ".//head/meta[@property='al:ios:url']"
        ).attrib["content"]
        supla_id = str(uuid.UUID(app_url.split("/")[-1]))

    return supla_id


@click.command()
@click.option("--config-file", required=True,
    type=click.File(mode="r", encoding="UTF-8", lazy=False),
    help="Location of json file to read config from")
def main(config_file):

    config = json.load(config_file)

    # There's no other validation of config other than that these exist
    podcasts = config["podcasts"]
    own_url = config["own_url"]
    target_dir = config["target_dir"]
    limit_recent = config.get("limit_recent", 200)

    for shortname in podcasts:
        id_or_url = podcasts[shortname]
        print(f"[{datetime.datetime.now()}] Resolving {id_or_url}...")
        podcast_id = resolve_id(id_or_url)
        print(f"[{datetime.datetime.now()}] {id_or_url} resolved to {podcast_id}")

        rss_url = f"{own_url}/{shortname}.rss"
        target_file = f"{target_dir}/{shortname}.rss"

        print(f"[{datetime.datetime.now()}] Fetching {podcast_id}...")
        podcast = get_podcast_data(podcast_id, limit=limit_recent)
        print(f"[{datetime.datetime.now()}] {len(podcast['episodes'])} episodes")
        print(f"[{datetime.datetime.now()}] Generating RSS...")
        rss = generate_rss(podcast, rss_url)

        print(f"[{datetime.datetime.now()}] Generating {target_file}...")
        ElementTree.ElementTree(rss).write(
            target_file, encoding="UTF-8", xml_declaration=True)

        print(f"[{datetime.datetime.now()}] Generated {target_file} from {id_or_url}")


if __name__ == "__main__":
    main()
