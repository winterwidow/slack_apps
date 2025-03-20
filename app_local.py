from flask import Flask, request, jsonify
import os
import trafilatura
from langchain_openai import ChatOpenAI  
from langchain.chains import LLMChain  
from langchain_core.prompts import PromptTemplate  
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from dotenv import load_dotenv
import json

#if using .env files
load_dotenv()

#api key
with open("api_key.txt", 'r') as file:
    OPENAI_API_KEY = file.read().strip()

#initialize Flask
flask_app = Flask(__name__)

#langchain output parsing
summary_schema = ResponseSchema(name="summary", description="Short summary of the content.")
keywords_schema = ResponseSchema(name="keywords", description="List of up to 10 keywords.", type="array(string)")
response_schemas = [summary_schema, keywords_schema]
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

#prompt
template = """
Your task is to summarize the given content and extract keywords.
1. Generate a short summary of 120 to 150 words.
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
chain = LLMChain(llm=llm_openai, prompt=prompt)

def summarize_url(url):  #to summarize the text
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded) if downloaded else ""

    if not text:
        print("Error: Could not extract content from the URL.")
        return

    # Use `.invoke()` and extract the actual text response
    response = chain.invoke({"content": text[:3500]})

    if not response or "text" not in response or not response["text"].strip():
        print("Error: OpenAI returned an empty response.")
        return

    try:
        parsed_response = output_parser.parse(response["text"])

        summary = parsed_response.get("summary", "No summary available.")
        keywords = ", ".join(parsed_response.get("keywords", []))

        print("\n Summary:\n", summary)
        print("\n Keywords:\n", keywords)

    except (json.JSONDecodeError, KeyError):
        print(f"Error: Failed to parse OpenAI response. {str(e)}")
        print("Error: OpenAI returned an invalid response. Check the API output.")


if __name__ == "__main__":
    url = input("Enter a URL to summarize: ").strip()
    
    if url:
        summarize_url(url)
    else:
        print("Please enter a valid URL.")
