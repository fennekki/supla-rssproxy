import click
import datetime
import re
import requests
import uuid

from html.parser import HTMLParser
from xml.etree import ElementTree


class InvalidSuplaIdError(Exception):
    pass


def resolve_id(supla_id):
    try:
        supla_id = int(supla_id)
    except ValueError:
        try:
            match = re.match(r"(((https?://)?(www\.)?supla\.fi)?/)?supla/([0-9]+)", supla_id)
            supla_id = int(match[5])
        except ValueError:
            raise InvalidSuplaIdError(f"Invalid id {supla_id}")
    return supla_id


def fetch_xml(supla_id):
    url = f"http://gatling.nelonenmedia.fi/media-xml-cache?id={supla_id}"
    ref = f"https://www.supla.fi/supla/{supla_id}"

    return ElementTree.fromstring(requests.get(url, headers={"Referer": ref}).text)


class HTMLParserAdapter(HTMLParser):
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



@click.command()
@click.argument("supla_id")
def main(supla_id):
    supla_id = resolve_id(supla_id)

    base_url = "https://www.supla.fi/supla"
    url = f"{base_url}/{supla_id}"
    document = requests.get(url).text
    html = ElementTree.XML(document, parser=HTMLParserAdapter())

    # Hacky, but works?
    other_episodes = html.findall(".//div[@class='video-sidebar__content']/div/div/a")
    for a in other_episodes:
        href = a.attrib['href']
        a_id = resolve_id(href)
        print(a_id)

        xml = fetch_xml(a_id)

        # Get full link to page for this episode
        page_link = f"https://www.supla.fi{href}"

        # Let's find what this episode is about
        program = xml.find("./Behavior/Program")
        duration = xml.find("./Clip/Duration")
        date_start = xml.find("./Clip/PassthroughVariables/variable[@name='date_start']").attrib["value"]

        # This node is where we'll find the mp3 url
        audiomediafile = xml.find("./Clip/AudioMediaFiles/AudioMediaFile")
        audiofile_url = audiomediafile.text
        audiofile_head = requests.head(audiofile_url)
        audiofile_length = audiofile_head.headers["Content-Length"]
        audiofile_type = audiofile_head.headers["Content-Type"]

        # Calculate and format length
        duration_str = str(datetime.timedelta(seconds=int(duration.text)))

        # This is the thing that gets turned to RSS XML again
        item = {
            "title": program.attrib["program_name"],
            "pubDate": date_start,
            "guid": uuid.uuid5(uuid.NAMESPACE_URL, page_link),
            "link": page_link,
            "description": program.attrib["description"],
            "content:encoded": program.attrib["description"],
            "enclosure": {
                "length": audiofile_length,  # In bytes
                "type": audiofile_type,  # Mimetype
                "url": audiofile_url,
            },
            "itunes:duration": duration_str,
            "itunes:explicit": "no",
            "itunes:episodeType": "full",
        }

        print(item)


if __name__ == "__main__":
    main()
