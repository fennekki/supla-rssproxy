# supla-rssproxy

## howto

Make a json file containing the following
```json
{
    "own_url": "https://your_url",
    "target_dir": "~/public_html or whereever",
    "podcasts": {
        "podcastname": "https://link to an episode on supla"
    }
}
```

Run `supla-rssproxy --config-file <filename>`.

supla-rssproxy will scrape the website and produce a new RSS document.

## thanks

Thanks to [@0x416C6578 on Twitter](https://twitter.com/0x416C6578) for actually
finding the location of the URLs for me when I'd missed them completely.

## notes

The url to fetch from is
`http://gatling.nelonenmedia.fi/media-xml-cache?id={ID}&v=2` where `{ID}` is
replaced by the Supla episode id (eg. for `https://www.supla.fi/supla/3320811`
this would be `3320811`). This XML file contains data we want

Looks like
`https://dynamic-gatling.nelonenmedia.fi/cos/videos/2/limit=100&orderby=airtime&order_direction=desc&media_type=audio_podcast&series={series
id}` is where we should find the data on the series but it seems to require an API key.

## coding conventions

- Strings use `"` always, because I can't stop myself
- PEP 8
