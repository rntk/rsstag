'use strict';
import React from 'react';

export default class SearchInput extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            request: '',
            suggestions: []
        };
        this.t_out = 0;
        this.debounce_t = 800;
        this.urls = {
            tags_search: '/tags-search'
        }
        this.changeSearchRequest = this.changeSearchRequest.bind(this);
    }

    changeSearchRequest(e) {
        let value = e.target.value,
            suggestions;

        if (value) {
            suggestions = this.state.suggestions;
        } else {
            suggestions = [];
        }
        this.setState({
            request: e.target.value,
            suggestions: suggestions,
        });
        if (this.t_out) {
            clearTimeout(this.t_out);
        }
        this.t_out = setTimeout(() => {
            this.fetchSuggestions(this.state.request);
        }, this.debounce_t);
    }

    fetchSuggestions(request) {
        if (request) {
            let form = new FormData();

            form.append('req', request);
            fetch(
                this.urls.tags_search,
                {
                    method: 'POST',
                    credentials: 'include',
                    body: form
                }
            ).then(response => {
                response.json().then(data => {
                    if (data.data) {
                        this.setState({
                            request: request,
                            suggestions: data.data
                        });
                    } else {
                        this.errorMessage('Error. Try later');
                    }
                });
            }).catch(err => {
                this.errorMessage('Error. Try later');
            });
        }
    }

    render() {
        let suggestions = [];

        if (this.state && this.state.suggestions) {
            suggestions = this.state.suggestions.map(sugg => {
                return(
                    <p className="search_result_item" key={sugg.tag}>
                        <a href={sugg.url}>{sugg.tag} ({sugg.cnt})</a>
                    </p>
                );
            });
        }
        return(
            <div className="search_tools">
                <input className="search_field" type="text" placeholder="Search" value={this.state.request} onChange={this.changeSearchRequest} />
                <div className="search_result">{suggestions}</div>
            </div>
        );
    }
};