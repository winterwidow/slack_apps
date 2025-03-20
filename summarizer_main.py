from flask import Flask, request, jsonify
import os
import trafilatura
import re
import json
import threading
import requests
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate  
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.schema.runnable import RunnableLambda
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain.schema import AIMessage

# Load environment variables
load_dotenv()
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN_SUMMARIZE")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN_SUMMARIZE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize Flask app
flask_app = Flask(__name__)

# Initialize Slack app (handles all interactions)
slack_app = App(token=SLACK_BOT_TOKEN)

# 🔥 FIX: Handle Slack event subscription challenge
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    print("📢 In slack_events()")
    print("Headers:", request.headers)  # Debugging headers

    data = {}

    # Handle both JSON and form-encoded requests
    if request.content_type == "application/json":
        data = request.get_json()  # Extract JSON data
        print("JSON Data:", data)
    elif request.content_type == "application/x-www-form-urlencoded":
        data = request.form.to_dict()  # Convert form data to dictionary
        print("Form Data:", data)
    else:
        print("Unsupported Media Type:", request.content_type)
        return "Unsupported Media Type", 415  # Reject unknown formats

    # Handle Slack URL Verification (Required when first enabling Event Subscriptions)
    if "challenge" in data:
        print("Slack URL Verification Challenge Detected")
        return jsonify({"challenge": data["challenge"]})

    # Only Process `/summarizeurl`
    if "command" in data and data["command"] == "/summarizeurl":
        return handle_summarizeurl(data)

    # If it's an event (not a command), just acknowledge
    print("ℹIgnoring Non-Command Event")
    return jsonify({"status": "ignored"}), 200

def handle_summarizeurl(data):
    """Handles the /summarizeurl command from Slack"""
    print("Handling /summarizeurl command")

    raw_url = data.get("text", "").strip()
    url = clean_slack_url(raw_url)
    print(f"Extracted URL: {url}")

    if not url.startswith("http"):
        return jsonify({"response_type": "ephemeral", "text": "Please provide a valid URL."})

    # Slack requires an immediate response, so acknowledge first
    response_url = data.get("response_url")  # Get Slack's response URL
    threading.Thread(target=process_summarization, args=(url, response_url)).start()

    return jsonify({"response_type": "ephemeral", "text": "⏳ Processing summary... Please wait."})

def process_summarization(url, response_url):
    """Processes the URL, generates a summary, and sends it to Slack asynchronously"""
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded) if downloaded else ""

        if not text:
            error_msg = "Sorry, the content couldn't be extracted."
            print(f"{error_msg}")
            requests.post(response_url, json={"text": error_msg})
            return

        langchain_input = {"content": text[:3500]}
        print(f"LangChain Input: {langchain_input}")

        response = chain.invoke(langchain_input)

        print(f"🔥 Raw LangChain Response Type: {type(response)}")
        print(f"🔥 Raw LangChain Response: {response}")

        # ✅ FIX: Ensure response_text is a string before parsing
        if isinstance(response, dict):
            parsed_response = response  # ✅ Response is already a dictionary
        else:
            response_text = response.content if isinstance(response, AIMessage) else str(response)
            parsed_response = json.loads(response_text)  # ✅ Parse only if needed

        print(f"✅ Parsed Response: {parsed_response}")

        summary = parsed_response.get("Summary", "No summary available.")
        keywords = ", ".join(parsed_response.get("keywords", []))

        slack_response = {
            "response_type": "ephemeral",
            "text": f"*Summary:*\n{summary}\n\n*Keywords:*\n{keywords}"
        }
        print(f"✅ Sending Final Response to Slack: {slack_response}")

        requests.post(response_url, json=slack_response)  # ✅ Send final response asynchronously

    except Exception as e:
        error_msg = f"❌ Critical Error: {str(e)}"
        print(error_msg)
        requests.post(response_url, json={"text": error_msg})



# Define LangChain summary and keyword extraction
summary_schema = ResponseSchema(name="Summary", description='Summary of the content')  
keywords_schema = ResponseSchema(name="keywords", description="List of up to 10 keywords.", type="array(string)")
response_schemas = [summary_schema, keywords_schema]
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

# OpenAI prompt template
template = """
Your task is to summarize the given content and extract keywords.
1. Generate a short summary of length 120 to 150 words.
2. Extract up to 10 keywords.
Content: '''{content}'''
{format_instructions}
"""

prompt = PromptTemplate(
    template=template,
    input_variables=["content"],
    partial_variables={"format_instructions": output_parser.get_format_instructions()}
)

llm_openai = ChatOpenAI(temperature=0.0, openai_api_key=OPENAI_API_KEY)
chain = prompt | llm_openai | RunnableLambda(lambda msg: output_parser.parse(msg.content))


# 🔥 FIX: Slash Command Handler for `/summarize`
@slack_app.command("/summarizeurl")
def summarize(ack, respond, command):
    """Handles Slack command /summarize"""
    ack()  # ✅ Acknowledge the command immediately!

    url = command.get("text", "").strip()  # 🔥 FIX: Ensure URL is not None or empty

    if not url:
        respond("Please provide a valid URL to summarize.")
        return

    # Extract text from webpage
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded) if downloaded else ""

    if not text:
        respond("Sorry, the content couldn't be extracted.")
        return

    # Use LangChain to generate summary & keywords
    response = chain.invoke({"content": text[:3500]})

    # 🔥 FIX: Ensure response is parsed correctly
    if isinstance(response, AIMessage):
        response_text = response.content 
    else:
        response_text = str(response)

    print(f"Raw response: {response_text}")  # Debugging

    parsed_response = output_parser.parse(response_text)

    # 🔥 FIX: Use correct capitalization for `Summary`
    summary = parsed_response.get("Summary", "No summary available.")
    keywords = ", ".join(parsed_response.get("keywords", []))

    # 🔥 FIX: Send formatted response to Slack
    respond(f"*Summary:*\n{summary}\n\n*Keywords:*\n{keywords}")

# 🔥 FIX: Handle Slack App Mentions (e.g., `@SlackBot summarize URL`)
@slack_app.event("app_mention")
def handle_mention(event, say):
    """Handles @SlackBot mentions"""
    text = event.get("text", "").strip()
    
    if "/summarize" in text:
        say("You can use `/summarize <URL>` to summarize a webpage!")

# Debug route to check Flask status
@flask_app.route("/")
def home():
    return "Slack Summarizer is running"

def clean_slack_url(slack_text):
    """Extracts a clean URL from Slack's link formatting."""
    match = re.search(r'<(https?://[^|>]+)', slack_text)
    return match.group(1) if match else slack_text  # Return cleaned URL or original text

# Start Slack Bolt Socket Mode and Flask together
def main():
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    from threading import Thread
    # Run Flask in a separate thread
    flask_thread = Thread(target=flask_app.run, kwargs={"host": "0.0.0.0", "port": 5001})
    flask_thread.start()

    main()
