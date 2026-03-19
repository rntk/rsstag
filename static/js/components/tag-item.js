'use strict';
import React from 'react';

export default class TagItem extends React.Component {
  constructor(props) {
    super(props);
    this.state = { tag: props.tag };
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
      <li className={'cloud_item ' + sentiment}>
        <div className="cloud_item_header">
          <a name={this.state.tag.tag}></a>
          <a href={this.state.tag.url} className="cloud_item_title">
            {this.state.tag.tag}
          </a>{' '}
          <span className="cloud_item_count">({this.state.tag.count})</span>
        </div>
        {(sub_tags.length > 0 || words) ? (
          <div className="cloud_item_info">
            {sub_tags}
            {sub_tags.length ? sents_link : null}
            {sub_tags.length ? ctx_link : null}
            {words}
          </div>
        ) : null}
        <div className="cloud_item_tools">
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
        </div>
      </li>
    );
  }
}
