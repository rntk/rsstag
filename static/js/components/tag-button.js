'use strict';
import React from 'react';

export default class TagTool extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      list_hidden: true,
    };
    this.loadData = this.loadData.bind(this);
  }

  loadData() {
    this.setState({ list_hidden: !this.state.list_hidden });
    this.props.ES.trigger(this.props.ES.CHANGE_TAGS_LOAD_BUTTON_STATE, {
      tag: this.props.tag.tag,
      hide_list: !this.state.list_hidden,
    });
  }

  render() {
    const prefix = this.state.list_hidden ? 'Load ' : 'Hide ';
    return (
      <button
        type="button"
        className={`tag-info-control${this.state.list_hidden ? '' : ' tag-info-control--active'}`}
        onClick={this.loadData}
        aria-controls={this.props.controls}
        aria-expanded={!this.state.list_hidden}
      >
        {prefix + this.props.title}
      </button>
    );
  }
}
