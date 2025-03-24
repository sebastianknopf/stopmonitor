from bs4 import BeautifulSoup

class TextSanitizer:

    def __init__(self):
        pass

    def sanitize(self, text: str) -> str:
        
        text = BeautifulSoup(text, "html.parser").get_text()

        text = text.replace('\n', '')
        text = text.replace('\r', '')

        return text