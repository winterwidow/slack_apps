from flask import Flask, request, jsonify
import os
import trafilatura
#from langchain.chat_models import ChatOpenAI
#from langchain_community.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate  
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.schema.runnable import RunnableLambda
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain.schema import AIMessage


#load environment variables
load_dotenv()
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

#key=open("api_key.txt",'r').read()
#OPENAI_API_KEY = key

#initialize flask and slack app
flask_app = Flask(__name__)
slack_app = App(token = SLACK_BOT_TOKEN)

#define langchain
summary_schema = ResponseSchema(name="Summary", description='Summary of the content')  #short summary
keywords_schema = ResponseSchema(name="keywords", description="List of upto 10keywords.", type="array(string)")
response_schemas = [summary_schema,keywords_schema]  #structures the AI response
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

#opeani prompt
template = """
Your task is to summarize the given content and extarct keywords.
1. Generate a short summary of length 120 to 150 words.
2. Extract upto 10 keywords
Content: '''{content}'''
{format_instructions} 
"""
#content is replaced with the webpage text

prompt = PromptTemplate(
    template = template,
    input_variables = ["content"],
    partial_variables = {"format_instructions" : output_parser.get_format_instructions()}
)

llm_openai = ChatOpenAI(temperature = 0.0, openai_api_key = OPENAI_API_KEY)  #temperature gives lower randomness of llm response (low: more factual, high: more creative/unpredictable)
#chain = LLMChain(llm = llm_openai, prompt = prompt)  #langchain connection to openai

chain = prompt | llm_openai | RunnableLambda(output_parser.parse)  #more recent method


@slack_app.command("/summarize")

def summarize(ack, respond, command):

    """Handles Slack command /summarize"""

    print("Received command:", command)  #debug

    ack()  #acknowledge the command
    url = command["text"]

    #validate URL
    if not url:
        respond("Please provide a valid URL to summarize.")
        return

    #extract text from webpage
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded) if downloaded else ""

    if not text:
        respond("Sorry, the content couldn't be extracted.")
        return

    # Use .invoke() to get a direct string output instead of AIMessage
    response = chain.invoke({"content": text[:3500]})

    # Check if the response is an AIMessage and extract text properly
    if isinstance(response, AIMessage):
        response_text = response.content 
    else:
        response_text = str(response)  
        
    print(f"Raw response: {response_text}")  #debug

    parsed_response = output_parser.parse(response_text)

    summary = parsed_response.get("summary", "No summary available.")
    keywords = ", ".join(parsed_response.get("keywords", []))

    #save to file
    output_file = "summary.txt"
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(f"Summary:\n{summary}\n\nKeywords:\n{keywords}")

    print(f"Responding with summary: {summary}")
    respond(f"Summary:\n{summary}\n\nKeywords:\n{keywords}")


@flask_app.route("/")
def home():  #debug - to check if server is running
    return "Slack Summarizer is running"

def main():  #starts the slack bot in socket mode
    handler = SocketModeHandler(slack_app,SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    from threading import Thread
    # Run Flask in a separate thread
    flask_thread = Thread(target=flask_app.run, kwargs={"host": "0.0.0.0", "port": 5000})
    flask_thread.start()
    
    main()