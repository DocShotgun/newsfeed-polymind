import json
import os
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

# Read config
script_dir = Path(os.path.abspath(__file__)).parent
conf_path = script_dir / "config.json"
with open(conf_path, "r") as config_file:
    config = json.load(config_file)
results_per_source = config.get("results_per_source", 5)
rss_sources = config.get(
    "rss_sources", []
)
ctx_alloc = config.get("ctx_alloc", 0.3)


def rss_news_get(rss_url, max_results):
    feed = feedparser.parse(rss_url)

    articles_list = []

    for article in feed.entries:
        if len(articles_list) < max_results:
            title = article.title
            link = article.link
            soup = BeautifulSoup(article.description, "html.parser")
            summary = soup.get_text()

            articles_list.append({"title": title, "link": link, "summary": summary})

    return articles_list


def main(params, memory, infer, ip, Shared_vars):
    # Definitions for API-based tokenization
    API_ENDPOINT_URL = Shared_vars.API_ENDPOINT_URI
    if Shared_vars.TABBY:
        API_ENDPOINT_URL += "v1/completions"
    else:
        API_ENDPOINT_URL += "completion"

    def tokenize(input):
        payload = {
            "add_bos_token": "true",
            "encode_special_tokens": "true",
            "decode_special_tokens": "true",
            "text": input,
            "content": input,
        }
        request = requests.post(
            API_ENDPOINT_URL.replace("completions", "token/encode")
            if Shared_vars.TABBY
            else API_ENDPOINT_URL.replace("completion", "tokenize"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {Shared_vars.API_KEY}",
            },
            json=payload,
            timeout=360,
        )
        return (
            request.json()["length"]
            if Shared_vars.TABBY
            else len(request.json()["tokens"])
        )

    message = ""
    test_message = ""
    result_list = []

    for source in rss_sources:
        result_list += rss_news_get(source, results_per_source)

    for article in result_list:
        text = ""
        if article.get("title"):
            text = text + article.get("title") + "\n"
        if article.get("link"):
            text = text + "URL: " + article.get("link") + "\n"
        if article.get("summary"):
            text = text + article.get("summary") + "\n"

        # Add separator if this is the first result
        if len(message) > 0:
            test_message = message + "***\n"
        test_message += text

        # Prevent RAG content from taking up too much of the context
        if ctx_alloc == -1:
            message = test_message
        elif tokenize(test_message) < (Shared_vars.config.ctxlen * ctx_alloc):
            message = test_message
        else:
            break

    # Handle unsuccessful search
    if len(message) == 0:
        print("No search results")
        return "No search results received, please notify the user"

    print(message)
    return "<search_results>:\n" + message + "</search_results>"


if __name__ == "__main__":
    main(params, memory, infer, ip, Shared_vars)
