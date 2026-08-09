import signal
import time
import logging
import sys
import os
import shlex
import re
from mastodon import Mastodon
import feedparser

class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True

import shlex
import re
import logging

def parse_command(message, bot_name):
    if not message.strip():
        return None, None  # Handle empty message case

    # Remove HTML tags using a regular expression
    message = re.sub(r'<[^>]+>', '', message)  # Strip HTML tags
    logging.debug("MSG: " + message)
    # Use shlex to handle quoted strings. User-generated Mastodon posts aren't
    # guaranteed to have balanced quotes (e.g. a stray apostrophe like "wasn't"),
    # which makes shlex.split raise ValueError -- treat that as "not a command"
    # instead of letting it crash the whole notification loop.
    try:
        parts = shlex.split(message)
    except ValueError as e:
        logging.debug(f"Could not parse message as a command ({e}): {message}")
        return None, None

    if not parts:
        return None, None  # Nothing left after stripping tags/whitespace

    # Check if the first part is the bot's name
    if parts[0].lower() != '@' + bot_name.lower():
        logging.info(f"Message does not start with my name: {bot_name} / {parts[0]}")
        return None, None  # Do nothing if the first var is not the bot's name

    # Extract command and parameters
    command = parts[1].lower() if len(parts) > 1 else None
    parameters = ' '.join(parts[2:]).strip() if len(parts) > 2 else ''
    return command, parameters

def handle_command(mastodon, staff, command, parameters, username):
    """Handle commands received from users."""
    if username == OWNER:
        user_role = 'OWNER'
    elif username in STAFF:
        user_role = 'STAFF'
    #elif member:
        #user_role = 'MEMBER'
    else:
        user_role = 'PUBLIC'

    if command in command_permissions:
        allowed_roles = command_permissions[command]
        if user_role in allowed_roles:
            # Execute the command
            if command == "say":
                # Post the message with privacy setting of Followers
                mastodon.status_post(parameters, visibility='public')
                logging.info(f"Posted message from {username}: {parameters}")
        else:
            logging.info(f"User {username} is not allowed to use the command '{command}'.")
    else:
        logging.info(f"Command '{command}' is not recognized.")

# Define command permissions
command_permissions = {
    "say": ["OWNER"],
}

def build_post(header, title, url):
    """Assemble a toot: announcement, title, and link, each on its own line."""
    parts = [header]
    if title:
        parts.append(title)
    parts.append(url)
    return '\n\n'.join(parts)

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    killer = GracefulKiller()

    VERSION = '2.2'

    # Echo version
    logging.info("Mastodon YT & Podcast Notifier Bot Version " + VERSION)
    logging.info("https://github.com/dftba-club/carl")

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
    STAFFC = os.getenv('STAFF')

    if STAFFC is not None:
        STAFF = STAFFC.split(',')

    # Register us with the server
    Mastodon.create_app(BOT_NAME, api_base_url=SERVER_URL)

    # Initialize Client
    mastodon = Mastodon(api_base_url=SERVER_URL, access_token=ACCESS_TOKEN)

    # Init ID vars
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
    #mastodon.status_post("I'm online @" + OWNER, visibility='direct')
    last_execution_time = 0
    logging.info("Starting application loop..")
    while True:
        current_time = time.time()
        try:
            # CHECK FOR NOTIFICATIONS ON LOOP
            logging.debug("Checking for new DMs..")
            notifications = mastodon.notifications()
            for notification in notifications:
                try:
                    if notification['type'] == 'mention':
                        username = notification['account']['username']
                        message = notification['status']['content']
                        command, parameters = parse_command(message, BOT_NAME)
                        if command != None:
                            handle_command(mastodon, STAFF, command, parameters, username)
                    else:
                        logging.debug("Ignoring notif type: " + notification['type'])
                except Exception as e:
                    # Never let one bad notification block notifications_clear() below --
                    # that used to strand the whole batch and get it re-processed (and
                    # re-crashed on) forever, blocking feed posting along with it.
                    logging.info(f"Error handling notification {notification.get('id')}: {e}")
            mastodon.notifications_clear()


            # FETCH FEEDS ON DELAY
            if current_time - last_execution_time >= DELAY:
                # Check if we should quit
                if killer.kill_now:
                    break
                
                # Check for new videos
                logging.info("Checking for new Videos..")
                x = feedparser.parse(YT_URL)
                y = x.entries[0].id
                z = x.entries[0].link
                t = x.entries[0].get('title', '')
                if y != currentYT:
                    currentYT = y
                    logging.info("Found new video: " + t)
                    mastodon.status_post(build_post(messageYT, t, z))

                # Check for new podcasts
                logging.info("Checking for new Podcasts..")
                x = feedparser.parse(POD_URL)
                y = x.entries[0].id
                z = x.entries[0].enclosures[0].href
                t = x.entries[0].get('title', '')
                if y != currentPD:
                    currentPD = y
                    logging.info("Found new podcast: " + t)
                    mastodon.status_post(build_post(messagePD, t, z))
                last_execution_time = current_time
                logging.info("Update loop complete.")
            time.sleep(20)
        except Exception as e:
            logging.info(f"Exception not handled: {e}. I'm dying!")
            time.sleep(10)

    logging.info("End of the program.")
