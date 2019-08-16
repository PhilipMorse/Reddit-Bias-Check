import sqlite3
from sqlite3 import Error
from bs4 import BeautifulSoup as bs
import requests
import praw
import os
import datetime
import csv
import glob
import numpy as np
import matplotlib.pyplot as plt

PULL_WEBSITE_BIAS_DATA = False  # Change this to True to reload website bias data
GET_REDDIT_ARTICLES = False  # (Main Function) Change this to True to load Reddit articles
ANALYZE_DATA = True

DB_FILE = "data.sqlite"

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

# PULL_WEBSITE_BIAS_DATA
# do not change this
CATEGORIES = [["https://mediabiasfactcheck.com/left/", "left"],
              ["https://mediabiasfactcheck.com/leftcenter/", "leftcenter"],
              ["https://mediabiasfactcheck.com/center/", "center"],
              ["https://mediabiasfactcheck.com/right-center/", "right-center"],
              ["https://mediabiasfactcheck.com/right/", "right"],
              ["https://mediabiasfactcheck.com/pro-science/", "pro-science"],
              ["https://mediabiasfactcheck.com/conspiracy/", "conspiracy"],
              ["https://mediabiasfactcheck.com/fake-news/", "fake-news"],
              ["https://mediabiasfactcheck.com/satire/", "satire"]]

# GET_REDDIT_ARTICLES
# add desired subreddits to this list. Max 60/minute)
SUBREDDITS = ['news',
              'worldnews',
              'politics',
              'the_donald',
              'worldpolitics',
              'business',
              'economics',
              'libertarian',
              'conservative',
              'sandersforpresident',
              'progressive',
              'the_mueller']
TIMEFRAME = 'day'
ARTICLE_COUNT = 100

# ANALYZE_DATA
TIMEFRAMES = ['hour', 'day', 'week', 'month', 'year', 'all']
PLOT_DATA = False


class SubredditData:
    def __init__(self, date, count, ups):
        self.date = date
        self.name = count[0]
        self.count = count
        self.ups = ups
        self.total_news_ups = 0
        self.news_ups_bias_value = 0
        self.news_ratio = 0

    def get_bias(self):
        for i in range(1, 6):
            self.total_news_ups += int(self.ups[i])
        self.news_ups_bias_value += int(self.ups[1]) * -1 / self.total_news_ups
        self.news_ups_bias_value += int(self.ups[2]) * -0.5 / self.total_news_ups
        self.news_ups_bias_value += int(self.ups[4]) * 0.5 / self.total_news_ups
        self.news_ups_bias_value += int(self.ups[5]) * 1 / self.total_news_ups
        self.news_ratio = (self.total_news_ups - int(self.ups[10])) / (self.total_news_ups + int(self.ups[10]))
        return self.name, float(self.news_ups_bias_value), float(self.news_ratio)


# Load bias data from mediabiasfactcheck.com and save to sql
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


# Pull articles from specified subreddit and save to csv
def get_reddit_articles(access_inf, subreddit, time_filt, n_count, date_time, dict_keys):
    data = access_inf.subreddit(subreddit).top(limit=n_count, time_filter=time_filt)
    article_count = dict_keys.copy()
    article_count['title'] = subreddit
    article_upvote_count = dict_keys.copy()
    article_upvote_count['title'] = subreddit
    unknown = set()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for d in data:
            if "self." in d.domain:
                article_count['user-submitted'] += 1
                article_upvote_count['user-submitted'] += d.ups
            else:
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

        ####################################################  OLD saving method
        # rel_path = os.path.join(__location__, f"subreddit/{subreddit}")
        # if not os.path.exists(rel_path):
        #    os.makedirs(rel_path)
        #
        # query_data = {'subreddit': subreddit,
        #              'time_filter': time_filt,
        #              'count': n_count,
        #              'datetime': date_time,
        #              'article_count': article_count,
        #              'upvote_count': article_upvote_count}
        # with open(os.path.join(rel_path, f"{date_time}.json"), 'w') as f:
        #    json.dump(query_data, f, indent=2)
        ####################################################

        with open(os.path.join(__location__, "unknown-websites.txt"), 'a') as file:
            file.write(str(unknown) + "\n")
        with open(os.path.join(__location__, f"csvs/{TIMEFRAME}-{date_time}-count.csv"), 'a', newline='') as file:
            writer_ups = csv.DictWriter(file, keys.keys())
            writer_ups.writerow(article_count)
        with open(os.path.join(__location__, f"csvs/{TIMEFRAME}-{date_time}-ups.csv"), 'a', newline='') as file:
            writer_ups = csv.DictWriter(file, keys.keys())
            writer_ups.writerow(article_upvote_count)
    except Error as e:
        print(e)
    finally:
        conn.close()


# Analyze csv data
def analyze_data(tf):
    for file in glob.glob(f'{tf}-*-count.csv'):
        datestring = file.title().split("-")[1]
        subreddits_data = [[], [], []]
        with open(f'{tf}-{datestring}-count.csv') as count_file:
            reader = csv.reader(count_file)
            next(reader)
            for line in reader:
                subreddits_data[0].append(line)
        with open(f'{tf}-{datestring}-ups.csv') as ups_file:
            reader = csv.reader(ups_file)
            next(reader)
            for line in reader:
                subreddits_data[1].append(line)
        for i, x in enumerate(subreddits_data[0]):
            sub = SubredditData(datestring, x, subreddits_data[1][i])
            subreddits_data[2].append(sub.get_bias())
        transposed_data = np.transpose(subreddits_data[2])
        with open(f"{tf}_exported_data.csv", 'a', newline='') as fi:
            w = csv.writer(fi, delimiter=',')
            w.writerows(transposed_data)
        if PLOT_DATA:
            for i, txt in enumerate(transposed_data[0]):
                x = float(transposed_data[1][i])
                y = float(transposed_data[2][i])
                plt.text(x, y, txt, fontsize=12)
                plt.plot(x, y, 'bo')
            plt.grid(True, which='both')
            plt.xlim((-1, 1))
            plt.ylim((-1, 1))
            plt.show()
        os.rename(f'{tf}-{datestring}-count.csv',f'analyzed/{tf}-{datestring}-count.csv')
        os.rename(f'{tf}-{datestring}-ups.csv',f'analyzed/{tf}-{datestring}-ups.csv')
        print(f'{tf}-{datestring} done')

if __name__ == '__main__':
    if PULL_WEBSITE_BIAS_DATA:
        for c in CATEGORIES:
            pull_website_bias_data(c[0], c[1])
    if GET_REDDIT_ARTICLES:
        access_info = praw.Reddit(client_id=os.environ['REDDIT_APP_BIAS_CHECK_USER'],  # Insert your own values here
                                  client_secret=os.environ['REDDIT_APP_BIAS_CHECK_KEY'],
                                  username=os.environ['REDDIT_USER'],
                                  password=os.environ['REDDIT_PASSWORD'],
                                  user_agent=os.environ['REDDIT_USER'])
        d_time = str(int(datetime.datetime.timestamp(datetime.datetime.now())))
        keys = {'title': 0,
                'left': 0,
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
        with open(os.path.join(__location__, f"csvs/{TIMEFRAME}-{d_time}-count.csv"), 'a', newline='') as f:
            writer = csv.DictWriter(f, keys.keys())
            writer.writeheader()
        with open(os.path.join(__location__, f"csvs/{TIMEFRAME}-{d_time}-ups.csv"), 'a', newline='') as f:
            writer = csv.DictWriter(f, keys.keys())
            writer.writeheader()
        for subs in SUBREDDITS:
            get_reddit_articles(access_info, subs, TIMEFRAME, ARTICLE_COUNT, d_time, keys)
            print(f"{subs} done")
    if ANALYZE_DATA:
        os.chdir(os.path.join(__location__, "csvs"))
        if not os.path.exists(os.path.join(os.getcwd(), "analyzed")):
            os.makedirs("analyzed")
        for time_frame in TIMEFRAMES:
            analyze_data(time_frame)
        os.chdir(os.path.join(__location__))
