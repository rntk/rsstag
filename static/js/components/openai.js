'use strict';
import React from 'react';

export class OpenAITool extends React.Component{
    constructor(props) {
        super(props);
        this.updateResponse = this.updateResponse.bind(this);
        this.changeRequest = this.changeRequest.bind(this);
        this.getResponse = this.getResponse.bind(this);
        this.state = {user: "", response: ""}
    }

    updateResponse(state) {
        this.setState(state);
    }

    componentDidMount() {
        this.props.ES.bind(this.props.ES.OPENAI_GOT_RESPONSE, this.updateResponse);
        //subscribe
    }

    componentWillUnmount() {
        this.props.ES.unbind(this.props.ES.OPENAI_GOT_RESPONSE, this.updateResponse);
        //unsubscribe
    }

    getResponse(e) {
        let data = {
            user: this.state.user,
        }
        this.props.ES.trigger(this.props.ES.OPENAI_GET_RESPONSE, data);
    }
    changeRequest(e) {
        this.setState({
            user: e.target.value,
            response: this.state.response
        });
    }

    render() {
        return (<table className="openai_tool_table">
            <tbody>
            <tr>
                <td className="tag_prompt_response">
                    <pre>{this.state? this.state.response: ""}</pre>
                </td>
            </tr>
            <tr>
                <td className="tag_prompt_field">
                    <textarea onChange={this.changeRequest}>
                    {this.state? this.state.user: ""}
                    </textarea>
                </td>
            </tr>
            <tr>
                <td colSpan={"2"}>
                    <button onClick={this.getResponse}>Get response</button>
                </td>
            </tr>
            </tbody>
        </table>);
    }
}
