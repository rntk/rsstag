'use strict';
import React from 'react';

const TAB_CLOUD = 'cloud';
const TAB_TABLE = 'table';

export class BiGramsTabs extends React.Component {
  constructor(props) {
    super(props);
    this.tabs = new Map();
    this.tabs.set(TAB_CLOUD, 'Tags Cloud');
    this.tabs.set(TAB_TABLE, 'Tags Table');
    this.state = {
      current: TAB_CLOUD,
    };

    this.onTabClick = this.onTabClick.bind(this);
  }

  onTabClick(ev) {
    let tab = ev.target.getAttribute('data-tab');
    this.changeTab(tab);
  }

  componentDidMount() {
    this.updateVisibility();
  }

  componentDidUpdate() {
    this.updateVisibility();
  }

  updateVisibility() {
    const tagsPage = document.getElementById('tags_page');
    const bigramsTablePage = document.getElementById('bigrams_table_page');

    if (tagsPage && bigramsTablePage) {
      if (this.state.current === TAB_CLOUD) {
        tagsPage.style.display = 'block';
        bigramsTablePage.style.display = 'none';
      } else if (this.state.current === TAB_TABLE) {
        tagsPage.style.display = 'none';
        bigramsTablePage.style.display = 'block';
      }
    }
  }

  render() {
    let tabs = [];
    for (let [name, title] of this.tabs) {
      let act = '';
      if (name === this.state.current) {
        act = ' post_tab_active';
      }
      tabs.push(
        <li
          key={'tab_' + name}
          data-tab={name}
          onClick={this.onTabClick}
          className={'post_tab' + act}
        >
          {title}
        </li>
      );
    }

    return (
      <div className="bigrams_tabs_container">
        <ul className="post_tabs_list">{tabs}</ul>
      </div>
    );
  }

  changeTab(tab) {
    this.setState({ current: tab });
  }
}
