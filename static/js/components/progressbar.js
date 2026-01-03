'use strict';
import React from 'react';

export default class ProgressBar extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      tasks: [],
      progress: 0,
    };
    this.changeFilling = this.changeFilling.bind(this);
    this.animationEnd = this.animationEnd.bind(this);
  }

  componentDidMount() {
    this.props.ES.bind(this.props.ES.CHANGE_PROGRESSBAR, this.changeFilling);
  }

  componentWillUnmount() {
    this.props.ES.unbind(this.props.ES.CHANGE_PROGRESSBAR, this.changeFilling);
  }

  animationEnd() {
    this.props.ES.trigger(this.props.ES.PROGRESSBAR_ANIMATION_END);
  }

  changeFilling(state) {
    this.setState(state);
  }

  render() {
    let style = {
      display: this.state.progress > 0 ? 'block' : 'none',
      width: this.state.progress + '%',
    };

    return <div className="filling" style={style} onTransitionEnd={this.animationEnd}></div>;
  }
}
