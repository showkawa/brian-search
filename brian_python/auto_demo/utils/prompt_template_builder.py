from langchain.prompts.prompt import PromptTemplate
from typing import List, Optional
from langchain.tools.base import BaseTool
from langchain.schema.output_parser import BaseOutputParser
from .file_utils import load_file

import os, json

def chinese_friendly(string) -> str:
    lines = string.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('{') and line.endswith('}'):
            try:
                lines[i] = json.dumps(json.loads(line), ensure_ascii=False)
            except:
                pass
    return '\n'.join(lines)


class PromptTemplateBuilder:
    def __init__(
            self,
            prompt_path: str,
            prompt_file: str
            ):
        self.prompt_path = prompt_path
        self.prompt_file = prompt_file

    def _get_prompt(self, prompt_file):
        builder = PromptTemplateBuilder(self.prompt_path, prompt_file)
        return builder.build().format()
    
    def _get_tools_prompt(self, tools: List[BaseTool]) -> str:
        tools_prompt = ""
        for i, tool in  enumerate(tools):
            prompt = f"{i+1}. {tool.name}: {tool.description}, \
                arg json schema: {json.dump(tool.args, ensure_ascii=False)}\n"
            tools_prompt += prompt
        return tools_prompt

    def build(
            self,
            tools: Optional[List[BaseTool]] = None,
            output_parser: Optional[BaseOutputParser] = None
            ) -> PromptTemplate:
        main_templ_str = load_file(os.path.join(self.prompt_path, self.prompt_file))
        main_templ = PromptTemplate.from_template(main_templ_str)

        variables = main_templ.input_variables
        partial_variables = {}
        #遍历所有变量，如果变量以_templ结尾，读取对应的文件数据，将文件内容作为变量的值
        for var in variables:
            if var.endswith('_templ'):
                var_file = var[:-6] + ".templ"
                var_str = self._get_prompt(var_file)
                partial_variables[var]=var_str

        if tools is not None:
            tools_prompt = self._get_tools_prompt(tools)
            partial_variables["tools"] = tools_prompt

        if output_parser is not None:
            partial_variables["format_instructions"] = chinese_friendly(
                output_parser.get_format_instructions()
            )

        #将有值的变量填充到模板中    
        return main_templ.partial(**partial_variables)
