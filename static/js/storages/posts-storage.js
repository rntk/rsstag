'use strict';
export default class PostsStorage {
    constructor(event_system) {
        this.ES = event_system;
        this._state = {
            words: [],
            group: '',
            group_title: '',
            posts: new Map(),
            readed: false
        };
        this.urls = {
            fetch_content: '/posts-content',
            fetch_links: '/post-links',
            read_posts: '/read/posts'
        }
    }

    normalizePosts(posts) {
        let posts_map = new Map();

        for (let i = 0; i < posts.length; i++) {
            posts_map.set(+posts[i].pos, posts[i]);
        }

        return(posts_map);
    }

    fetchPosts() {
        let state = {
            posts: this.normalizePosts(window.posts_list),
            group: window.group,
            group_title: window.group_title,
            words: window.words,
            readed: false,
            showed: false
        };
        if (this.isNeedReadedChange(state)) {
            state.readed = !state.readed;
        }
        this.setState(state);

    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        this._state = state;
        this.ES.trigger(this.ES.POSTS_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.CHANGE_POSTS_CONTENT_STATE, this.changePostsContentState.bind(this));
        this.ES.bind(this.ES.CHANGE_POSTS_STATUS, this.changePostsStatus.bind(this));
        this.ES.bind(this.ES.SHOW_POST_LINKS, this.fetchPostLinks.bind(this));
    }

    changePostsContentState(data) {
        let ids = [],
            changed = false,
            state = this.getState();

        if (data.showed) {
            data.ids.forEach(post_id => {
                let id = +post_id;

                if (state.posts.has(id)) {
                    let post = state.posts.get(id);

                    if (post.post.content.content === undefined) {
                        ids.push(id);
                    } else {
                        post.showed = true;
                        changed = true;
                    }
                }
            });
        } else {
            data.ids.forEach(post_id => {
                let id = +post_id;

                if (state.posts.has(id)) {
                    let post = state.posts.get(id);
                    post.showed = data.showed;
                    state.posts.set(id, post);
                    changed = true;
                }
            });
        }
        if (ids.length) {
            this.fetchPostsContent(ids);
        }

        if (changed) {
            this.setState(state);
        }
    }

    fetchPostsContent(ids) {
        if (ids) {
            fetch(
                this.urls.fetch_content,
                {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(ids)
                }
            ).then(response => {
                response.json().then(data => {
                    if (data.data) {
                        let state = this.getState(),
                            changed = false,
                            content = data.data.slice(0);

                        content.forEach(content => {
                            let id = +content.pos;

                            if (state.posts.has(id)) {
                                let post = state.posts.get(id);
                                post.showed = true;
                                post.post.content.content = content.content;
                                state.posts.set(id, post);
                                changed = true;
                            }
                        });
                        if (changed) {
                            this.setState(state);
                        }
                    } else {
                        this.errorMessage('Error. Try later');
                    }
                });
            }).catch(err => {
                this.errorMessage('Error. Try later');
            })
        }
    }

    isNeedReadedChange(state) {
        let change_readed = true;

        for (let item of state.posts) {
            if ((item[1].post.read === state.readed)) {
                change_readed = false;
            }
            if (!change_readed) {
                break;
            }
        }

        return change_readed;
    }

    changePostsStatus(data) {
        if (data.ids && data.ids.length) {
            fetch(
                this.urls.read_posts,
                {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                }
            ).then(response => {
                response.json().then(resp => {
                    if (resp.data) {
                        let state = this.getState(),
                            changed = false;

                        data.ids.forEach(post_id => {
                            let id = +post_id

                            if (state.posts.has(id)) {
                                let post = state.posts.get(id);

                                if (post.post.read !== data.readed) {
                                    post.post.read = data.readed;
                                    state.posts.set(id, post);
                                    changed = true;
                                }
                            }
                        });
                        if (changed) {
                            if (this.isNeedReadedChange(state)) {
                                state.readed = !state.readed;
                            }
                            this.setState(state);
                        }
                    } else {
                        this.errorMessage('Error. Try later');
                    }
                });
            }).catch(err => {//mutate state
                this.errorMessage('Error. Try later');
            });
        }
    }

    fetchPostLinks(id) {
        let promise,
            post_id = +id;

        promise = fetch(
            `${this.urls.fetch_links}/${post_id}`,
            {
                method: 'GET',
                credentials: 'include'
            }
        );
        promise.then(response => {
            response.json().then(data => {
                if (data.data) {
                    let state = this.getState();

                    if (state.posts.has(post_id)) {
                        let post = state.posts.get(post_id);
                        if (data.data.tags) {
                            data.data.tags.sort((a, b) => {
                                if (a.tag.charAt(0) > b.tag.charAt(0)) {
                                    return 1;
                                } else {
                                    return -1;
                                }
                            });
                        }
                        post.links = data.data
                        state.posts.set(post_id, post);
                        this.setState(state);
                    }
                } else {
                    this.errorMessage(data.error);
                }
            });
        }).catch(err => {
            this.errorMessage('Error');
        });
        return(promise);
    }

    errorMessage(msg) {
        console.log(msg);
        this.ES.trigger(this.POSTS_ERROR_MESSAGE, msg);
    }

    start() {
        this.bindEvents();
        this.fetchPosts();
    }
}