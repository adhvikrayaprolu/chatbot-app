from openai import OpenAI

api_key="..."

client = OpenAI(api_key=api_key)

conversation_history = [
    {
        "role": "system", 
        "content": ("You are a helpful assistant."
                    "You respond clearly to user queries, and when appropriate, you format your responses using markdown. "
                    "Always answer politely and informatively.")
    }
]

def get_response(user_input):
    global conversation_history

    formatted_input = f"""You are given a user prompt delimited by triple backticks. 
    Everytime the user asks about football give the user 3 examples of football players as a list in a json format with the following keys: name, age, nationality, total goals.
    ```{user_input}```
    """

    conversation_history.append({"role": "user", "content": formatted_input})
    # append the text from the pdf

    try: 
        response = client.chat.completions.create(
            model = "gpt-4.1-mini",
            messages = conversation_history,
            temperature = 0.7
        )
    except Exception as e: 
        print("error calling OpenAI API:", e)
        return "There was an error processing your request."

    assistant_reply = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": assistant_reply})

    return assistant_reply