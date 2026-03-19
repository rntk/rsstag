'use strict';
import React from 'react';

export default class CategoriesList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      cats: window.initial_cats_list,
    };
  }

  changeFeedsState(cat_name) {
    let state = Object.assign({}, this.state);

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
              return (
                <li key={i} className="feed-item">
                  <input
                    type="checkbox"
                    className="feed-checkbox"
                    data-type="feed"
                    data-id={feed.feed_id}
                    onChange={window.handleCheckboxChange}
                  />
                  <a href={feed.url}>{feed.title}</a>
                  <span className="category-count">{feed.unread_count}</span>
                </li>
              );
            });
          }
          cats.push(
            <li className="category" key={cat_name}>
              <div className="category-header">
                {cat_name !== 'All' ? (
                  <span
                    className={'show_btn ' + (cat.showed ? 'not_minimized' : 'minimized')}
                    onClick={this.changeFeedsState.bind(this, cat_name)}
                  ></span>
                ) : (
                  <span style={{ width: '20px' }}></span>
                )}
                {cat_name !== 'All' ? (
                  <input
                    type="checkbox"
                    className="category-checkbox"
                    data-type="category"
                    data-id={cat.category_id}
                    onChange={window.handleCheckboxChange}
                  />
                ) : (
                  ''
                )}
                <a href={cat.url}>{cat.title}</a>
                <span className="category-count">{cat.unread_count}</span>
              </div>
              <ul className={'feeds ' + (cat.showed ? 'not_hidden' : 'hidden')}>{feeds}</ul>
            </li>
          );
        }
      }
      return <ul>{cats}</ul>;
    } else {
      return <p>No categories</p>;
    }
  }
}
