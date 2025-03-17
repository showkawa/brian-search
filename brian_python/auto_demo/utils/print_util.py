from colorama import init, Fore, Back, Style

THOUGHT_COLOR = Fore.GREEN
OBSERVATION_COLOR = Fore.YELLOW
def color_print(text, color=None):
    if color is not None:
        print(color + text + Style.RESET_ALL)
    else:
        print(text)