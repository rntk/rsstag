from rsstag.wordnet import WordNetLabinform

def make_hypernyms():
    lab = WordNetLabinform('./data/wordnet/labinform.ru')
    lab.get_hypernyms('трава')

if __name__ == '__main__':
    make_hypernyms()