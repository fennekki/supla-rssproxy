# supla-rssproxy

## howto

Make a json file containing the following structure
```json
{
    "own_url": "https://your_url",
    "target_dir": "/directory/to/write/feeds/in",
    "limit_recent": 200,
    "podcasts": {
        "podcastname": "https://www.supla.fi/supla/episodenumber"
    }
}
```

where

- `own_url` should contain the base URL the feeds will be hosted at;
- `target_dir` the directory on the current system to place the generated files
  in;
- `limit_recent` specifies how many episodes to put in the feed per podcast
  (default: 200); and
- `podcasts` is an object where
  - each key is the name that will be used to generate the rss file (eg.
    `podcastname` will become `podcastname.rss`, and
  - each value is a link to one of the episodes in the series you want to make
    the feed for (eg. `https://www.supla.fi/supla/3320811`).

Run `supla-rssproxy --config-file <filename>`.

supla-rssproxy will fetch data from the Supla API and write RSS files into
`target_dir`.

**WARNING**: Files with the same name that already exist in the target
directory will be replaced!! This is an intentional design decision to allow
updating the same files.

## thanks

Thanks to [@0x416C6578 on Twitter](https://twitter.com/0x416C6578) for actually
finding the location of the URLs for me when I'd missed them completely.

## notes

-

## coding conventions

- Strings use `"` always, because I can't stop myself
- PEP 8
