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
      let letterGroups = [];

      // Collect and sort tags alphabetically by their display text
      const sorted = Array.from(this.state.tags.values()).sort((a, b) => {
        const at = (a.tag || '').toString();
        const bt = (b.tag || '').toString();
        return at.localeCompare(bt, undefined, { numeric: true, sensitivity: 'base' });
      });

      // Group by first letter
      let currentLetter = null;
      let currentGroupTags = [];

      for (let tag of sorted) {
        const first = ((tag.tag || '').trim().charAt(0) || '').toUpperCase();

        if (first && first !== currentLetter) {
          // Save previous group if exists
          if (currentLetter !== null && currentGroupTags.length > 0) {
            letterGroups.push(
              <div key={`group_${currentLetter}`} className="alpha_group_container">
                <div className="alpha_group_title">
                  <h3>{currentLetter}</h3>
                </div>
                <div className="alpha_group_tags">
                  {currentGroupTags}
                </div>
              </div>
            );
          }

          // Start new group
          currentLetter = first;
          currentGroupTags = [];
        }

        currentGroupTags.push(
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

      // Don't forget the last group
      if (currentLetter !== null && currentGroupTags.length > 0) {
        letterGroups.push(
          <div key={`group_${currentLetter}`} className="alpha_group_container">
            <div className="alpha_group_title">
              <h3>{currentLetter}</h3>
            </div>
            <div className="alpha_group_tags">
              {currentGroupTags}
            </div>
          </div>
        );
      }

      return <ol className="cloud">{letterGroups}</ol>;
    } else {
      return <p>No tags</p>;
    }
  }
}
