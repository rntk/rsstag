'use strict';
import React from 'react';
import PostItem from '../components/post-item.js';
import TagItem from '../components/tag-item.js';

export default class PostsList extends React.Component{
    constructor(props) {
        super(props);
        this.updatePosts = this.updatePosts.bind(this);
    }

    updatePosts(state) {
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.POSTS_UPDATED, this.updatePosts);
    }

    componentDidUpdate() {
        this.props.ES.trigger(this.props.ES.POSTS_RENDERED);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.POSTS_UPDATED, this.updatePosts);
    }

    render() {
        if (this.state) {
            /*let words = this.state.words.map(word => {
                return(<span key={word}>{word}, </span>);
            });*/
            let words = this.state.words.join(', ');
            if (words) {
                words = `(${words})`;
            }
            let posts = [];
            let bi_grams = {};
            let freq = {}
            for (let item of this.state.posts) {
                let post = item[1];

                posts.push(
                    <PostItem post={post} key={post.pos} ES={this.props.ES} current={this.state.current_post} />
                );
                for (let tag of post.post.tags) {
                    if (!(tag in freq)) {
                        freq[tag] = 0;
                    }
                    freq[tag]++
                }
                for (let bi of post.post.bi_grams) {
                    if (!(bi in bi_grams)) {
                        bi_grams[bi] = 0;
                    }
                    bi_grams[bi]++;
                }
            }
            let bi_grams_l = [];
            let stopwords = ["didn\'t", "при", "куда", "him", "этого", "you\'ll", "ни", "before", "было", "нет", "никогда", "что", "том", "во", "того", "my", "y", "s", "yours", "этом", "по", "эту", "m", "with", "сейчас", "три", "that\'ll", "ее", "даже", "то", "do", "меня", "вы", "yourselves", "shan", "we", "isn", "above", "тем", "со", "out", "ты", "всегда", "над", "тот", "what", "to", "хоть", "ничего", "yourself", "этой", "not", "себе", "own", "more", "где", "she\'s", "всю", "сам", "другой", "зачем", "by", "being", "всех", "be", "а", "ведь", "them", "здесь", "какой", "hadn\'t", "этот", "only", "раз", "o", "wasn", "myself", "моя", "вот", "нибудь", "nor", "wouldn", "можно", "mustn\'t", "она", "mightn\'t", "doesn\'t", "тоже", "конечно", "further", "им", "про", "hadn", "itself", "без", "they", "к", "themselves", "those", "его", "будто", "были", "aren\'t", "тебя", "ним", "your", "won", "надо", "еще", "wasn\'t", "shan\'t", "вам", "shouldn\'t", "few", "does", "почти", "he", "herself", "its", "into", "такой", "свою", "i", "ll", "once", "о", "needn", "are", "her", "all", "чтобы", "his", "теперь", "couldn", "whom", "same", "под", "again", "него", "too", "mightn", "weren\'t", "which", "don", "in", "won\'t", "более", "иногда", "why", "всего", "не", "мне", "just", "они", "перед", "кто", "hasn\'t", "below", "если", "между", "два", "you\'d", "for", "so", "себя", "himself", "that", "you\'ve", "чем", "у", "hers", "впрочем", "from", "under", "you", "но", "да", "haven\'t", "should", "did", "может", "и", "тут", "лучше", "только", "есть", "hasn", "some", "же", "или", "я", "was", "very", "так", "за", "ours", "both", "or", "couldn\'t", "isn\'t", "during", "the", "от", "had", "these", "having", "чуть", "с", "on", "один", "все", "of", "doesn", "будет", "should\'ve", "because", "он", "ve", "ourselves", "their", "на", "about", "ему", "until", "вдруг", "об", "ж", "их", "she", "and", "ней", "хорошо", "совсем", "разве", "них", "быть", "нее", "t", "был", "через", "потом", "нельзя", "shouldn", "чтоб", "through", "when", "as", "over", "how", "our", "between", "была", "here", "re", "me", "while", "it\'s", "than", "мы", "опять", "до", "ей", "a", "needn\'t", "чего", "вас", "после", "it", "been", "am", "up", "any", "больше", "theirs", "какая", "will", "down", "потому", "now", "в", "doing", "but", "weren", "aren", "wouldn\'t", "is", "have", "d", "this", "don\'t", "there", "mustn", "didn", "an", "where", "наконец", "has", "бы", "at", "no", "уже", "you\'re", "haven", "для", "against", "уж", "if", "then", "off", "много", "ain", "such", "were", "ma", "can", "other", "who", "из", "ли", "нас", "тогда", "most", "там", "как", "мой", "ну", "after", "each", "эти", "когда"]
            let stopw = new Map();
            for (let stop of stopwords) {
                stopw.set(stop, "");
            }
            for (let bi in bi_grams) {
                let tags = bi.split(" ");
                if (stopw.has(tags[0]) || stopw.has(tags[1])) {
                    continue;
                }
                let coef = bi_grams[bi] / freq[tags[0]] + freq[tags[1]];
                bi_grams_l.push([bi, bi_grams[bi], coef]);
            }
            bi_grams_l.sort((a, b) => {
                if (a[2] < b[2]) {
                    return 1;
                } else {
                    return -1;
                }
            })
            //bi_grams_l = bi_grams_l.slice(0, Number.parseInt(bi_grams_l.length / 2 + 1));
            let tags = [];
            for (let bi of bi_grams_l) {
                if (bi[1] < 2) {
                    continue;
                }
                let tag = {
                    tag: bi[0],
                    count: bi[1],
                    words: bi[0].split(" "),
                    url: "/bi-gram/" + encodeURIComponent(bi[0])
                }
                tags.push(
                    <TagItem key={bi[0]} tag={tag} tags={[]} tag_hash={bi[0]} uniq_id={bi[0]} is_bigram={true} />
                );
            }

            return(
                <div className="posts_list">
                    <div className="group_title">
                        <h3>{this.state.group_title}&nbsp;</h3>
                        {words? words: ''}
                    </div>
                    <div className="posts">
                        {posts.length? posts: <p>No posts</p>}
                    </div>
                    <div className="posts">
                        <ol className="cloud">
                            {tags}
                        </ol>
                    </div>
                </div>
            );
        } else {
            return(<p>No posts</p>);
        }
    }
};