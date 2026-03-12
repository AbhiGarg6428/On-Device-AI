import os
import webbrowser
import urllib.parse
import pyttsx3
import ast
import operator
import logging

from tools import app_resolver

logger = logging.getLogger(__name__)


class ToolPlugin:
    """Base class for all tools in the plugin system."""

    def __init__(self, name, description, parameters):
        self.name = name
        self.description = description
        self.parameters = parameters

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def execute(self, value):
        raise NotImplementedError()


# ---------------- SPEAK TOOL ----------------

class SpeakTool(ToolPlugin):

    def __init__(self):
        super().__init__("speak", "Speaks text aloud.", ["text"])
        self.engine = pyttsx3.init()

    def execute(self, value):
        if not value:
            return
        print("AI:", value)
        try:
            self.engine.say(str(value))
            self.engine.runAndWait()
        except Exception as e:
            logger.error(f"TTS Error: {e}")


# ---------------- OPEN APP ----------------

class OpenAppTool(ToolPlugin):

    def __init__(self):
        super().__init__("open_app", "Opens an application.", ["app_name"])

    def execute(self, value):
        try:
            app = app_resolver.resolve_app(str(value))

            if os.path.exists(app):
                os.startfile(app)
            else:
                os.system(f'start "" "{app}"')

            return f"Opening {value}"

        except Exception as e:
            logger.error(f"OpenApp Error: {e}")
            return "Failed to open application"


# ---------------- OPEN URL ----------------

class OpenUrlTool(ToolPlugin):

    def __init__(self):
        super().__init__("open_url", "Opens a URL.", ["url"])

    def execute(self, value):
        webbrowser.open(str(value))


# ---------------- PLAY ----------------

class PlayTool(ToolPlugin):

    def __init__(self):
        super().__init__("play", "Play something on YouTube.", ["query"])

    def execute(self, value):
        query = str(value) if value else "music"
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        webbrowser.open(url)


# ---------------- SEARCH ----------------

class SearchTool(ToolPlugin):

    def __init__(self):
        super().__init__("search", "Search Google.", ["query"])

    def execute(self, value):
        url = f"https://www.google.com/search?q={urllib.parse.quote(str(value))}"
        webbrowser.open(url)


# ---------------- CALCULATOR ----------------

class CalcTool(ToolPlugin):

    def __init__(self):
        super().__init__("calc", "Perform math calculations.", ["expression"])

        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

    def safe_eval(self, node):

        if isinstance(node, ast.Num):
            return node.n

        elif isinstance(node, ast.BinOp):
            return self.operators[type(node.op)](
                self.safe_eval(node.left), self.safe_eval(node.right)
            )

        elif isinstance(node, ast.UnaryOp):
            return self.operators[type(node.op)](
                self.safe_eval(node.operand)
            )

        else:
            raise TypeError(node)

    def execute(self, value):

        try:
            expr = str(value).replace("^", "**")
            node = ast.parse(expr, mode="eval").body
            result = self.safe_eval(node)

            return f"The result is {result}"

        except Exception as e:
            logger.error(f"Calc error: {e}")
            return "Invalid calculation"


# ---------------- TOOL MANAGER ----------------

class ToolManager:

    def __init__(self):

        self.tools = {}
        self.register_builtin()

    def register_builtin(self):

        self.register(SpeakTool())
        self.register(OpenAppTool())
        self.register(OpenUrlTool())
        self.register(PlayTool())
        self.register(SearchTool())
        self.register(CalcTool())

    def register(self, tool):

        self.tools[tool.name] = tool

    def get_tool_schemas(self):

        return [t.get_schema() for t in self.tools.values()]

    def execute(self, action, value):

        if action in self.tools:
            return self.tools[action].execute(value)

        logger.warning(f"Unknown tool: {action}")
        return None