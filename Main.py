import sqlite3
from sqlite3 import Error
from bs4 import BeautifulSoup as bs
import requests
import praw
import os
import json
import datetime

GET_REDDIT_ARTICLES = True  # (Main Function) Change this to True to load Reddit articles
PULL_WEBSITE_BIAS_DATA = False  # Change this to True to reload website bias data

DB_FILE = "data.sqlite"

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

CATEGORIES = [["https://mediabiasfactcheck.com/left/", "left"],  # do not change this
              ["https://mediabiasfactcheck.com/leftcenter/", "leftcenter"],
              ["https://mediabiasfactcheck.com/center/", "center"],
              ["https://mediabiasfactcheck.com/right-center/", "right-center"],
              ["https://mediabiasfactcheck.com/right/", "right"],
              ["https://mediabiasfactcheck.com/pro-science/", "pro-science"],
              ["https://mediabiasfactcheck.com/conspiracy/", "conspiracy"],
              ["https://mediabiasfactcheck.com/fake-news/", "fake-news"],
              ["https://mediabiasfactcheck.com/satire/", "satire"]]

# add desired subreddits to this list. Max 60/minute)
SUBREDDITS = ['the_donald','news','worldnews','politics']


# Load bias data from mediabiasfactcheck.com
def pull_website_bias_data(url, bias):
    soup = bs(requests.get(url).text, features="html.parser")
    table = soup.find(lambda tag: tag.name == 'table' and tag.has_attr('id') and tag['id'] == "mbfc-table")
    rows = table.findAll(lambda tag: tag.name == 'tr')
    urls = []
    for r in rows:
        text = r.findAll(text=True)
        for t in text:
            url = t[t.find("(") + 1:t.find(")")]
            if url != '':
                urls.append(url)
    try:
        conn = sqlite3.connect(DB_FILE)
        website_table = "CREATE TABLE IF NOT EXISTS websites (num INTEGER PRIMARY KEY AUTOINCREMENT, " \
                        "bias text NOT NULL, " \
                        "website text NOT NULL UNIQUE" \
                        ");"""
        conn.execute(website_table)
        conn.commit()
        for website in urls:
            try:
                conn.execute("INSERT or IGNORE INTO websites ("
                             "bias, "
                             "website)"
                             "VALUES (?,?)", (
                                 bias,
                                 website))
            except Error as e:
                print(e)
    except Error as e:
        print(e)
        exit()
    finally:
        conn.commit()
        conn.close()
        print(bias + " done")


def get_reddit_articles(access_inf, subreddit, time_filt, n_count):
    data = access_inf.subreddit(subreddit).top(limit=n_count, time_filter=time_filt)
    article_count = {'left': 0,
                     'leftcenter': 0,
                     'center': 0,
                     'right-center': 0,
                     'right': 0,
                     'pro-science': 0,
                     'conspiracy': 0,
                     'fake-news': 0,
                     'satire': 0,
                     'user-submitted': 0,
                     'unknown': 0}
    article_upvote_count = {'left': 0,
                            'leftcenter': 0,
                            'center': 0,
                            'right-center': 0,
                            'right': 0,
                            'pro-science': 0,
                            'conspiracy': 0,
                            'fake-news': 0,
                            'satire': 0,
                            'user-submitted': 0,
                            'unknown': 0}
    unknown = set()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for d in data:
            bias = (cursor.execute(
                "SELECT bias FROM websites WHERE website LIKE ?",
                ("%{}".format(d.domain),)).
                    fetchone())
            if bias is None:
                if str(d.domain).count(".") > 1:
                    first_removed = str(d.domain)[str(d.domain).find('.') + 1:]
                    bias = (cursor.execute(
                        "SELECT bias FROM websites WHERE website LIKE ?",
                        ("%{}".format(first_removed),)).
                            fetchone())
            if bias is None:
                article_count['unknown'] += 1
                article_upvote_count['unknown'] += d.ups
                unknown.add(d.domain)
            else:
                article_count[bias[0]] += 1
                article_upvote_count[bias[0]] += d.ups
        # TODO: Add saving and data-vis
        date_time = str(int(datetime.datetime.timestamp(datetime.datetime.now())))
        query_data = {'subreddit':subreddit,
                      'time_filter': time_filt,
                      'count': n_count,
                      'datetime': date_time,
                      'article_count':article_count,
                      'upvote_count':article_upvote_count}
        rel_path = os.path.join(__location__,f"subreddit/{subreddit}")
        if not os.path.exists(rel_path):
            os.makedirs(rel_path)
            print("here")
        print(rel_path)
        with open(os.path.join(rel_path,f"{date_time}.json"), 'w') as f:
            json.dump(query_data, f, indent=2)
    except Error as e:
        print(e)
    finally:
        conn.close()


if __name__ == '__main__':
    if PULL_WEBSITE_BIAS_DATA:
        for c in CATEGORIES:
            pull_website_bias_data(c[0], c[1])
    if GET_REDDIT_ARTICLES:
        access_info = praw.Reddit(client_id=os.environ['REDDIT_APP_BIAS_CHECK_USER'], #Insert your own values here
                                  client_secret=os.environ['REDDIT_APP_BIAS_CHECK_KEY'],
                                  username=os.environ['REDDIT_USER'],
                                  password=os.environ['REDDIT_PASSWORD'],
                                  user_agent=os.environ['REDDIT_USER'])
        for s in SUBREDDITS:
            get_reddit_articles(access_info, s, 'month', 50)
