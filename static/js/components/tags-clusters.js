'use strict';
import React from 'react';

export class TagsClustersTxtList extends React.Component {
  constructor(props) {
    super(props);
    this.updateTags = this.updateTags.bind(this);
  }

  updateTags(state) {
    this.setState(state);
  }

  componentDidMount() {
    this.props.ES.bind(this.props.ES.TAGS_CLUSTERS_UPDATED, this.updateTags);
    //subscribe
  }

  componentWillUnmount() {
    this.props.ES.unbind(this.props.ES.TAGS_CLUSTERS_UPDATED, this.updateTags);
    //unsubscribe
  }

  render() {
    if (this.state && this.state.clusters) {
      let tbodies = [];
      for (let label in this.state.clusters) {
        let rows = [];
        let skip_tag = false;
        let txt_i = 0;
        const words_n = 15;
        for (let txt_d of this.state.clusters[label]) {
          const txt = txt_d.txt;
          let pos = txt.search(this.props.tag);
          let bf = txt.substr(0, pos);
          let words = bf.split(' ');
          bf = words.splice(words.length - words_n).join(' ');
          let af = txt.substr(pos + this.props.tag.length);
          words = af.split(' ');
          af = words.splice(0, words_n).join(' ');
          let tag_td = null;
          if (!skip_tag) {
            let pids = [];
            for (let txt_dd of this.state.clusters[label]) {
              pids.push(txt_dd.pid);
            }
            tag_td = (
              <td
                className="tag_txt_clusters_td_middle"
                rowSpan={this.state.clusters[label].length}
              >
                <a href={'/posts/' + pids.join('_')}>{this.props.tag}</a>
              </td>
            );
          }
          rows.push(
            <tr key={`label_${label}_${txt_i}`} className="tag_txt_clusters_tr">
              <td className="tag_txt_clusters_td_left">{bf}</td>
              {tag_td}
              <td className="tag_txt_clusters_td_right">{af}</td>
            </tr>
          );
          txt_i++;
          skip_tag = true;
        }
        tbodies.push(
          <tbody className="tag_txt_clusters_cluster" key={'label_body' + label}>
            {rows}
          </tbody>
        );
      }
      return <table className="cloud">{tbodies}</table>;
    } else {
      return <p>No tags</p>;
    }
  }
}

export default class TagsClustersList extends React.Component {
  constructor(props) {
    super(props);
    this.updateTags = this.updateTags.bind(this);
  }

  updateTags(state) {
    this.setState(state);
  }

  componentDidMount() {
    this.props.ES.bind(this.props.ES.TAGS_CLUSTERS_UPDATED, this.updateTags);
    //subscribe
  }

  componentWillUnmount() {
    this.props.ES.unbind(this.props.ES.TAGS_CLUSTERS_UPDATED, this.updateTags);
    //unsubscribe
  }

  render() {
    if (!this.state || !this.state.clusters) {
      return <p>No clusters</p>;
    }
    let pids_labels = [];
    for (let label in this.state.clusters) {
      let pids = [];
      for (let cl of this.state.clusters[label]) {
        pids.push(cl.pid);
      }
      pids_labels.push({
        lbl: label,
        pids: pids,
      });
    }
    pids_labels = pids_labels.sort((a, b) => {
      return b.pids.length - a.pids.length;
    });
    let clust_links = [];
    for (let pids_l of pids_labels) {
      let pids_s = pids_l.pids.join('_');
      clust_links.push(
        <a
          href={`/posts/${pids_s}`}
          className="cluster_link"
          key={'cluster_' + pids_l.lbl}
        >{`${pids_l.lbl} (${pids_l.pids.length})`}</a>
      );
    }
    return <div className="cloud">{clust_links}</div>;
  }
}
