import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rsstag.web.app import RSSTagApplication

import gzip

from rsstag.html_cleaner import HTMLCleaner

from werkzeug.wrappers import Response, Request

def on_chat_post(app: "RSSTagApplication", user: dict, rqst: Request):
    data = rqst.get_json()
    if not data:
        return Response(json.dumps({"error": "No data"}), mimetype="application/json", status=400)

    tag = data["tag"]
    if not tag:
        return Response(json.dumps({"error": "No tag"}), mimetype="application/json", status=400)

    pids = data.get("pids", [])
    if not pids:
        return Response(json.dumps({"error": "No post IDs provided"}), mimetype="application/json", status=400)
    
    db_posts_c = app.posts.get_by_pids(user["sid"], pids)
    cleaner = HTMLCleaner()
    user_msgs = ""
    if "user" in data and data["user"]:
        user_msgs = data["user"]
    if not user_msgs:
        result = {"error": "No user messages"}
        return Response(json.dumps(result), mimetype="application/json", status=400)
    
    # Process posts and clean content
    post_contents = []
    for post in db_posts_c:
        txt = post["content"]["title"] + ". " + gzip.decompress(post["content"]["content"]).decode(
            "utf-8", "replace"
        )

        cleaner.purge()
        cleaner.feed(txt)
        txt = " ".join(cleaner.get_content())
        txt = txt.strip()
        if txt:
            post_contents.append(txt)

    if not post_contents:
        result = {"error": "No texts found for these posts"}
        return Response(json.dumps(result), mimetype="application/json", status=200)
    
    # Constants for managing context window
    max_chunk_size = 6000  # Characters per chunk
    max_batch_size = 5     # Maximum posts per batch
    
    def process_text_batches(texts, question, depth=0, max_depth=2):
        """
        Process texts in batches to handle LLM context limits
        Recursively combines results for large datasets
        """
        # Base case for recursion
        if len(texts) <= max_batch_size or depth >= max_depth:
            batch_text = "\n".join([f"<message>{text}</message>" for text in texts])
            prompt = f"""
You will receive a list of messages about the topic "{tag}".
The messages will be enclosed within the <messages></messages> tags,
and each individual message will be wrapped in <message></message> tags.
Your task is to process these messages and assist the user with the following request:
{question}

<messages>{batch_text}</messages>
"""
            return app.llamacpp.call([prompt])
        
        # Process in batches
        results = []
        batches = []
        current_batch = []
        current_size = 0
        
        # Create batches based on both count and character limits
        for text in texts:
            if len(current_batch) >= max_batch_size or current_size + len(text) > max_chunk_size:
                if current_batch:  # Don't add empty batches
                    batches.append(current_batch)
                current_batch = [text]
                current_size = len(text)
            else:
                current_batch.append(text)
                current_size += len(text)
                
        # Add the last batch if it has content
        if current_batch:
            batches.append(current_batch)
        
        # Process each batch and collect summaries/analyses
        for batch in batches:
            # For intermediate batches, ask for a summary or key points
            intermediate_question = f"Analyze these messages about {tag} and provide key information and insights that would help answer: {question}"
            batch_result = process_text_batches(batch, intermediate_question, depth + 1)
            results.append(batch_result)
        
        # If we have multiple results, recursively process them
        if len(results) > 1:
            meta_prompt = f"""
I've analyzed multiple batches of messages about "{tag}" and have the following analyses. 
Please combine these analyses to answer the user's question: {question}

<analyses>
{"".join([f"<analysis>{r}</analysis>" for r in results])}
</analyses>
"""
            return app.llamacpp.call([meta_prompt])
        elif len(results) == 1:
            return results[0]
        else:
            return "No results were generated from the analysis."
    
    # Process all content and generate the final response
    txt = process_text_batches(post_contents, user_msgs)
    
    result = {"data": txt}

    return Response(json.dumps(result), mimetype="application/json", status=200)