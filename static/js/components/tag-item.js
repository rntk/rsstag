'use strict';
import React from 'react';
import { finiteScore, formatScore } from '../libs/tag-sort.js';
import {
  USER_RANK_HIDDEN,
  USER_RANK_PINNED,
  saveUserRank,
  supportsUserRank,
  toggledUserRank,
  userRankClass,
} from '../libs/tag-user-rank.js';

export default class TagItem extends React.Component {
  constructor(props) {
    super(props);
    this.state = { tag: props.tag, saving: false, error: '' };
    this.togglePin = this.toggleUserRank.bind(this, 'pin');
    this.toggleHide = this.toggleUserRank.bind(this, 'hide');
  }

  toggleUserRank(action, event) {
    if (event) {
      event.preventDefault();
    }
    if (this.state.saving) {
      return Promise.resolve();
    }
    const value = toggledUserRank(this.state.tag.user_rank, action);
    this.setState({ saving: true, error: '' });
    return saveUserRank(this.state.tag.tag, value)
      .then(() => {
        this.setState((prev) => ({
          tag: { ...prev.tag, user_rank: value },
          saving: false,
        }));
      })
      .catch((err) => {
        console.error('Can not save tag user rank', err);
        this.setState({ saving: false, error: 'Could not save, try again' });
      });
  }

  renderUserRankControls() {
    const rank = this.state.tag.user_rank;
    return (
      <React.Fragment>
        <button
          type="button"
          className="tag_pin_button"
          onClick={this.togglePin}
          disabled={this.state.saving}
        >
          {rank === USER_RANK_PINNED ? 'unpin' : 'pin'}
        </button>
        <button
          type="button"
          className="tag_hide_button"
          onClick={this.toggleHide}
          disabled={this.state.saving}
        >
          {rank === USER_RANK_HIDDEN ? 'unhide' : 'hide'}
        </button>
        {this.state.error ? <span className="tag_user_rank_error">{this.state.error}</span> : null}
      </React.Fragment>
    );
  }

  renderPinMarker() {
    if (this.state.tag.user_rank !== USER_RANK_PINNED) {
      return null;
    }
    return (
      <React.Fragment>
        {' '}
        <span className="cloud_item_pin" title="Pinned">
          &#9733;
        </span>
      </React.Fragment>
    );
  }

  renderScore() {
    const { scoreKey, scoreLabel } = this.props;
    const score = scoreKey ? finiteScore(this.state.tag, scoreKey) : null;
    if (score === null) {
      return null;
    }
    const text = scoreLabel ? `${scoreLabel} ${formatScore(score)}` : formatScore(score);
    return (
      <React.Fragment>
        {' '}
        <span className="cloud_item_score">{text}</span>
      </React.Fragment>
    );
  }

  render() {
    let sentiment = '';

    if (this.state.tag.sentiment && this.state.tag.sentiment.length) {
      sentiment = this.state.tag.sentiment[0].replace('/', '_');
    }
    let hide_tag_info_link = false;
    if (this.props.is_bigram) {
      hide_tag_info_link = true;
    } else if (this.props.is_entity) {
      hide_tag_info_link = this.state.tag.tag.search(/\s/) !== -1;
    }
    let sub_tags = [];
    if (hide_tag_info_link) {
      let subs = this.state.tag.tag.split(' ');
      for (let i = 0; i < subs.length; i++) {
        const tag = subs[i];
        sub_tags.push(
          <a
            href={'/tag-info/' + encodeURIComponent(tag)}
            key={`st_${this.state.tag.tag}_${tag}_${i}`}
            title={tag}
            className="cloud_sub_item_title"
          >
            ...
          </a>
        );
      }
    }
    let sents_link = (
      <a
        href={'/sentences/with/tags/' + encodeURIComponent(this.state.tag.tag)}
        className="tag_sentences_link"
      >
        sents
      </a>
    );
    let ctx_link = (
      <a
        href={'/context-tags/' + encodeURIComponent(this.state.tag.tag)}
        className="context_tags_link"
      >
        ctx
      </a>
    );

    let words = '';
    if (this.state.tag.words && this.state.tag.words.length) {
      words = `(${this.state.tag.words.join(', ')})`;
    }

    return (
      <li className={'cloud_item ' + sentiment + userRankClass(this.state.tag.user_rank)}>
        <div className="cloud_item_header">
          <a name={this.state.tag.tag}></a>
          <a
            href={this.state.tag.url}
            className="cloud_item_title"
            title={this.state.tag.hint || undefined}
          >
            {this.state.tag.tag}
          </a>{' '}
          <span className="cloud_item_count">({this.state.tag.count})</span>
          {this.renderScore()}
          {this.renderPinMarker()}
        </div>
        {sub_tags.length > 0 || words ? (
          <div className="cloud_item_info">
            {sub_tags}
            {sub_tags.length ? sents_link : null}
            {sub_tags.length ? ctx_link : null}
            {words}
          </div>
        ) : null}
        <div className="cloud_item_tools">
          {supportsUserRank(this.state.tag, this.props.is_bigram)
            ? this.renderUserRankControls()
            : null}
          <a href={'/tag-hierarchy?tag=' + encodeURIComponent(this.state.tag.tag)}>
            word hierarchy
          </a>
          {hide_tag_info_link ? null : (
            <a href={'/tag-info/' + this.state.tag.tag} className="get_tag_siblings">
              ...
            </a>
          )}
          {hide_tag_info_link ? null : sents_link}
          {hide_tag_info_link ? null : (
            <a href={'/sunburst/' + this.state.tag.tag} className="get_tag_sunburst">
              sunburst
            </a>
          )}
          {hide_tag_info_link ? null : (
            <a href={'/chain/' + this.state.tag.tag} className="get_tag_chains">
              chain
            </a>
          )}
          {hide_tag_info_link ? null : (
            <a
              href={'/tag-context-tree/' + encodeURIComponent(this.state.tag.tag)}
              className="get_tag_context_tree"
            >
              tree
            </a>
          )}
          {hide_tag_info_link ? null : (
            <a
              href={'/tag-concordance/' + encodeURIComponent(this.state.tag.tag)}
              className="get_tag_concordance"
            >
              context
            </a>
          )}
          {hide_tag_info_link ? null : (
            <a
              href={'/tag-explorer/' + encodeURIComponent(this.state.tag.tag)}
              className="get_tag_explorer"
            >
              explorer
            </a>
          )}
        </div>
      </li>
    );
  }
}
