'use strict';
import React from 'react';

export class PostChat extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            message: '',
            response: '',
            isLoading: false
        };
        this.handleChange = this.handleChange.bind(this);
        this.handleSubmit = this.handleSubmit.bind(this);
    }

    handleChange(event) {
        this.setState({message: event.target.value});
    }

    handleSubmit(event) {
        event.preventDefault();
        
        if (!this.state.message.trim()) {
            return;
        }

        this.setState({isLoading: true, response: ''});
        
        const tag = this.props.posts.group_title;
        const pids = Array.from(this.props.posts.posts.values()).map(post => post.post.pid);
        const requestData = {
            tag: tag,
            pids: pids,
            user: this.state.message
        };

        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                this.setState({
                    response: 'Error: ' + data.error,
                    isLoading: false
                });
            } else {
                this.setState({
                    response: data.data,
                    isLoading: false
                });
            }
        })
        .catch(error => {
            this.setState({
                response: 'Error connecting to server: ' + error.message,
                isLoading: false
            });
        });
    }

    render() {
        return (
            <div className="post-chat-container">
                <h3>Chat with posts about: {this.props.posts.group_title}</h3>
                <form onSubmit={this.handleSubmit} className="chat-form">
                    <textarea 
                        value={this.state.message}
                        onChange={this.handleChange}
                        placeholder="Ask a question about these posts..."
                        className="chat-input"
                        rows="4"
                    />
                    <button 
                        type="submit" 
                        disabled={this.state.isLoading} 
                        className="chat-submit"
                    >
                        {this.state.isLoading ? 'Processing...' : 'Send'}
                    </button>
                </form>
                {this.state.isLoading && <div className="loading-indicator">Processing your request...</div>}
                {this.state.response && (
                    <div className="chat-response">
                        <h4>Response:</h4>
                        <div className="response-content">{this.state.response}</div>
                    </div>
                )}
            </div>
        );
    }
}

export default function PostChatS(posts) {
    return <PostChat posts={posts} />;
}