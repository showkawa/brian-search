from typing import List, Optional

from langchain.chat_models.base import BaseChatModel
from langchain.llms import BaseLLM
from langchain.memory import ConversationTokenBufferMemory, VectorStoreRetrieverMemory
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain.tools.base import BaseTool
from langchain.chains.llm import LLMChain
from langchain.vectorstores.base import VectorStoreRetriever
from pydantic import ValidationError

from action import Action
from utils.prompt_template_builder import PromptTemplateBuilder


class AutoGPT:
    """AutoGPT：基于Langchain实现"""

    def __init__(self,
                 llm: BaseLLM | BaseChatModel,
                 prompts_path: str,
                 tools: List[BaseTool],
                 work_dir: str = "./brian_python/auto_demo/data",
                 main_prompt_file: str = "main.templ",
                 final_prompt_file: str = "final.templ",
                 agent_name: Optional[str] = "老陈",
                 agent_role: Optional[str] = "强大的AI助手，可以使用工具与指令自动化解决问题",
                 max_thought_steps: Optional[int] = 10,
                 memery_retriever: Optional[VectorStoreRetriever] = None,
                 ):
        self.llm = llm
        self.prompts_path = prompts_path
        self.tools = tools
        self.work_dir = work_dir
        self.agent_name = agent_name
        self.agent_role = agent_role
        self.max_thought_steps = max_thought_steps
        self.memery_retriever = memery_retriever
        
        # OutputFixingParser： 如果输出格式不正确，尝试修复
        self.output_parser = PydanticOutputParser(pydantic_object=Action)
        self.robust_parser = OutputFixingParser.from_llm(parser=self.output_parser, llm=self.llm)

        self.main_prompt_file = main_prompt_file
        self.final_prompt_file = final_prompt_file
        
    def run(self, task_description, verbose=False) -> str:
        thought_step_count = 0 # 思考步数
        # 初始化模板
        prompt_template = PromptTemplateBuilder(
            self.prompts_path,
            self.main_prompt_file
        ).build(
            tools=self.tools,
            output_parser=self.output_parser,
        ).partial(
            work_dir=self.work_dir,
            ai_name=self.agent_name,
            ai_role=self.agent_role,
            task_description=task_description
        )
        
        # 短时记忆
        short_term_memory = ConversationTokenBufferMemory(
            llm=self.llm,
            ai_prefix="",
            human_prefix="",
            max_token_limit=16000
        )
        
        short_term_memory.save_context(
            {"input":"\n初始化"},
            {"output":"\n开始"}
        )
        
        # 初始化LLM链
        llm_chain = LLMChain(
            llm=self.llm,
            prompt=prompt_template
        )
        
        # 如果有长时记忆，加载长时记忆
        if self.memery_retriever is not None:
            long_term_memory = VectorStoreRetrieverMemory(
                retriever=self.memery_retriever,
            )
        else:
            long_term_memory = None
            
        # 本轮结束
        reply = ""
            