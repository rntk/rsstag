"""Post grouping functionality"""
import logging
from typing import Optional, List, Dict, Any
from pymongo import MongoClient
import gzip
import re
import hashlib
import colorsys
from rsstag.html_cleaner import HTMLCleaner


class RssTagPostGrouping:
    """Post grouping handler"""

    def __init__(self, db: MongoClient, llamacpp_handler=None) -> None:
        self._db: MongoClient = db
        self._log = logging.getLogger("post_grouping")
        self._llamacpp_handler = llamacpp_handler

    def prepare(self) -> None:
        """Create indexes for post_grouping collection"""
        try:
            self._db.post_grouping.create_index("owner")
            self._db.post_grouping.create_index("post_ids_hash")
            self._db.post_grouping.create_index([("owner", 1), ("post_ids_hash", 1)], unique=True)
        except Exception as e:
            self._log.warning("Can't create post_grouping indexes. May already exist. Info: %s", e)

    def get_grouped_posts(self, owner: str, post_ids: List[int]) -> Optional[dict]:
        """Get grouped posts data by owner and post IDs"""
        post_ids_hash = self._generate_post_ids_hash(post_ids)
        return self._db.post_grouping.find_one({
            "owner": owner,
            "post_ids_hash": post_ids_hash
        })

    def save_grouped_posts(self, owner: str, post_ids: List[int], 
                          sentences: List[dict], groups: Dict[str, List[int]], 
                          group_colors: Dict[str, str], feed_title: str) -> bool:
        """Save grouped posts data"""
        post_ids_hash = self._generate_post_ids_hash(post_ids)
        
        data = {
            "owner": owner,
            "post_ids": post_ids,
            "post_ids_hash": post_ids_hash,
            "sentences": sentences,
            "groups": groups,
            "group_colors": group_colors,
            "feed_title": feed_title,
            "processing": 0
        }
        
        try:
            self._db.post_grouping.update_one(
                {
                    "owner": owner,
                    "post_ids_hash": post_ids_hash
                },
                {
                    "$set": data
                },
                upsert=True
            )
            return True
        except Exception as e:
            self._log.error("Can't save grouped posts data. Info: %s", e)
            return False

    def _generate_post_ids_hash(self, post_ids: List[int]) -> str:
        """Generate a hash from post IDs for unique identification"""
        post_ids_sorted = sorted(post_ids)
        post_ids_str = ",".join(str(pid) for pid in post_ids_sorted)
        return hashlib.md5(post_ids_str.encode("utf-8")).hexdigest()

    def process_post_grouping(self, owner: str, posts: List[dict], feeds: List[dict]) -> Optional[bool]:
        """Process post grouping for given posts and save to DB"""
        try:
            if not posts:
                return True
            
            # Process each post individually
            for post in posts:
                post_ids = [post["pid"]]
                
                # Get feeds for this post
                post_feeds = [f for f in feeds if f["feed_id"] == post.get("feed_id")]
                
                # Process the post to generate grouped data
                result = self._generate_grouped_data(owner, [post], post_feeds)
                
                if result:
                    # Save the result
                    self.save_grouped_posts(owner, post_ids, 
                                          result["sentences"], 
                                          result["groups"], 
                                          result["group_colors"], 
                                          result["feed_title"])
            
            return True
            
        except Exception as e:
            self._log.error("Error processing post grouping. Info: %s", e)
            return False

    def _generate_grouped_data(self, owner: str, posts: List[dict], feeds: List[dict]) -> Optional[dict]:
        """Generate grouped data from posts (similar to the web endpoint logic)"""
        try:
            full_content_html = ""
            full_content_plain = ""
            feed_titles = []
            html_cleaner = HTMLCleaner()

            # Collect content from all posts
            for post in posts:
                content = gzip.decompress(post["content"]["content"]).decode("utf-8", "replace")
                if post["content"]["title"]:
                    content = post["content"]["title"] + ". " + content

                # Keep original HTML for display
                full_content_html += content + "\n\n"
                
                # Clean HTML tags for LLM processing
                html_cleaner.purge()
                html_cleaner.feed(content)
                clean_content = " ".join(html_cleaner.get_content())
                full_content_plain += clean_content + "\n\n"

                # Get feed title
                feed = next((f for f in feeds if f["feed_id"] == post.get("feed_id")), None)
                feed_titles.append(feed["title"] if feed else "Unknown Feed")

            # Generate chapters using LLM
            chapters = self._llm_split_chapters(full_content_plain, full_content_html)
            
            # Split into sentences and create groups
            sentences, groups, group_colors = self._create_sentences_and_groups(
                full_content_plain, full_content_html, chapters
            )
            
            feed_title = " | ".join(feed_titles) if feed_titles else "Unknown Feeds"
            
            return {
                "sentences": sentences,
                "groups": groups,
                "group_colors": group_colors,
                "feed_title": feed_title
            }
            
        except Exception as e:
            self._log.error("Error generating grouped data. Info: %s", e)
            return None

    def _llm_split_chapters(self, text_plain: str, text_html: str) -> List[dict]:
        """Split content into chapters using LLM"""
        try:
            if not self._llamacpp_handler:
                # Fallback: single chapter with all content
                return [{"title": "Main Content", "text": text_html}]
            
            # First LLM call: get list of topics
            prompt1 = f"""You are a text analysis expert. Analyze the following article and provide a list of main topics or chapters. Each topic should be a brief title (1-3 words).

Output format:

Topic Title
Another Topic

Article:
{text_plain}
"""
            
            response1 = self._llamacpp_handler.call([prompt1], temperature=0.0).strip()
            logging.info("LLM topics response: %s", response1)
            
            # Parse topics
            lines = [ln.strip() for ln in response1.strip().split('\n') if ln.strip()]
            topics = []
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                if ln[0].isdigit() and '. ' in ln:
                    parts = ln.split('. ', 1)
                    if len(parts) == 2:
                        topic = parts[1].strip()
                    else:
                        continue
                else:
                    topic = ln
                # Clean the count
                topic = re.sub(r'\s*\(\d+ sentences?\)', '', topic).strip()
                topics.append(topic)
            
            if not topics:
                return [{"title": "Main Content", "text": text_html}]
            
            # Second LLM call: split content into chapters based on topics
            topics_list = '\n'.join([f"{i+1}. {topic}" for i, topic in enumerate(topics)])
            prompt2 = f"""You are a text analysis expert. Split the following article into chapters based on the topics provided. For each topic, extract the relevant content from the article.

Output format:

Topic Title
Content for this topic

Another Topic
Content for this topic

Topics:
{topics_list}

Article:
{text_plain}
"""
            
            response2 = self._llamacpp_handler.call([prompt2], temperature=0.0).strip()
            logging.info("LLM chapter content response: %s", response2)
            
            # Parse chapters with content
            chapters = []
            current_topic = None
            current_content = []
            
            for line in response2.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Check if this is a topic line (matches one of our topics)
                is_topic = False
                for topic in topics:
                    if line.lower().startswith(topic.lower()):
                        # Save previous chapter if exists
                        if current_topic and current_content:
                            chapters.append({
                                "title": current_topic,
                                "text": '\n'.join(current_content)
                            })
                        
                        # Start new chapter
                        current_topic = topic
                        current_content = []
                        is_topic = True
                        break
                
                if not is_topic and current_topic:
                    current_content.append(line)
            
            # Add the last chapter
            if current_topic and current_content:
                chapters.append({
                    "title": current_topic,
                    "text": '\n'.join(current_content)
                })
            
            # If we couldn't parse chapters properly, fallback to single chapter
            if not chapters:
                return [{"title": "Main Content", "text": text_html}]
            
            return chapters
            
        except Exception as e:
            logging.error("LLM chapter splitting failed: %s", e)
            # Fallback: single chapter with all content
            return [{"title": "Main Content", "text": text_html}]

    def _create_sentences_and_groups(self, full_content_plain: str, full_content_html: str, 
                                    chapters: List[dict]) -> tuple:
        """Create sentences and groups from chapters"""
        # Split into sentences
        sentences = self._split_sentences(full_content_plain)
        
        # Create groups based on chapters
        groups = {}
        group_colors = {}
        
        # If only one chapter, assign all sentences to it
        if len(chapters) == 1:
            title = chapters[0]["title"]
            groups[title] = list(range(1, len(sentences) + 1))
            group_colors[title] = self._group_color(title)
        else:
            # For multiple chapters, we need to map sentences to chapters
            # This is a simplified approach - in a full implementation, you would
            # need more sophisticated text matching between chapter content and sentences
            current_sentence = 1
            for i, chapter in enumerate(chapters):
                title = chapter["title"]
                chapter_text = chapter["text"]
                
                # Count sentences in this chapter's text
                chapter_sentences = self._split_sentences(chapter_text)
                sentence_count = len(chapter_sentences)
                
                if sentence_count > 0:
                    groups[title] = list(range(current_sentence, current_sentence + sentence_count))
                    current_sentence += sentence_count
                else:
                    # Fallback: assign at least one sentence to each chapter
                    groups[title] = [current_sentence]
                    current_sentence += 1
                
                group_colors[title] = self._group_color(title)
        
        return sentences, groups, group_colors

    def _split_sentences(self, text: str) -> List[dict]:
        """Split text into sentences"""
        # Normalize whitespace
        txt = re.sub(r"\s+", " ", text.strip())
        if not txt:
            return []
        
        # Simple sentence splitting by punctuation followed by space and capital letter
        # Use positive lookbehind to include punctuation with the sentence
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-Я])', txt)
        
        # Clean up and filter empty sentences
        result = []
        for i, sentence in enumerate(sentences):
            if sentence and len(sentence.strip()) > 0:
                result.append({
                    "text": sentence.strip(),
                    "number": i + 1
                })
        
        return result

    def _group_color(self, group_id: str) -> str:
        """Generate color for a group"""
        digest = hashlib.md5(group_id.encode('utf-8')).hexdigest()
        hue = (int(digest[:8], 16) % 360) / 360.0
        sat = 0.6
        light = 0.7
        return self._hsl_to_hex(hue, sat, light)

    def _hsl_to_hex(self, h: float, s: float, l: float) -> str:
        """Convert HSL to HEX color"""
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return '#' + ''.join(f'{int(c*255):02x}' for c in (r, g, b))
