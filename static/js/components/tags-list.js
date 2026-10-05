'use strict';
import React from 'react';
import TagItem from '../components/tag-item.js';
import { compareByName, rankedComparator } from '../libs/tag-sort.js';

export default class TagsList extends React.Component {
  constructor(props) {
    super(props);
    // Ranked lists open flat so the selected ordering is immediately visible.
    this.state = { groupByLetter: !props.scoreKey && !props.preserveOrder };
    this.updateTags = this.updateTags.bind(this);
    this.toggleGrouping = this.toggleGrouping.bind(this);
  }

  updateTags(state) {
    // Keep UI-only flags local to this component.
    const nextState = { ...state };
    delete nextState.groupByLetter;
    this.setState(nextState);
  }

  toggleGrouping() {
    this.setState((prevState) => ({ groupByLetter: !prevState.groupByLetter }));
  }

  rankedLabel() {
    if (this.props.preserveOrder) {
      return 'Show selected ranking';
    }
    return this.props.scoreKey ? 'Show by score' : 'Show by frequency';
  }

  static getDerivedStateFromProps(props) {
    if (props.tags) {
      return { tags: props.tags, tag_hash: props.tag_hash || '' };
    }
    return null;
  }

  componentDidMount() {
    if (!this.props.tags) {
      this.props.ES.bind(this.props.ES.TAGS_UPDATED, this.updateTags);
    }
    //subscribe
  }

  componentWillUnmount() {
    if (!this.props.tags) {
      this.props.ES.unbind(this.props.ES.TAGS_UPDATED, this.updateTags);
    }
    //unsubscribe
  }

  render() {
    if (this.state && this.state.tags && this.state.tags.size) {
      const mode = this.state.groupByLetter ? 'grouped' : 'flat';
      const toolsRow = (
        <div className="tags_tools_row">
          <button type="button" onClick={this.toggleGrouping} className="tags_grouping_toggle">
            {this.state.groupByLetter ? this.rankedLabel() : 'Show grouped by letter'}
          </button>
        </div>
      );

      const tags = Array.from(this.state.tags.values());
      const tagItems = (sortedTags, keyPrefix) =>
        sortedTags.map((tag) => (
          <TagItem
            key={`${keyPrefix}_${tag.tag}`}
            tag={tag}
            tags={this.state.tags}
            tag_hash={this.state.tag_hash}
            ES={this.props.ES}
            uniq_id={tag.tag}
            is_entity={this.props.is_entities}
            scoreKey={this.props.scoreKey}
            scoreLabel={this.props.scoreLabel}
          />
        ));

      if (!this.state.groupByLetter) {
        const sortedFlat = tags.sort(
          rankedComparator(this.props.scoreKey, this.props.preserveOrder)
        );

        return (
          <div key={mode}>
            {toolsRow}
            <ol className="cloud">{tagItems(sortedFlat, 'flat')}</ol>
          </div>
        );
      }

      let letterGroups = [];

      // Collect and sort tags alphabetically by their display text
      const sorted = tags.sort(compareByName);

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
                <div className="alpha_group_tags">{currentGroupTags}</div>
              </div>
            );
          }

          // Start new group
          currentLetter = first;
          currentGroupTags = [];
        }

        currentGroupTags.push(...tagItems([tag], 'grouped'));
      }

      // Don't forget the last group
      if (currentLetter !== null && currentGroupTags.length > 0) {
        letterGroups.push(
          <div key={`group_${currentLetter}`} className="alpha_group_container">
            <div className="alpha_group_title">
              <h3>{currentLetter}</h3>
            </div>
            <div className="alpha_group_tags">{currentGroupTags}</div>
          </div>
        );
      }

      return (
        <div key={mode}>
          {toolsRow}
          <ol className="cloud">{letterGroups}</ol>
        </div>
      );
    } else {
      return <p className="tag-info-empty-state">No tags</p>;
    }
  }
}
