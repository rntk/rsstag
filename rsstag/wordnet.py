import os
import logging
from typing import List
from collections import namedtuple, defaultdict
from xml.sax import parse, ContentHandler


class LabinformSenseHandler(ContentHandler):
    def __init__(self, **params):
        super().__init__(**params)
        self._data = {}
        self._log = logging.getLogger("SAX")

    def startElement(self, name, attrs) -> None:
        if name == "sense":
            lemma = ""
            try:
                lemma = attrs.getValue("lemma").casefold()
                self._data[lemma] = {
                    "id": attrs.getValue("id"),
                    "synset_id": attrs.getValue("synset_id"),
                }
            except Exception as e:
                self._log.error("Can`t handle %s %s", name, e)

            try:
                word = attrs.getValue("name").casefold()
                if word != lemma:
                    self._data[word] = {
                        "id": attrs.getValue("id"),
                        "synset_id": attrs.getValue("synset_id"),
                    }
            except Exception as e:
                self._log.error("Can`t handle %s %s", name, e)

    def get_data(self) -> dict:
        return self._data


class LabinformRelationHandler(ContentHandler):
    def __init__(self, **params):
        super().__init__(**params)
        self._data = defaultdict(lambda: {"childs": set(), "parents": set()})
        self._log = logging.getLogger("SAX")

    def startElement(self, name, attrs) -> None:
        if name == "relation":
            try:
                parent_id = attrs.getValue("parent_id")
                child_id = attrs.getValue("child_id")
                relation = attrs.getValue("name")
                self._data[parent_id]["childs"].add((child_id, relation))
                self._data[child_id]["parents"].add((parent_id, relation))
            except Exception as e:
                self._log.error("Can`t handle %s %s", name, e)

    def get_data(self) -> dict:
        return self._data


class LabinformSynsetHandler(ContentHandler):
    def __init__(self, **params):
        super().__init__(**params)
        self._data = defaultdict(lambda: set())
        self._log = logging.getLogger("SAX")
        self._synset_id = ""
        self._sense_started = False

    def startElement(self, name, attrs) -> None:
        if name == "synset":
            try:
                self._synset_id = attrs.getValue("id")
            except Exception as e:
                self._log.error("Can`t handle %s %s", name, e)
                self._synset_id = ""
        elif name == "sense":
            self._sense_started = True

    def endElement(self, name):
        if name == "synset":
            self._synset_id = ""
        elif name == "sense":
            self._sense_started = False

    def characters(self, content):
        if self._synset_id and self._sense_started:
            word = content.strip()
            if word:
                self._data[self._synset_id].add(word.casefold())

    def get_data(self) -> dict:
        return self._data


class WordNetLabinform:
    """
    Wordnet wrapper for dictionary from http://www.labinform.ru/pub/ruwordnet/index.htm
    """

    def __init__(self, directory: str):
        self._dir = directory
        self._data = {}
        POS = namedtuple("POS", ["adj", "noun", "verb"])
        self._pos = POS(adj="A", noun="N", verb="V")
        PosFiles = namedtuple("PosFiles", ["sense", "synset", "relation"])
        self._files = PosFiles(
            sense="senses", relation="synset_relations", synset="synsets"
        )
        self._ext = "xml"
        self._senses = {}
        self._relations = {}
        self._synsets = {}
        Relations = namedtuple(
            "Relations",
            [
                "derivational",
                "part_holonym",
                "hypernym",
                "hyponym",
                "antonym",
                "part_meronym",
                "instance_hypernym",
                "instance_hyponym",
            ],
        )
        """relations = (
            'derivational', 'part holonym', 'hypernym', 'hyponym',
            'antonym', 'part meronym', 'instance hypernym', 'instance hyponym'
        )"""
        self._relation_names = Relations(
            derivational="derivational",
            part_holonym="part holonym",
            hypernym="hypernym",
            hyponym="hyponym",
            antonym="antonym",
            part_meronym="part meronym",
            instance_hypernym="instance hypernym",
            instance_hyponym="instance hyponym",
        )
        self.build_vocab(self._dir)

    def _load_file(self, name: str, directory: str, handler) -> dict:
        data = {}
        for pos in self._pos:
            xml_name = os.path.join(
                os.path.abspath(directory), "{}.{}.{}".format(name, pos, self._ext)
            )
            parse(xml_name, handler)
            data.update(handler.get_data())

        return data

    def build_vocab(self, directory: str):
        handler = LabinformSenseHandler()
        self._senses = self._load_file(self._files.sense, directory, handler)
        del handler

        handler = LabinformRelationHandler()
        self._relations = self._load_file(self._files.relation, directory, handler)
        for synset_id in self._relations:
            self._relations[synset_id]["childs"] = tuple(
                sorted(self._relations[synset_id]["childs"], key=lambda el: el[0])
            )
            self._relations[synset_id]["parents"] = tuple(
                sorted(self._relations[synset_id]["parents"], key=lambda el: el[0])
            )
        del handler

        handler = LabinformSynsetHandler()
        self._synsets = self._load_file(self._files.synset, directory, handler)
        for synset_id in self._synsets:
            self._synsets[synset_id] = tuple(sorted(self._synsets[synset_id]))
        del handler

    def get_parents(self, word: str, chain: set = set()) -> List[str]:
        hypernyms = []
        if word in self._senses:
            synset_id = self._senses[word]["synset_id"]
            if self._relations[synset_id]["parents"]:
                for _id, rel in self._relations[synset_id]["parents"]:
                    if rel == self._relation_names.hypernym and _id not in chain:
                        chain.add(_id)
                        for syn_word in self._synsets[_id]:
                            if syn_word not in chain:
                                chain.add(syn_word)
                                hypernyms.append(syn_word)
                                hypernyms += self.get_parents(syn_word, chain)

        return hypernyms
