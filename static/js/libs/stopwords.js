"use strict"

const _stopwords = [
    "didn\'t", "при", "куда", "him", "этого", "you\'ll", "ни", "before", "было", "нет", "никогда", "что", "том", "во", "того", "my", "y", "s",
    "yours", "этом", "по", "эту", "m", "with", "сейчас", "три", "that\'ll", "ее", "даже", "то", "do", "меня", "вы", "yourselves", "shan", "we",
    "isn", "above", "тем", "со", "out", "ты", "всегда", "над", "тот", "what", "to", "хоть", "ничего", "yourself", "этой", "not", "себе", "own",
    "more", "где", "she\'s", "всю", "сам", "другой", "зачем", "by", "being", "всех", "be", "а", "ведь", "them", "здесь", "какой", "hadn\'t", "этот",
    "only", "раз", "o", "wasn", "myself", "моя", "вот", "нибудь", "nor", "wouldn", "можно", "mustn\'t", "она", "mightn\'t", "doesn\'t", "тоже", "конечно",
    "further", "им", "про", "hadn", "itself", "без", "they", "к", "themselves", "those", "его", "будто", "были", "aren\'t", "тебя", "ним", "your", "won",
    "надо", "еще", "wasn\'t", "shan\'t", "вам", "shouldn\'t", "few", "does", "почти", "he", "herself", "its", "into", "такой", "свою", "i", "ll", "once",
    "о", "needn", "are", "her", "all", "чтобы", "his", "теперь", "couldn", "whom", "same", "под", "again", "него", "too", "mightn", "weren\'t", "which",
    "don", "in", "won\'t", "более", "иногда", "why", "всего", "не", "мне", "just", "они", "перед", "кто", "hasn\'t", "below", "если", "между", "два",
    "you\'d", "for", "so", "себя", "himself", "that", "you\'ve", "чем", "у", "hers", "впрочем", "from", "under", "you", "но", "да", "haven\'t", "should",
    "did", "может", "и", "тут", "лучше", "только", "есть", "hasn", "some", "же", "или", "я", "was", "very", "так", "за", "ours", "both", "or", "couldn\'t",
    "isn\'t", "during", "the", "от", "had", "these", "having", "чуть", "с", "on", "один", "все", "of", "doesn", "будет", "should\'ve", "because", "он", "ve",
    "ourselves", "their", "на", "about", "ему", "until", "вдруг", "об", "ж", "их", "she", "and", "ней", "хорошо", "совсем", "разве", "них", "быть", "нее", "t",
    "был", "через", "потом", "нельзя", "shouldn", "чтоб", "through", "when", "as", "over", "how", "our", "between", "была", "here", "re", "me", "while", "it\'s",
    "than", "мы", "опять", "до", "ей", "a", "needn\'t", "чего", "вас", "после", "it", "been", "am", "up", "any", "больше", "theirs", "какая", "will", "down",
    "потому", "now", "в", "doing", "but", "weren", "aren", "wouldn\'t", "is", "have", "d", "this", "don\'t", "there", "mustn", "didn", "an", "where", "наконец",
    "has", "бы", "at", "no", "уже", "you\'re", "haven", "для", "against", "уж", "if", "then", "off", "много", "ain", "such", "were", "ma", "can", "other",
    "who", "из", "ли", "нас", "тогда", "most", "там", "как", "мой", "ну", "after", "each", "эти", "когда"
];

export function stopwords() {
    let s = new Set();
    for (let w of _stopwords) {
        s.add(w);
    }
    
    return s
}