import os
import time
import re
from slackclient import SlackClient
from sheetclient import SheetClient

import pprint
pp = pprint.PrettyPrinter(indent=4)
import random

if "SHEET_ID" not in os.environ:
    print("Run \"export SHEET_ID = \'<your google sheet Id>\'\" first")
    exit()

if "SLACK_BOT_TOKEN" not in os.environ:
    print("Run \"export SLACK_BOT_TOKEN = \'<your slackbot token>\'\" first")
    exit()

sheet_id = os.environ.get("SHEET_ID")
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")

sheet_client = SheetClient(sheet_id)

# instantiate Slack client
slack_client = SlackClient(slack_bot_token)
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

RTM_READ_DELAY = 0.01 # 0.1 second delay between reading from RTM
MAX_LENGTH = 128
MAX_NUMBER_OF_REGEXES = 100

compiled_regex_list = []

def load_regexes():
    global compiled_regex_list
    compiled_regex_list = []
    sheet_client.clear_status()
    raw_regex_list = sheet_client.get_regexes()
    regex_dict = {}
    compiled_regex_count = 0
    for i, row in enumerate(raw_regex_list):
        sheet_client.update_status(i + 2, "Checking")
        message = "Accepted"
        if compiled_regex_count > MAX_NUMBER_OF_REGEXES:
            message = "Too many regexes in sheet"
        if len(row) >= 2 and len(row[0].strip()) == 0 and len(row[1].strip()) == 0:
            message = ""
        elif len(row) < 2 or len(row[0].strip()) == 0 or len(row[1].strip()) == 0:
            message = "Empty Cell"
        elif len(row[0].strip()) > MAX_LENGTH or len(row[1].strip()) > MAX_LENGTH:
            message = "Regex too long: " + str(len(row[0].strip())) + ", " + str(len(row[1].strip())) + ", maximum is " + str(MAX_LENGTH)
        else:
            source_regex = row[0].strip()
            destination_regex = row[1].strip()
            try:
                compiled_regex = re.compile(source_regex)
                if compiled_regex not in regex_dict:
                    regex_dict[compiled_regex] = []
                    compiled_regex_count += 1
                regex_dict[compiled_regex].append(destination_regex)
            except re.error as e:
                message = "Error compiling regex"
        sheet_client.update_status(i+2, message)
    for compiled_regex, destination_regexes in regex_dict.items():
        compiled_regex_list.append((compiled_regex, destination_regexes))

def handle_message(slack_event):
    message_text = slack_event["text"]
    message_channel = slack_event["channel"]
    if message_text == "<@" + str(starterbot_id) + "> reload":
        # If the exact message "@regexbot reload" is seen, then reload the regexes
        load_regexes()
        return

    for source_regex, destination_regexes in compiled_regex_list:
        try:
            if source_regex.search(message_text):
                new_message = re.sub(source_regex, random.choice(destination_regexes), message_text)

                slack_client.api_call(
                    "chat.postMessage",
                    channel=message_channel,
                    text=new_message
                )
                return
        except re.error as e:
            print("Error!", e)
            continue

def handle_next_events(slack_events):
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event and "text" in event:
            handle_message(event)

if __name__ == "__main__":
    print("Initialising regexes")
    load_regexes()

    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            handle_next_events(slack_client.rtm_read())
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
