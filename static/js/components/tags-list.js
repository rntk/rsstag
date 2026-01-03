'use strict';
import React from 'react';
import TagItem from '../components/tag-item.js';

export default class TagsList extends React.Component {
  constructor(props) {
    super(props);
    this.updateTags = this.updateTags.bind(this);
  }

  updateTags(state) {
    this.setState(state);
  }

  componentDidMount() {
    this.props.ES.bind(this.props.ES.TAGS_UPDATED, this.updateTags);
    //subscribe
  }

  componentWillUnmount() {
    this.props.ES.unbind(this.props.ES.TAGS_UPDATED, this.updateTags);
    //unsubscribe
  }

  render() {
    if (this.state && this.state.tags && this.state.tags.size) {
      let tags = [];

      // Collect and sort tags alphabetically by their display text
      const sorted = Array.from(this.state.tags.values()).sort((a, b) => {
        const at = (a.tag || '').toString();
        const bt = (b.tag || '').toString();
        return at.localeCompare(bt, undefined, { numeric: true, sensitivity: 'base' });
      });

      // Group by first letter and insert a small title before each group
      let currentLetter = null;
      for (let tag of sorted) {
        const first = ((tag.tag || '').trim().charAt(0) || '').toUpperCase();
        if (first && first !== currentLetter) {
          currentLetter = first;
          tags.push(
            <div key={`hdr_${currentLetter}`} className="alpha_group_title">
              <h3>{currentLetter}</h3>
            </div>
          );
        }

        tags.push(
          <TagItem
            key={tag.tag}
            tag={tag}
            tags={this.state.tags}
            tag_hash={this.state.tag_hash}
            ES={this.props.ES}
            uniq_id={tag.tag}
            is_bigram={this.props.is_bigram}
            is_entity={this.props.is_entities}
          />
        );
      }
      return <ol className="cloud">{tags}</ol>;
    } else {
      return <p>No tags</p>;
    }
  }
}
