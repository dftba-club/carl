import signal
import time
import logging, sys
import os
from mastodon import Mastodon
import feedparser

class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self,signum, frame):
        self.kill_now = True

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    killer = GracefulKiller()

    VERSION = '1.1'

    # Echo version
    logging.info("Mastodon YT & Podcast Notifier Bot Version " + VERSION)
    logging.info("https://github.com/nomad-geek/tuberbot")

    # Env Vars
    SERVER_URL = os.getenv('SERVER_URL')
    BOT_NAME = os.getenv('BOT_NAME')
    CLIENT_KEY = os.getenv('CLIENT_KEY')
    CLIENT_SECRET = os.getenv('CLIENT_SECRET')
    ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
    YT_URL = os.getenv('YT_URL')
    POD_URL = os.getenv('POD_URL')
    DELAY = int(os.getenv('DELAY')) * 60
    GROUP_NAME = os.getenv('GROUP_NAME')
    OWNER = os.getenv('OWNER')

    # Register us with the server
    Mastodon.create_app(BOT_NAME, api_base_url = SERVER_URL)

    # initialize Client
    mastodon = Mastodon(api_base_url = SERVER_URL, access_token = ACCESS_TOKEN)

    # init ID vars
    currentYT = ''
    currentPD = ''

    # Get initial IDs so we know when there's a new one
    logging.info("Initializing YouTube Feed..")
    x = feedparser.parse(YT_URL)
    currentYT = x.entries[0].id
    logging.info("  Current Video ID is " + currentYT)

    logging.info("Initializing Podcast Feed..")
    x = feedparser.parse(POD_URL)
    currentPD = x.entries[0].id
    logging.info("  Current Pod ID is " + currentPD)

    # Messaging
    messageYT = "A new " + GROUP_NAME + " video has been posted!"
    messagePD = "A new " + GROUP_NAME + " podcast has been posted!"

    # Check in with owner
    logging.info("Checking in with owner..")
    mastodon.status_post("I'm online @" + OWNER, visibility='direct')

    logging.info("Starting application loop..")
    while True:
        # Check if we should quit
        if killer.kill_now:
            break
        # Check for new videos
        logging.info("Checking for new Videos..")
        x = feedparser.parse(YT_URL)
        y = x.entries[0].id
        z = x.entries[0].link
        if y != currentYT:
            currentYT = y
            logging.info("Found new video!")
            mastodon.status_post(messageYT + ' ' + z)
        # Check for new podcasts
        logging.info("Checking for new Podcasts..")
        x = feedparser.parse(POD_URL)
        y = x.entries[0].id
        z = x.entries[0].link
        if y != currentPD:
            currentPD = y
            logging.info("Found new podcast!")
            mastodon.status_post(messagePD + ' ' + z)
        # Start the sleep loop
        logging.info("Checking Loop Complete. Zzzz..")
        for number in range(DELAY):
            time.sleep(1)
            if killer.kill_now:
                break

    logging.info("End of the program. I was killed gracefully :)")