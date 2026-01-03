'use strict';
import React from 'react';

export default class TagNetTools extends React.Component {
  constructor(props) {
    super(props);
    this.changeTagSettings = this.changeTagSettings.bind(this);
    this.renderTools = this.renderTools.bind(this);
  }

  changeTagSettings(e) {
    if (this.state.tags.has(this.state.selected_tag)) {
      let tag = this.state.tags.get(this.state.selected_tag);

      tag.hidden = e.target.checked;
      this.props.ES.trigger(this.props.ES.NET_TAG_CHANGE, tag);
    }
  }

  renderTools(state) {
    this.setState(state);
  }

  componentDidMount() {
    this.props.ES.bind(this.props.ES.TAGS_NET_UPDATED, this.renderTools);
    //subscribe
  }

  componentWillUnmount() {
    this.props.ES.unbind(this.props.ES.TAGS_NET_UPDATED, this.renderTools);
    //unsubscribe
  }

  render() {
    let tools = <span></span>;
    if (this.state) {
      let stat,
        control,
        showed_tags = 0;

      for (let tag_data of this.state.tags) {
        if (!tag_data[1].hidden) {
          showed_tags++;
        }
      }
      stat = (
        <span>
          {' '}
          {showed_tags} / {this.state.tags.size}
        </span>
      );
      if (this.state.tags.has(this.state.selected_tag)) {
        let tag = this.state.tags.get(this.state.selected_tag);

        tools = (
          <div>
            <span>Tag: {tag.tag}</span>
            <label htmlFor="hidden">
              <input
                type="checkbox"
                checked={tag.hidden}
                id="hidden"
                onChange={this.changeTagSettings}
              />
              Hide tag
            </label>
            {stat}
          </div>
        );
      } else {
        tools = stat;
      }
    }

    return tools;
  }
}
