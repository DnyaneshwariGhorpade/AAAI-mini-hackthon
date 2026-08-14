from dotenv import load_dotenv
import os
from groq import Groq

#Load env file
load_dotenv()
#get api key
api_key=os.getenv("GROQ_API_KEY")

#create groq client
client=Groq(api_key=api_key)

query="What parameters i should consider while approving a loan of a customer"

#API call
response= client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role":"user","content":query}
    ]
)

#print answer
print(response.choices[0].message.content)