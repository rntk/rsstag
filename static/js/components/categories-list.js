'use strict';
import React from 'react';

export default class CategoriesList extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            cats: window.initial_cats_list
        }
    }

    changeFeedsState(cat_name) {
        let state = Object.assign({}, this.state);console.log(state, this.state);

        if (cat_name in state.cats) {
            state.cats[cat_name].showed = !state.cats[cat_name].showed;
            this.setState(state);
        }
    }

    render() {
        if (this.state && this.state.cats) {
            let cats = [];

            for (let cat_name in this.state.cats) {
                if (this.state.cats.hasOwnProperty(cat_name)) {
                    let cat = this.state.cats[cat_name],
                        feeds = [];

                    if (cat.feeds) {
                        feeds = cat.feeds.map((feed, i) => {
                            return(
                                <li key={i}><a href={feed.url}>{feed.title}</a>({feed.unread_count})</li>
                            );
                        })
                    }
                    cats.push(
                        <li className="category" key={cat_name}>
                            <a href={cat.url}>{cat.title}</a>({cat.unread_count})
                            {(cat_name !== 'All')? <span className={'show_btn ' +  ((cat.showed)? 'not_minimized': 'minimized')} onClick={this.changeFeedsState.bind(this, cat_name)}></span>: ''}
                            <ul className={'feeds ' + ((cat.showed)? 'not_hidden': 'hidden')}>
                                {feeds}
                            </ul>
                        </li>
                    )
                }
            }
            return(
                <ul>
                    {cats}
                </ul>
            );
        } else {
            return(<p>No categories</p>);
        }
    }
};