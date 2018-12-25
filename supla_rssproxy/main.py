import click
import datetime
import json
import re
import requests
import time
import uuid

from email.utils import format_datetime
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

    print(f"[{datetime.datetime.now()}] Scraping {supla_id}")
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

        print(f"[{datetime.datetime.now()}] Parsing {a_id}")

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
            # TODO: Figure out if we can get proper date info
            "pubDate": format_datetime(datetime.datetime.strptime(date_start, "%Y-%m-%d").astimezone()),
            # Since we're not setting this to no permalink, it can just
            # be the link
            "guid": page_link,
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
        }

        items.append(item)
    return items, series_name, series_description


def create_rss(items, series_name, series_description, rss_url):
    # The episodes are reverse-chronological: items[0] is the latest one
    link_text = items[0]["link"]
    last_build_date_data = datetime.datetime.now().astimezone()

    # We need a bunch of xml namespaces, see attribs in above function
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
    title.text = series_name

    description = ElementTree.SubElement(channel, "description")
    description.text = series_description

    # Link to the website of the podcast, I believe
    link = ElementTree.SubElement(channel, "link")
    link.text = link_text

    # Not an unfair assumption, on a finnish language website
    language = ElementTree.SubElement(channel, "language")
    language.text = "fi-FI"

    # Recommended link to self
    atom_link = ElementTree.SubElement(channel, "atom:link", attrib={
        "href": rss_url,
        "rel": "self",
        "type": "application/rss+xml"})

    # Feels fair to say who we are
    generator = ElementTree.SubElement(channel, "generator")
    generator.text = "supla-rssproxy"

    last_build_date = ElementTree.SubElement(channel, "lastBuildDate")
    last_build_date.text = str(format_datetime(last_build_date_data))

    # I mean, I guess this should be "yes" since I dunno
    itunes_explicit = ElementTree.SubElement(channel, "itunes:explicit")
    itunes_explicit.text = "yes"

    for i in items:
        item = ElementTree.SubElement(channel, "item")
        for key in i:
            if type(i[key]) is dict:
                ElementTree.SubElement(item, key, attrib=i[key])
            else:
                e = ElementTree.SubElement(item, key)
                e.text = str(i[key])

    return rss


@click.command()
@click.option("--config-file", required=True,
    type=click.File(mode="r", encoding="UTF-8", lazy=False),
    help="Location of json file to read config from")
def main(config_file):

    config = json.load(config_file)
    print(config)

    # There's no other validation of config other than that these exist
    podcasts = config["podcasts"]
    own_url = config["own_url"]
    target_dir = config["target_dir"]

    # The key for podcasts is what generates the rss filename
    for podcast_shortname in podcasts:
        supla_id = resolve_id(podcasts[podcast_shortname])

        # The locations of the file online and the physical file,
        # respectively
        rss_url = f"{own_url}/{podcast_shortname}.rss"
        target_file = f"{target_dir}/{podcast_shortname}.rss"

        # Run all the machinery above
        rss_data = get_rss_data(supla_id)
        rss = create_rss(*rss_data, rss_url)

        # Write the actual XML document via another ElementTree
        # construct
        ElementTree.ElementTree(rss).write(
            target_file, encoding="UTF-8", xml_declaration=True)
        print(f"[{datetime.datetime.now()}] Generated {target_file} from {supla_id}")


if __name__ == "__main__":
    main()
