import os
import time
import schedule
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

#no need for app token
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN_WATER")
CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")  # The channel or user ID to send messages to

#initialize slack 
client = WebClient(token=SLACK_BOT_TOKEN)

test_response = client.auth_test()
print(test_response)


def send_reminder():
    #sends the reminder to a particular channel
    try:
        response = client.chat_postMessage(
            channel= CHANNEL_ID,
            text = "Stay hydrated! Time to drink some water"
        )
        print("Reminder successfull",response["ts"])

    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

'''def get_all_channels():
    #to get all channels
    try:
        response = client.conversations_list()
        channels = response["channels"]

        return [channel["ID"] for channel in channels if channel["is_member"]]
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

def send_to_all():
    channels = get_all_channels()
    for channel in channels:
        try:
            response = client.chat_postMessage(
            channel= CHANNEL_ID,
            text = "Stay hydrated! Time to drink some water"
        )
            print("Reminder successfull",response["ts"])
        except  SlackApiError as e:
            print(f"Error sending message: {e.response['error']}")
'''

#schedule the reminder for every hour:
#schedule.every().hour.do(send_reminder)

#every 20 seconds
schedule.every(20).seconds.do(send_reminder)

if __name__ == '__main__':
    print("Slack Water reminder bot is running ")

    while True:
        schedule.run_pending()
        time.sleep(20) #checks for something new  to run every minute (prevents excessive CPU usage)