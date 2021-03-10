'use strict';
import React from 'react';

export default class TagContexts extends React.Component {
    constructor(props) {
        super(props);
        this.state = {tag: props.tag, texts: []};
        this.updateState = this.updateState.bind(this);
    }

    updateState(state) {
        this.setState(state)
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.WORDTREE_TEXTS_UPDATED, this.updateState);
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.WORDTREE_TEXTS_UPDATED, this.updateState);
    }

    render() {
        if (!this.state.texts) {
            return <p>No data yet</p>;
        }
        let texts = [];
        let texts_s = Array.from(new Set(this.state.texts));
        texts_s.sort();
        let middle_style = {
            textAlign: "center",
            vertical: "middle",
            padding: "1em",
            fontWeight: "bold"
        };
        let left_style = {
            textAlign: "center",
        }
        let right_style = {
            textAlign: "center",
            padding: "0px",
            verticalAlign: "top"
        }
        let tag = this.state.tag;
        let lefts = [];
        let middles = [];
        let rights = [];
        let fn = (text, text_i) => {
            let l = [];
            let words = text.split(" ");
            for (let i = 0; i < words.length; i++) {
                let word = words[i];
                l.push(<p key={word + "_" + i + "_" + text_i + "_"}>{word}</p>)
            }

            return l;
        }
        for (let i = 0; i < texts_s.length; i++) {
            let txt = texts_s[i];
            let pos = txt.indexOf(tag);
            let left_txt = txt.substr(0, pos);
            let right_txt = txt.substr(pos + tag.length + 1, txt.length);
            lefts.push(<td style={left_style} key={"txt_left" + i}>{fn(left_txt, i)}</td>);
            middles.push(<td style={middle_style} key={"txt_middle" + i}>{tag}</td>);
            rights.push(<td style={right_style} key={"txt_right" + i}>{fn(right_txt, i)}</td>);
            /*texts.push(
                <tr key={"txt" + i}>
                    <td key={"txt_left" + i} style={left_style}>{left_txt}</td>
                    <td key={"txt_middle" + i} style={middle_style}>{tag}</td>
                    <td key={"txt_right" + i} style={right_style}>{right_txt}</td>
                </tr>
            );*/
        }

        return <div style={{overflow: "scroll"}}>
            <table>
                <tbody>
                    <tr>{lefts}</tr>
                    <tr>{middles}</tr>
                    <tr>{rights}</tr>
                </tbody>
            </table>
        </div>
    }
};