import os
from urllib import response
import openai
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  #searches for .env file with api keys and automatically reads it

app = Flask(__name__)

#api_key = os.getenv("OPEN_API_KEY")
#print(api_key)

key=open("api_key.txt",'r').read()
openai.api_key = key


#opeani = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_content(url):  #extract content from url

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parse")
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        return text[:5000]  #limit the response length
    
    except Exception as e:
        return f"Error extracting content {e}"
    
def summarize_text(text):  #pass to llm

    try:

        messages = [{'role':'user','content':'You are a helpful assistant'},
                    {'role':'user','content':f'Summarize this text {text}'}]   #add more nuance
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        return response.choices[0].message.content
    
    except Exception as e:
        return f"Error summarizing content {e}"
    
@app.route("/summarize",methods=["POST"])

def summarize():
    data=request.json
    url=data.get("url")

    if not url or not url.startswith("http"):
        return jsonify({"error: ":"Invalid url"}),400
    
    content = extract_content(url)

    if len(content) <50:
        return jsonify({"error: ":"Content too short to summarize"}),400
    
    summary = summarize_text(content)
    return jsonify({"summary:":summary})

if __name__ == '__main__':
    app.run(port=5000,debug = True)
        

