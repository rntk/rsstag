class Stopwords:
    def __init__(self):
        self.__stopwords = {
            "russian": [],
            "english": []
        }

    def words(self, lang):
        """
        Returns the stopwords for the specified language.
        """
        if lang not in self.__stopwords:
            raise ValueError(f"Language '{lang}' not supported.")
        
        return self.__stopwords[lang]
    
stopwords = Stopwords()