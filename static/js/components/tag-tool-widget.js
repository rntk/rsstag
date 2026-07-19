'use strict';
import React from 'react';
import { createPortal } from 'react-dom';
import TagsList from './tags-list.js';
import rsstag_utils from '../libs/rsstag_utils.js';

function normalizedTags(data) {
  data.sort((a, b) => {
    const countDiff = (b.count || 0) - (a.count || 0);
    if (countDiff !== 0) {
      return countDiff;
    }
    const at = (a.tag || '').toString();
    const bt = (b.tag || '').toString();
    return at.localeCompare(bt, undefined, { numeric: true, sensitivity: 'base' });
  });

  const tags = new Map();
  data.forEach((tag) => {
    tag.root = true;
    tags.set(tag.tag, tag);
  });

  return tags;
}

export default class TagToolWidget extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hidden: true, loading: false, tags: null, error: null };
    this.loadData = this.loadData.bind(this);
  }

  componentWillUnmount() {
    this.clearRenderData();
  }

  clearRenderData() {
    if (this.props.renderData) {
      const container = document.getElementById(this.props.listContainerId);
      if (container) {
        container.innerHTML = '';
      }
    }
  }

  loadData() {
    if (!this.state.hidden) {
      this.setState({ hidden: true, tags: null });
      this.clearRenderData();
      return;
    }

    this.setState({ loading: true, error: null });
    rsstag_utils
      .fetchJSON(this.props.url + '/' + encodeURIComponent(this.props.tag), {
        method: 'GET',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      .then((data) => {
        if (data.data) {
          const tags = normalizedTags(data.data);
          this.setState({ hidden: false, loading: false, tags });
          if (this.props.renderData) {
            const container = document.getElementById(this.props.listContainerId);
            if (container) {
              this.props.renderData(container, tags);
            }
          }
        } else {
          this.setState({ loading: false, error: 'Error. Try later' });
        }
      })
      .catch((err) => {
        console.log(err);
        this.setState({ loading: false, error: 'Error. Try later' });
      });
  }

  render() {
    const prefix = this.state.hidden ? 'Load ' : 'Hide ';
    const container = !this.props.renderData && document.getElementById(this.props.listContainerId);

    return (
      <React.Fragment>
        <button onClick={this.loadData}>{prefix + this.props.title}</button>
        {this.state.error ? <span>{this.state.error}</span> : null}
        {!this.state.hidden && container
          ? createPortal(
              <TagsList
                tags={this.state.tags}
                is_bigram={this.props.is_bigram}
                is_entities={this.props.is_entities}
              />,
              container
            )
          : null}
      </React.Fragment>
    );
  }
}
