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
    """Resolve URL, partial URL, or numeric id to numeric id.

    The numeric id represents the id of an episode in a Supla series.
    """
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
    """Fetch XML describing a single episode on Supla."""
    # We happen to know this is where the XML is stored. Hacky, in that
    # sense
    url = f"http://gatling.nelonenmedia.fi/media-xml-cache?id={supla_id}"
    ref = f"https://www.supla.fi/supla/{supla_id}"

    return ElementTree.fromstring(requests.get(url, headers={"Referer": ref}).text)


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


def get_rss_data(supla_id):
    """Get objects matching the data scraped from Supla.

    First we scrape the HTML document for the URLs of other episodes,
    then we query the known XML location for all those episodes. This
    data is used to construct the starting point for RSS.
    """
    base_url = "https://www.supla.fi/supla"
    url = f"{base_url}/{supla_id}"
    document = requests.get(url).text
    # We use our custom HTMLParserAdapter because XMLParser might not
    # work. HTMLParserAdapter just makes HTMLParser provided by Python
    # act like XMLParser does by default.
    html = ElementTree.XML(document, parser=HTMLParserAdapter())

    # Hacky, but works? Depends on the sidebar having exactly this
    # structure
    other_episodes = html.findall(".//div[@class='video-sidebar__content']/div/div/a")

    # Other hacks to find name, description
    series_name = html.find(".//h2[@class='series-info__title']").text
    series_description = html.find(".//div[@class='series-info__description']").text

    # Collect all the episodes here
    items = []
    for a in other_episodes:
        # The href attribute from the links, in format /supla/<id>
        href = a.attrib['href']
        # resolve_id still works here
        a_id = resolve_id(href)

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
            # UUID 5 (SHA1-hash) based on the URL
            "guid": uuid.uuid5(uuid.NAMESPACE_URL, page_link),
            "link": page_link,
            "description": program.attrib["description"],
            "content:encoded": program.attrib["description"],
            # This needs to become an <enclosure> with attributes, no
            # body
            "enclosure": {
                "length": audiofile_length,  # In bytes
                "type": audiofile_type,  # Mimetype
                "url": audiofile_url,
            },
            # These might be ignored but I'm trying anyway
            "itunes:duration": duration_str,
            "itunes:explicit": "no",
            "itunes:episodeType": "full",
        }

        items.append(item)
    return items, series_name, series_description


def create_rss(items, series_name, series_description):
    # The episodes are reverse-chronological: items[0] is the latest one
    link = items[0]["link"]
    lastBuildDate = datetime.datetime.now()

    rss = ElementTree.Element("rss", attrib={"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel", text=series_name)
    ElementTree.SubElement(channel, "title", text=series_name)
    ElementTree.SubElement(channel, "description", text=series_description)
    ElementTree.SubElement(channel, "link", text=link)
    ElementTree.SubElement(channel, "generator", text="supla-rssproxy")
    ElementTree.SubElement(channel, "lastBuildDate", text=str(lastBuildDate))

    for i in items:
        item = ElementTree.SubElement(channel, "item")
        for key in i:
            if type(i[key]) is dict:
                ElementTree.SubElement(item, key, attrib=i[key])
            else:
                ElementTree.SubElement(item, key, text=str(i[key]))

    return rss


@click.command()
@click.argument("supla_id")
def main(supla_id):
    supla_id = resolve_id(supla_id)

    rss_data = get_rss_data(supla_id)
    rss = create_rss(*rss_data)
    print(ElementTree.tostring(rss))


if __name__ == "__main__":
    main()
