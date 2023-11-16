from utils.prompt_template_builder import PromptTemplateBuilder
from langchain.output_parsers import PydanticOutputParser
from auto_agents.action import Action
import sys,os

if __name__ == "__main__":
    # print("===========check path", os.path.exists('./brian_python/auto_demo/prompts/main.templ'))
    # print("===========print path", os.getcwd())

    ##### test build the template #####
    builder = PromptTemplateBuilder("./brian_python/auto_demo/prompts","main.templ")
    output_parser = PydanticOutputParser(pydantic_object=Action)
    prompt_template = builder.build(tools=[], output_parser=output_parser)
    print(prompt_template.format(
        ai_name="老陈",
        ai_role="智能助手机器人",
        task_description="解决问题",
        short_term_memory="",
        long_term_memory="",
        tools="",
        work_dir="./brian_python/auto_demo/data"
    ))