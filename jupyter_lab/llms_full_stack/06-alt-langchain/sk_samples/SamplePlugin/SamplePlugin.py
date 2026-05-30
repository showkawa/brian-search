from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter
from semantic_kernel.orchestration.sk_context import SKContext
import json

class SamplePlugin:
    @sk_function(
        description="判断 Linux 命令是否有害",
        name="harmful_command",
        input_description="Linux 命令",
    )
    def harmful_command(self, context: SKContext) -> str:
        command = json.loads(context["input"])["command"]
        if command in ["rm", "kill", "shutdown"]:
            return "true"
        else:
            return "false" # 注意：返回值一定是字符串类型

    @sk_function(
        description="计算两个数的和",
        name="add",
    )
    @sk_function_context_parameter(  # 对参数的描述
        name="number1",
        description="第一个加数",
    )
    @sk_function_context_parameter(
        name="number2",
        description="第二个加数",
    )
    def add(self, context: SKContext) -> str: # 注意：所有入参出参，都是字符串
        return str(float(context["number1"]) + float(context["number2"]))