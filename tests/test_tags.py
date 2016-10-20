import unittest
from rsstag.tags import RssTagTags
from pymongo import MongoClient

class TestHTMLCleaner(unittest.TestCase):

    def test_cahnge_unread(self):
        cl = MongoClient('127.0.0.1', 8888)
        db = cl.test
        tags_number = 5
        tags_data = []
        tags_update = {}
        unread_count = 10
        inc_value = 5
        for i in range(tags_number):
            tag = 'test' + str(i)
            tags_data.append({
                'owner': 'test',
                'tag': tag,
                'unread_count': unread_count
            })
            tags_update[tag] = inc_value

        readed = True
        db.tags.delete_many({})
        self.assertEqual(0, db.tags.count({}))
        db.tags.insert_many(tags_data)
        for tag in tags_data:
            db_data = db.tags.find_one({'owner': tag['owner'], 'tag': tag['tag']})
            tag['_id'] = db_data['_id']
            self.assertEqual(tag, db_data)

        tags = RssTagTags(db)
        tags.change_unread(tags_data[0]['owner'], tags_update, readed)
        for tag in tags_data:
            db_data = db.tags.find_one({'owner': tag['owner'], 'tag': tag['tag']})
            tag['unread_count'] -= inc_value
            tag['_id'] = db_data['_id']
            self.assertEqual(tag, db_data)


if __name__ == '__main__':
    unittest.main()
