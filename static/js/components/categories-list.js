'use strict';
import React from 'react';

export default class CategoriesList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      cats: window.initial_cats_list,
    };
  }

  qualityBand(score) {
    if (score >= 70) {
      return 'good';
    }
    if (score >= 45) {
      return 'mixed';
    }
    return 'poor';
  }

  renderQuality(quality) {
    if (!quality || typeof quality.score !== 'number') {
      return null;
    }

    return (
      <span
        className={'quality-badge quality-' + this.qualityBand(quality.score)}
        title={'Quality ' + quality.score + '/100 over ' + quality.posts_count + ' scored posts'}
      >
        {quality.score}
      </span>
    );
  }

  scanQuality(payload, event) {
    const button = event.currentTarget;

    button.disabled = true;
    fetch('/api/quality/scan', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    })
      .then((response) => response.json())
      .then((data) => {
        button.disabled = false;
        if (data.status !== 'success') {
          alert('Error: ' + data.message);
        } else {
          alert(data.message);
        }
      })
      .catch((err) => {
        button.disabled = false;
        alert('Error: ' + err);
      });
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
                  <a className="feed-title-link" href={feed.url}>
                    {feed.title}
                  </a>
                  {this.renderQuality(feed.quality)}
                  <span className="category-count">{feed.unread_count}</span>
                  <div className="feed-actions" aria-label={`${feed.title} views`}>
                    <a className="feed-action-link" href={feed.hierarchy_url}>
                      Hierarchy
                    </a>
                    <a className="feed-action-link" href={feed.canvas_url}>
                      Canvas
                    </a>
                    <button
                      className="feed-action-link quality-scan-btn"
                      onClick={this.scanQuality.bind(this, { feed_ids: [feed.feed_id] })}
                    >
                      Score
                    </button>
                  </div>
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
                <a className="category-title-link" href={cat.url}>
                  {cat.title}
                </a>
                {this.renderQuality(cat.quality)}
                <span className="category-count">{cat.unread_count}</span>
                <div className="category-actions" aria-label={`${cat.title} views`}>
                  <a className="category-action-link" href={cat.hierarchy_url}>
                    Hierarchy
                  </a>
                  <a className="category-action-link" href={cat.canvas_url}>
                    Canvas
                  </a>
                  {cat.category_id ? (
                    <button
                      className="category-action-link quality-scan-btn"
                      onClick={this.scanQuality.bind(this, {
                        category_ids: [cat.category_id],
                      })}
                    >
                      Score
                    </button>
                  ) : (
                    ''
                  )}
                </div>
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
