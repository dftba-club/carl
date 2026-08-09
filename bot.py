import signal
import socket
import time
import logging
import sys
import os
import shlex
import re
from urllib.parse import urlparse
from mastodon import Mastodon
import feedparser

VERSION = os.getenv('VERSION', 'dev')

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

def safe_log_text(text, limit=200):
    """Truncate and strip control characters before writing user-supplied text to logs."""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text or '')
    if len(text) > limit:
        text = text[:limit] + '…'
    return text


def parse_command(message, bot_name):
    if not message.strip():
        return None, None  # Handle empty message case

    # Remove HTML tags using a regular expression
    message = re.sub(r'<[^>]+>', '', message)  # Strip HTML tags
    logging.debug("MSG: " + safe_log_text(message))
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
        logging.info(f"Message does not start with my name: {bot_name} / {safe_log_text(parts[0])}")
        return None, None  # Do nothing if the first var is not the bot's name

    # Extract command and parameters
    command = parts[1].lower() if len(parts) > 1 else None
    parameters = ' '.join(parts[2:]).strip() if len(parts) > 2 else ''
    return command, parameters

def canonical_acct(identity, server_url):
    """Normalize a configured 'user@domain' identity to Mastodon's `acct` form.

    Mastodon reports `acct` as a bare username for local accounts and 'user@domain'
    for remote ones. Matching on the bare username alone would let a remote user with
    the same name impersonate the owner, so resolve the configured identity to
    whichever form Mastodon will actually report.
    """
    identity = identity.strip().strip('\'"').lstrip('@').lower()
    if '@' not in identity:
        return identity
    user, _, domain = identity.partition('@')
    local_domain = (urlparse(server_url).hostname or '').lower()
    return user if domain == local_domain else identity


def role_for(account, owner, staff, server_url):
    """Classify a notification's account as OWNER, STAFF, LOCAL, or PUBLIC (remote)."""
    acct = (account.get('acct') or '').lower()
    if acct and acct == canonical_acct(owner, server_url):
        return 'OWNER'
    if acct and any(acct == canonical_acct(s, server_url) for s in staff):
        return 'STAFF'
    if acct and '@' not in acct:
        return 'LOCAL'
    return 'PUBLIC'


def reply_safely(mastodon, status, text, key):
    """Reply to `status`, keyed for idempotency. Always passes spoiler_text='' so the
    reply never inherits the original status's Content Warning (Mastodon.py defaults to
    inheriting it when spoiler_text is None -- confirmed against its source), and never
    widens a private/direct message into a public 'unlisted' reply."""
    visibility = 'direct' if status.get('visibility') == 'direct' else 'unlisted'
    mastodon.status_reply(
        status, text,
        untag=True,
        visibility=visibility,
        spoiler_text='',
        idempotency_key=key,
    )


def sanitize_for_reply(text, limit=80):
    """Neutralize characters that would let attacker-supplied text be linkified, turned
    into an @-mention, or used to forge multi-line output when echoed back into a public
    reply (e.g. a search query). Not for use on trusted/authored content."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = text.replace('@', '(at)')
    text = re.sub(r'https?://', '', text, flags=re.IGNORECASE)
    text = text.strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + '…'
    return text


FEED_CACHE_TTL = 300  # seconds
_feed_cache = {}  # url -> (fetched_at, parsed_feed)


def cached_parse(url):
    """feedparser.parse() with a short TTL cache so repeated lastvideo/lastpod/search
    commands don't each trigger a fresh multi-MB feed download. The periodic
    new-item checker is unaffected -- it keeps calling feedparser.parse() directly,
    since it must see fresh data every DELAY tick regardless."""
    now = time.time()
    cached = _feed_cache.get(url)
    if cached and now - cached[0] < FEED_CACHE_TTL:
        return cached[1]
    parsed = feedparser.parse(url)
    _feed_cache[url] = (now, parsed)
    return parsed


COMMAND_COOLDOWN_SECONDS = 60
NETWORK_COMMANDS = {"lastvideo", "lastpod", "searchvideo", "searchpod"}
_last_command_time = {}  # acct -> timestamp


def rate_limited(acct):
    """True if `acct` used a network command within the cooldown window."""
    now = time.time()
    if now - _last_command_time.get(acct, 0) < COMMAND_COOLDOWN_SECONDS:
        return True
    _last_command_time[acct] = now
    return False


def handle_command(mastodon, command, parameters, account, status):
    """Handle commands received from users."""
    acct = (account.get('acct') or '').lower()
    user_role = role_for(account, OWNER, STAFF, SERVER_URL)

    if command in NETWORK_COMMANDS and user_role == 'LOCAL' and rate_limited(acct):
        reply_safely(mastodon, status, "You're doing that too fast — try again in a minute.",
                     f"cooldown-{status['id']}")
        logging.info(f"Rate-limited {command} from {acct}")
        return

    if command in command_permissions:
        allowed_roles = command_permissions[command]
        if user_role in allowed_roles:
            # Execute the command
            if command == "say":
                # Post the message with privacy setting of Followers
                mastodon.status_post(parameters, visibility='public',
                                      idempotency_key=f"say-{status['id']}")
                logging.info(f"Posted message from {acct}: {parameters}")
            elif command == "ping":
                reply_safely(mastodon, status, f"pong - {VERSION}", f"pong-{status['id']}")
                logging.info(f"Replied pong ({VERSION}) to {acct}")
            elif command == "lastvideo":
                x = cached_parse(YT_URL)
                entry = x.entries[0]
                text = build_post(f"Latest {GROUP_NAME} video:",
                                   entry.get('title', ''), entry.link)
                reply_safely(mastodon, status, text, f"lastvideo-{status['id']}")
                logging.info(f"Replied lastvideo to {acct}")
            elif command == "lastpod":
                x = cached_parse(POD_URL)
                entry = x.entries[0]
                text = build_post(f"Latest {GROUP_NAME} podcast:",
                                   entry.get('title', ''), entry.enclosures[0].href)
                reply_safely(mastodon, status, text, f"lastpod-{status['id']}")
                logging.info(f"Replied lastpod to {acct}")
            elif command in ("searchvideo", "searchpod"):
                if not parameters.strip():
                    text = f"Usage: @{BOT_NAME} {command} <search terms>"
                    result_count = 0
                else:
                    safe_query = sanitize_for_reply(parameters)
                    is_video = command == "searchvideo"
                    x = cached_parse(YT_URL if is_video else POD_URL)
                    matches = search_entries(x.entries, parameters)
                    result_count = len(matches)
                    kind = "video" if is_video else "podcast episode"
                    if not matches:
                        text = f'No {kind}s found matching "{safe_query}":'
                        if is_video:
                            text += "\n(only the 15 most recent videos are searchable)"
                    else:
                        header = (f'Found {result_count} {kind}'
                                  f'{"s" if result_count != 1 else ""} matching "{safe_query}":')
                        if is_video:
                            header += "\n(only the 15 most recent videos are searchable)"
                        results = [
                            (m.get('title', ''), m.link if is_video else m.enclosures[0].href)
                            for m in matches[:5]
                        ]
                        text = build_search_reply(header, results, result_count,
                                                   MAX_CHARS, URL_CHARS)
                reply_safely(mastodon, status, text, f"{command}-{status['id']}")
                logging.info(f"Replied {command} ({result_count} results) to {acct}")
        else:
            logging.info(f"User {acct} is not allowed to use the command '{command}'.")
    else:
        logging.info(f"Command '{command}' is not recognized.")

# Define command permissions
command_permissions = {
    "say": ["OWNER"],
    "ping": ["OWNER"],
    "lastpod": ["OWNER", "STAFF", "LOCAL"],
    "lastvideo": ["OWNER", "STAFF", "LOCAL"],
    "searchpod": ["OWNER", "STAFF", "LOCAL"],
    "searchvideo": ["OWNER", "STAFF", "LOCAL"],
}

def build_post(header, title, url):
    """Assemble a toot: announcement, title, and link, each on its own line."""
    parts = [header]
    if title:
        parts.append(title)
    parts.append(url)
    return '\n\n'.join(parts)


def strip_html(text):
    """Replace HTML tags with a space (not empty string) so stripped text doesn't glue
    adjacent words together, e.g. '...answers!<p>If' -> '...answers! If', not '...answers!If'."""
    return re.sub(r'<[^>]+>', ' ', text or '')


def search_entries(entries, query):
    """Every entry whose title or description contains `query` (case-insensitive
    substring), in feed order (most recent first)."""
    needle = query.strip().lower()
    matches = []
    for entry in entries:
        title = entry.get('title', '') or ''
        description = strip_html(entry.get('summary', '') or '')
        if needle in f"{title} {description}".lower():
            matches.append(entry)
    return matches


def estimate_length(text, url_chars):
    """Approximate how Mastodon counts a status's length: every http(s) URL counts as
    `url_chars` regardless of its real length. Not grapheme-cluster-exact (that needs the
    optional `grapheme` package Mastodon.py doesn't depend on) -- close enough for budgeting
    our own plain-text replies."""
    collapsed = re.sub(r'https?://\S+', 'x' * url_chars, text)
    return len(collapsed)


def build_search_reply(header, results, total_matches, max_chars, url_chars):
    """`results` is already capped to the top 5 matches as (title, url) pairs. Add them
    one at a time, stopping before exceeding max_chars (leaving room for the trailing
    note), and always report the true count remaining beyond what's shown."""
    lines = [header]
    shown = 0
    for i, (title, url) in enumerate(results, start=1):
        lines.append(f"{i}. {title}\n{url}")
        remaining = total_matches - i
        note = f"\n\n(+{remaining} more — refine your search)" if remaining else ''
        if estimate_length('\n\n'.join(lines) + note, url_chars) > max_chars:
            lines.pop()
            break
        shown = i
    remaining = total_matches - shown
    text = '\n\n'.join(lines)
    if remaining:
        text += f"\n\n(+{remaining} more — refine your search)"
    return text

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=os.getenv('LOG_LEVEL', 'INFO'))
    # Documented workaround for feedparser (which exposes no per-call timeout) --
    # also protects every Mastodon.py call in this process from hanging forever.
    socket.setdefaulttimeout(15)
    killer = GracefulKiller()

    # Echo version
    logging.info("Mastodon YT & Podcast Notifier Bot Version " + VERSION)
    logging.info("https://github.com/dftba-club/carl")

    # Env Vars
    SERVER_URL = os.getenv('SERVER_URL')
    BOT_NAME = os.getenv('BOT_NAME') or os.getenv('BOT_USER')
    ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
    YT_URL = os.getenv('YT_URL')
    POD_URL = os.getenv('POD_URL')
    DELAY = int(os.getenv('DELAY')) * 60
    GROUP_NAME = os.getenv('GROUP_NAME')
    OWNER = os.getenv('OWNER')
    STAFFC = os.getenv('STAFF')
    STAFF = STAFFC.split(',') if STAFFC else []

    # Initialize Client
    mastodon = Mastodon(api_base_url=SERVER_URL, access_token=ACCESS_TOKEN)

    # Look up this instance's real status-length limits once at startup, so search
    # replies can fit as many results as actually allowed instead of assuming Mastodon's
    # 500-char default.
    try:
        statuses_config = mastodon.instance()['configuration']['statuses']
        MAX_CHARS = statuses_config['max_characters']
        URL_CHARS = statuses_config['characters_reserved_per_url']
    except Exception as e:
        logging.info(f"Could not read instance status-length config ({e}), using Mastodon defaults")
        MAX_CHARS, URL_CHARS = 500, 23
    logging.info(f"Instance status limits: {MAX_CHARS} chars, URLs counted as {URL_CHARS}")

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
    last_notification_id = None
    logging.info("Starting application loop..")
    while True:
        current_time = time.time()
        try:
            # CHECK FOR NOTIFICATIONS ON LOOP
            logging.debug("Checking for new DMs..")
            notifications = mastodon.notifications(since_id=last_notification_id)
            for notification in notifications:
                try:
                    if notification['type'] == 'mention':
                        message = notification['status']['content']
                        command, parameters = parse_command(message, BOT_NAME)
                        if command != None:
                            handle_command(mastodon, command, parameters,
                                           notification['account'],
                                           notification['status'])
                    else:
                        logging.debug("Ignoring notif type: " + notification['type'])
                except Exception as e:
                    # Never let one bad notification block the dismiss below -- that
                    # used to strand the whole batch and get it re-processed (and
                    # re-crashed on) forever, blocking feed posting along with it.
                    logging.info(f"Error handling notification {notification.get('id')}: {e}")
                finally:
                    # Dismiss individually and track since_id, rather than the old
                    # blanket notifications_clear() -- that discarded anything beyond
                    # the fetched page or arriving mid-processing, letting a flood of
                    # mentions silently drop other users' (or the owner's) commands.
                    mastodon.notifications_dismiss(notification['id'])
                    nid = int(notification['id'])
                    if last_notification_id is None or nid > int(last_notification_id):
                        last_notification_id = notification['id']


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
                    logging.info("Found new video: " + t)
                    mastodon.status_post(build_post(messageYT, t, z))
                    currentYT = y

                # Check for new podcasts
                logging.info("Checking for new Podcasts..")
                x = feedparser.parse(POD_URL)
                y = x.entries[0].id
                z = x.entries[0].enclosures[0].href
                t = x.entries[0].get('title', '')
                if y != currentPD:
                    logging.info("Found new podcast: " + t)
                    mastodon.status_post(build_post(messagePD, t, z))
                    currentPD = y
                last_execution_time = current_time
                logging.info("Update loop complete.")
            time.sleep(20)
        except Exception as e:
            logging.info(f"Exception not handled: {e}. I'm dying!")
            time.sleep(10)

    logging.info("End of the program.")
