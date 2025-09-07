class Stopwords:
    def __init__(self):
        self.__stopwords = {
            "russian": [
                "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все", "она", "так", "его",
                "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только", "ее", "мне", "было", "вот", "от",
                "до", "это", "быть", "сейчас", "всего", "него", "если", "или", "ни", "были", "его", "тут", "где", "есть",
                "эт", "для"
            ],
            "english": [
                "the", "and", "is", "in", "to", "of", "a", "that", "it", "on", "for", "with", "as", "was", "at", "by", "an",
                "be", "this", "from", "or", "which", "but", "not", "are", "have", "has", "they", "you", "all", "we",
            ],
        }

    def words(self, lang):
        """
        Returns the stopwords for the specified language.
        """
        if lang not in self.__stopwords:
            raise ValueError(f"Language '{lang}' not supported.")
        
        return self.__stopwords[lang]
    
stopwords = Stopwords()