from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import  SystemMessage,HumanMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks import get_openai_callback
import streamlit as st

# load env
load_dotenv()
st.title("Update The Blog")
blog_prompt = st.text_input("what's your blog?")

# Prompt templates
blog_template = PromptTemplate(
    input_variables = ['content'], 
    template='{content}'
)


chat = ChatOpenAI(temperature=0.1, model_name="gpt-3.5-turbo-16k",
                 callbacks=[StreamingStdOutCallbackHandler()],verbose=True)


with get_openai_callback() as cb:
    res= chat([
        SystemMessage(content="Now you are a writer in the field of AI, mainly to review the content of the blog I submitted to you, I need you to do some optimization, such as removing the repeated parts in the content, and then rearranging the layout in a reasonable order, but in the content I gave you Do not make any changes to the content in content [],最后请记住用中文回答，用户的提问"),
        HumanMessage(content=blog_prompt)
    ])
    print(f"""
        total_tokens: {cb.total_tokens}
        prompt_tokens: {cb.prompt_tokens}
        completion_tokens: {cb.completion_tokens}
        successful_requests: {cb.successful_requests}
        total_cost: {cb.total_cost}
        """)





if blog_prompt: 
    reply = res.content

    with st.expander("New Blog"):
        st.info(reply)